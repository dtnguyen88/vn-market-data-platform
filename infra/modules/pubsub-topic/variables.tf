variable "project_id" {
  type        = string
  description = "GCP project ID."
}

variable "name" {
  type        = string
  description = "Pub/Sub topic name (also used as prefix for the paired DLQ topic and subscription)."
}

variable "ack_deadline_seconds" {
  type        = number
  default     = 60
  description = "Subscriber ack deadline in seconds. Default 60s (Cloud Run service request budget)."
}

variable "max_delivery_attempts" {
  type        = number
  default     = 5
  description = "Maximum delivery attempts before message is forwarded to the DLQ topic."
}

variable "minimum_backoff" {
  type        = string
  default     = "10s"
  description = "Min backoff between redelivery attempts (Pub/Sub duration string, e.g. \"10s\")."
}

variable "maximum_backoff" {
  type        = string
  default     = "600s"
  description = "Max backoff between redelivery attempts."
}
