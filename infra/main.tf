locals {
  services = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "cloudresourcemanager.googleapis.com",
  ]
  # Created by hand with `gcloud secrets create`, so their values never end up in
  # Terraform state or in this repository (see docs/DEPLOY.md).
  secrets = merge(
    {
      DATABASE_URL = "jobfit-database-url"
      ADMIN_TOKEN  = "jobfit-admin-token"
    },
    var.use_gemini ? { GOOGLE_API_KEY = "jobfit-google-api-key" } : {}
  )
}

resource "google_project_service" "enabled" {
  for_each           = toset(local.services)
  service            = each.value
  disable_on_destroy = false
}

# --- Container images ------------------------------------------------------------------

resource "google_artifact_registry_repository" "images" {
  repository_id = "jobfit"
  location      = var.region
  format        = "DOCKER"
  description   = "JobFit images built by GitHub Actions"

  # Stay within the free 0.5 GB of storage: only the two newest images survive.
  cleanup_policy_dry_run = false
  cleanup_policies {
    id     = "keep-two-newest"
    action = "KEEP"
    most_recent_versions {
      keep_count = 2
    }
  }
  cleanup_policies {
    id     = "delete-older"
    action = "DELETE"
    condition {
      older_than = "86400s"
    }
  }

  depends_on = [google_project_service.enabled]
}

# --- Runtime identity and secrets ------------------------------------------------------

resource "google_service_account" "runtime" {
  account_id   = "jobfit-runtime"
  display_name = "JobFit Cloud Run runtime"
  depends_on   = [google_project_service.enabled]
}

data "google_secret_manager_secret" "app" {
  for_each   = local.secrets
  secret_id  = each.value
  depends_on = [google_project_service.enabled]
}

resource "google_secret_manager_secret_iam_member" "runtime_access" {
  for_each  = data.google_secret_manager_secret.app
  secret_id = each.value.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

# --- Cloud Run service -----------------------------------------------------------------

resource "google_cloud_run_v2_service" "app" {
  name                = "jobfit"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account                  = google_service_account.runtime.email
    timeout                          = "120s"
    max_instance_request_concurrency = 40

    scaling {
      min_instance_count = 0 # scale to zero: no traffic, no cost
      max_instance_count = var.max_instances
    }

    containers {
      # Placeholder until the first GitHub Actions deploy pushes the real image.
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle          = true # CPU is billed only while handling requests
        startup_cpu_boost = true
      }

      env {
        name  = "DEMO_MODE"
        value = "true"
      }
      env {
        name  = "LLM_PROVIDER"
        value = var.use_gemini ? "gemini" : "fake"
      }
      env {
        name  = "RATE_LIMIT_PER_HOUR"
        value = "20"
      }

      dynamic "env" {
        for_each = local.secrets
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }
    }
  }

  lifecycle {
    # The image is rolled out by GitHub Actions; Terraform owns everything else.
    ignore_changes = [template[0].containers[0].image, client, client_version]
  }

  depends_on = [google_secret_manager_secret_iam_member.runtime_access]
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  name     = google_cloud_run_v2_service.app.name
  location = google_cloud_run_v2_service.app.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# --- Keyless deploys from GitHub Actions (Workload Identity Federation) ----------------

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"
  depends_on                = [google_project_service.enabled]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }
  # Only workflows of this repository running on main can get credentials.
  attribute_condition = "assertion.repository == '${var.github_repository}' && assertion.ref == 'refs/heads/main'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "deployer" {
  account_id   = "jobfit-deployer"
  display_name = "JobFit deployer (GitHub Actions)"
  depends_on   = [google_project_service.enabled]
}

resource "google_service_account_iam_member" "deployer_federation" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

resource "google_artifact_registry_repository_iam_member" "deployer_push" {
  repository = google_artifact_registry_repository.images.name
  location   = google_artifact_registry_repository.images.location
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deployer.email}"
}

# Project level: `gcloud run deploy` also reads operations and locations, not just the service.
resource "google_project_iam_member" "deployer_deploy" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

# Deploying a revision that runs as the runtime account requires actAs on it.
resource "google_service_account_iam_member" "deployer_act_as_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}
