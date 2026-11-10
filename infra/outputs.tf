output "service_url" {
  description = "Public URL of the app."
  value       = google_cloud_run_v2_service.app.uri
}

output "github_variables" {
  description = "GitHub Actions repository variables used by the deploy and demo-reset workflows."
  value = {
    GCP_PROJECT_ID   = var.project_id
    GCP_REGION       = var.region
    GCP_WIF_PROVIDER = google_iam_workload_identity_pool_provider.github.name
    GCP_DEPLOY_SA    = google_service_account.deployer.email
    DEMO_URL         = google_cloud_run_v2_service.app.uri
  }
}
