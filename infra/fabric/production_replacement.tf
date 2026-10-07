# The legacy template-app workspace remains protected in environment["production"].
# Create the eligible target additively; migrate data before deleting the legacy.
resource "fabric_workspace" "production_replacement" {
  display_name = "Retail Order Intelligence Platform - Production"
  description  = "Normal Production deployment target for the retail platform. Cutover pending verified migration from the legacy template-app workspace; schedules and releases remain disabled."
  capacity_id  = var.capacity_id
  identity = {
    type = "SystemAssigned"
  }
  lifecycle {
    prevent_destroy = true
  }
}

resource "fabric_workspace_role_assignment" "production_replacement_deployer" {
  workspace_id = fabric_workspace.production_replacement.id
  principal = {
    id   = var.deployment_principals["production"]
    type = "ServicePrincipal"
  }
  role = "Contributor"
  lifecycle {
    prevent_destroy = true
  }
}

resource "fabric_workspace_role_assignment" "production_replacement_runtime" {
  workspace_id = fabric_workspace.production_replacement.id
  principal = {
    id   = fabric_workspace.production_replacement.identity.service_principal_id
    type = "ServicePrincipal"
  }
  role = "Contributor"
  lifecycle {
    prevent_destroy = true
  }
}

output "production_replacement_workspace_id" {
  description = "Eligible Production stage target, not yet the active data-serving workspace."
  value       = fabric_workspace.production_replacement.id
}
