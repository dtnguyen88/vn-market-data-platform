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
  description = "Service name."
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

variable "min_instances" {
  type        = number
  default     = 0
  description = "Minimum instance count."
}

variable "max_instances" {
  type        = number
  default     = 5
  description = "Maximum instance count."
}

variable "memory" {
  type        = string
  default     = "1Gi"
  description = "Memory limit per instance."
}

variable "cpu" {
  type        = string
  default     = "1"
  description = "CPU limit per instance."
}

variable "port" {
  type        = number
  default     = 8080
  description = "Container listen port."
}

variable "ingress" {
  type        = string
  default     = "INGRESS_TRAFFIC_ALL"
  description = "INGRESS_TRAFFIC_ALL or INGRESS_TRAFFIC_INTERNAL_ONLY."
}

variable "timeout" {
  type        = string
  default     = "60s"
  description = "Request timeout."
}
