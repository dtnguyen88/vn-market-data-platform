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
  description = "Workflow name."
}

variable "description" {
  type        = string
  default     = ""
  description = "Workflow description."
}

variable "source_file_path" {
  type        = string
  description = "Path to the workflow YAML, relative to the env directory."
}

variable "service_account_email" {
  type        = string
  description = "Workflow runtime service account email."
}

variable "labels" {
  type        = map(string)
  default     = {}
  description = "Resource labels (env, owner, etc.)."
}
