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
  description = "Scheduler job name."
}

variable "description" {
  type        = string
  default     = ""
  description = "Scheduler job description."
}

variable "schedule" {
  type        = string
  description = "Cron expression (5-field standard cron)."
}

variable "time_zone" {
  type        = string
  default     = "Asia/Ho_Chi_Minh"
  description = "IANA timezone for the cron expression."
}

variable "target_workflow_id" {
  type        = string
  description = "Fully-qualified Workflows resource ID to trigger."
}

variable "service_account_email" {
  type        = string
  description = "Service account used to invoke Workflows (needs roles/workflows.invoker)."
}

variable "request_body" {
  type        = string
  default     = "{}"
  description = "JSON request body passed as argument to the workflow execution."
}
