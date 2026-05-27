variable "project_id" {
  type        = string
  description = "GCP project ID where the bucket is created."
}

variable "name" {
  type        = string
  description = "Globally unique bucket name (no gs:// prefix)."
}

variable "location" {
  type        = string
  default     = "asia-southeast1"
  description = "Bucket location (region or multi-region). Default asia-southeast1."
}

variable "versioning" {
  type        = bool
  default     = true
  description = "Enable object versioning. Default true."
}

variable "noncurrent_age_days" {
  type        = number
  default     = 30
  description = "Days after which non-current versions are deleted. Default 30."
}

variable "tiering_enabled" {
  type        = bool
  default     = false
  description = "If true, transition STANDARD → NEARLINE at 30d, NEARLINE → COLDLINE at 90d. Use for data-lake buckets; leave off for state/build buckets."
}
