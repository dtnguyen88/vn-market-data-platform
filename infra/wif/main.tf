terraform {
  required_version = ">= 1.7"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 5.30" }
  }
}

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "github-${var.env}"
  display_name              = "GitHub Actions (${var.env})"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub OIDC"
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "cicd_deploy" {
  project      = var.project_id
  account_id   = "cicd-deploy-sa"
  display_name = "CI/CD Deploy SA (used by GitHub Actions via WIF)"
}

# Grant cicd-deploy-sa the roles needed to deploy via terraform.
# Tighten in v2; owner is broad but acceptable per Phase 01 review.
resource "google_project_iam_member" "cicd_deploy_owner" {
  project = var.project_id
  role    = "roles/owner"
  member  = "serviceAccount:${google_service_account.cicd_deploy.email}"
}

# Bind the WIF principal (GitHub repo) to the cicd-deploy-sa.
resource "google_service_account_iam_member" "github_wif_binding" {
  service_account_id = google_service_account.cicd_deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}

output "wif_provider_resource" {
  value       = google_iam_workload_identity_pool_provider.github.name
  description = "Use this in GitHub secret WIF_PROVIDER_<ENV>."
}

output "cicd_sa_email" {
  value       = google_service_account.cicd_deploy.email
  description = "Use this in GitHub secret WIF_SA_<ENV>."
}
