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
    # SSI FastConnect v3 (current)
    "ssi-fc-api-key",
    "ssi-fc-api-secret",
    "ssi-fc-rsa-private-key",
    # SSI FastConnect v2 (legacy, kept for now until callers verified clean)
    "ssi-fc-username",
    "ssi-fc-password",
    # Alerter
    "telegram-bot-token",
    "telegram-chat-id",
    # Research-app basic auth gate (consumed by research_app module via env_vars_from_secret)
    "research-app-username",
    "research-app-password",
  ]
  description = "Secret IDs to provision (no values; populated out-of-band via `gcloud secrets versions add`)."
}
