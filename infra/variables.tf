variable "project_id" {
  description = "Google Cloud project ID."
  type        = string
}

variable "region" {
  description = "Cloud Run and Artifact Registry region. europe-west1 is a Tier 1 (cheaper) region."
  type        = string
  default     = "europe-west1"
}

variable "github_repository" {
  description = "GitHub repository allowed to deploy, as owner/name."
  type        = string
  default     = "Wojgos/jobfit"
}

variable "use_gemini" {
  description = "Use Gemini (needs the jobfit-google-api-key secret). False runs the offline fake LLM."
  type        = bool
  default     = true
}

variable "max_instances" {
  description = "Upper bound on Cloud Run instances - the main protection against a runaway bill."
  type        = number
  default     = 1
}
