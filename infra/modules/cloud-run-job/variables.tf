variable "project_id" {
  type        = string
  description = "GCP project ID."
}

variable "location" {
  type        = string
  default     = "asia-southeast1"
  description = "Region."
}

variable "name" {
  type        = string
  description = "Cloud Run Job name."
}

variable "image" {
  type        = string
  description = "Container image URI (Artifact Registry)."
}

variable "service_account_email" {
  type        = string
  description = "Runtime service account email."
}

variable "env_vars" {
  type        = map(string)
  default     = {}
  description = "Environment variables for the container."
}

variable "task_count" {
  type        = number
  default     = 1
  description = "Number of tasks per execution. Use >1 for parallel backfill."
}

variable "parallelism" {
  type        = number
  default     = 1
  description = "Max tasks running in parallel within a single execution."
}

variable "task_timeout" {
  type        = string
  default     = "1800s"
  description = "Per-task timeout (e.g. \"1800s\" = 30 min)."
}

variable "max_retries" {
  type        = number
  default     = 3
  description = "Per-task max retry attempts on failure."
}

variable "memory" {
  type        = string
  default     = "2Gi"
  description = "Memory limit per task."
}

variable "cpu" {
  type        = string
  default     = "1"
  description = "CPU limit per task."
}
