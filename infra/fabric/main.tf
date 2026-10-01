variable "capacity_id" {
  description = "Existing active Fabric capacity; this module never purchases capacity."
  type        = string
}

variable "workspace_names" {
  description = "Separate workspaces. Existing Production is imported, never recreated."
  type        = map(string)
  default = {
    dev        = "Retail Order Intelligence Platform - Dev"
    test       = "Retail Order Intelligence Platform - Test"
    production = "Retail Order Intelligence Platform"
  }
  validation {
    condition     = length(var.workspace_names) == 3 && alltrue([for e in ["dev", "test", "production"] : contains(keys(var.workspace_names), e)])
    error_message = "Exactly dev, test and production are required."
  }
}

variable "deployment_principals" {
  description = "Environment-specific service principal object IDs. Empty during bootstrap."
  type        = map(string)
  default     = {}
}

resource "fabric_workspace" "environment" {
  for_each     = var.workspace_names
  display_name = each.value
  capacity_id  = var.capacity_id
  identity = {
    type = "SystemAssigned"
  }
  lifecycle {
    prevent_destroy = true
    # Existing system-assigned workspace identities are not deployment identities.
    # Their connection authentication must remain intact during this adoption.
    ignore_changes = [description]
  }
}

resource "fabric_workspace_role_assignment" "deployer" {
  for_each     = var.deployment_principals
  workspace_id = fabric_workspace.environment[each.key].id
  principal = {
    id   = each.value
    type = "ServicePrincipal"
  }
  role = "Contributor"
  lifecycle {
    prevent_destroy = true
  }
}

output "workspace_ids" {
  description = "Use these IDs in environment configuration, not hard-coded in release code."
  value       = { for e, w in fabric_workspace.environment : e => w.id }
}
