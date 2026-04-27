module "service_accounts" {
  source     = "../../modules/service-accounts"
  project_id = var.project_id
}

module "secrets" {
  source     = "../../modules/secrets"
  project_id = var.project_id
}
