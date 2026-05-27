terraform {
  required_version = ">= 1.7"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
  }
}

resource "google_cloud_run_v2_service" "service" {
  project  = var.project_id
  location = var.location
  name     = var.name
  ingress  = var.ingress

  # Always ignore min_instance_count drift. Publisher shards are patched by the
  # publisher-scaler workflow at market open/close; without this, every
  # `terraform apply` would revert the scaler to the value declared here.
  # For services not under scaler control (writers, alerter, research-app),
  # the literal min_instances value still takes effect on initial create —
  # only subsequent drift is ignored, which is acceptable since manual scale
  # changes on those services are rare and intentional.
  lifecycle {
    ignore_changes = [template[0].scaling[0].min_instance_count]
  }

  template {
    service_account = var.service_account_email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    timeout = var.timeout

    containers {
      image = var.image

      ports {
        container_port = var.port
      }

      resources {
        limits = {
          memory = var.memory
          cpu    = var.cpu
        }
      }

      dynamic "env" {
        for_each = var.env_vars
        content {
          name  = env.key
          value = env.value
        }
      }
      dynamic "env" {
        for_each = var.env_vars_from_secret
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value.secret
              version = env.value.version
            }
          }
        }
      }
    }
  }
}
