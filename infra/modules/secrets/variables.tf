variable "project_id" {
  type        = string
  description = "GCP project ID where the secrets are created."
}

variable "region" {
  type        = string
  default     = "asia-southeast1"
  description = "Region used for user-managed Secret Manager replication."
}

variable "secret_names" {
  type = list(string)
  default = [
    "ssi-fc-username",
    "ssi-fc-password",
    "telegram-bot-token",
    "telegram-chat-id",
  ]
  description = "Secret IDs to provision (no values; populated out-of-band)."
}
