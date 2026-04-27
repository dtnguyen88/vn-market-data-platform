variable "project_id" {
  type        = string
  description = "GCP project ID for production."
}

variable "region" {
  type        = string
  default     = "asia-southeast1"
  description = "Default region for regional resources."
}
