terraform {
  required_version = "= 1.16.4"
  required_providers {
    azuread = {
      source  = "hashicorp/azuread"
      version = "= 3.10.0"
    }
  }
}

provider "azuread" {
  tenant_id = "cf22b271-7261-4a07-9b4f-a04dde6ba1b1"
}

data "azuread_client_config" "operator" {}

locals {
  environments = toset(["dev", "test", "production"])
  # GitHub immutable subject format: verified against the repository OIDC API.
  github_subject_prefix = "repo:dimpupraharsh@148876828/fabric-data-platform@1394039561"
}

resource "azuread_application" "deployment" {
  for_each     = local.environments
  display_name = "retail-oi-deploy-${each.key}"
  owners       = [data.azuread_client_config.operator.object_id]
  lifecycle {
    prevent_destroy = true
  }
}

resource "azuread_service_principal" "deployment" {
  for_each  = local.environments
  client_id = azuread_application.deployment[each.key].client_id
  owners    = [data.azuread_client_config.operator.object_id]
  lifecycle {
    prevent_destroy = true
  }
}

resource "azuread_application_federated_identity_credential" "github" {
  for_each       = local.environments
  application_id = azuread_application.deployment[each.key].id
  display_name   = "github-${each.key}"
  description    = "Only this repository's protected environment can request deployment tokens."
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "${local.github_subject_prefix}:environment:${each.key}"
}

output "deployment_principals" {
  value = { for e, p in azuread_service_principal.deployment : e => p.object_id }
}
output "deployment_client_ids" {
  value = { for e, a in azuread_application.deployment : e => a.client_id }
}
