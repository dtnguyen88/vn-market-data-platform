variable "project_id" {
  type        = string
  description = "GCP project ID."
}

variable "github_repo" {
  type        = string
  description = "GitHub owner/repo (e.g., 'ducthong/vn-market-data-platform')."
}

variable "env" {
  type        = string
  description = "Environment label (staging|prod|test)."
}
