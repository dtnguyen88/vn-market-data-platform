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
    # NOTE: SSI v3 secrets (ssi-fc-api-key/secret/rsa-private-key) are managed
    # OUT OF BAND via `gcloud secrets create ...` with `auto` replication. Adding
    # them here would force destroy+recreate to user_managed replication, losing
    # the values. Keep them out of this list; only add new secrets created with
    # user_managed replication (matching this module's policy).
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
  description = "Secret IDs to provision (no values; populated out-of-band via `gcloud secrets versions add`). Must match module's user_managed replication or pre-exist with it."
}
