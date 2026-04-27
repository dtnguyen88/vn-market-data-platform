variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type        = string
  default     = "asia-southeast1"
  description = "Default region for regional resources"
}

variable "env" {
  type        = string
  description = "Environment: staging, prod, test"
  validation {
    condition     = contains(["staging", "prod", "test"], var.env)
    error_message = "env must be one of: staging, prod, test."
  }
}
