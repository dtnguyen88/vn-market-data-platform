variable "project_id" {
  type        = string
  description = "GCP project ID."
}

variable "display_name" {
  type        = string
  description = "Human-readable alert policy name."
}

variable "documentation" {
  type        = string
  default     = ""
  description = "Markdown explanation of the alert."
}

variable "filter" {
  type        = string
  description = "MQL or filter expression for the time-series."
}

variable "duration_seconds" {
  type        = number
  default     = 60
  description = "Duration the condition must hold true to trigger."
}

variable "threshold_value" {
  type        = number
  description = "Threshold for the metric."
}

variable "comparison" {
  type        = string
  default     = "COMPARISON_LT"
  description = "COMPARISON_GT|COMPARISON_LT|COMPARISON_EQ etc."
}

variable "notification_channel_ids" {
  type        = list(string)
  description = "List of notification channel IDs."
}

variable "labels" {
  type        = map(string)
  default     = {}
  description = "User labels."
}

variable "per_series_aligner" {
  type        = string
  default     = "ALIGN_MEAN"
  description = "Aligner: ALIGN_RATE for DELTA/cumulative, ALIGN_MEAN for GAUGE."
}
