terraform {
  required_version = "= 1.16.4"
  required_providers {
    fabric = {
      source  = "microsoft/fabric"
      version = "= 1.14.0"
    }
  }
}

# Local bootstrap uses Azure CLI. GitHub infrastructure jobs use OIDC environment
# variables. Configure exactly one authentication mechanism for each invocation.
provider "fabric" {}
