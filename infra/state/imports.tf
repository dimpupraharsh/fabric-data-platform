# Adopt the dedicated bucket bootstrapped through the authorized AWS console.
# These imports are safe to retain after adoption; they do not recreate objects.
import {
  to = aws_s3_bucket.state
  id = "retail-oi-terraform-state-981450247725"
}

import {
  to = aws_s3_bucket_public_access_block.state
  id = "retail-oi-terraform-state-981450247725"
}

import {
  to = aws_s3_bucket_ownership_controls.state
  id = "retail-oi-terraform-state-981450247725"
}

import {
  to = aws_s3_bucket_versioning.state
  id = "retail-oi-terraform-state-981450247725"
}

import {
  to = aws_s3_bucket_server_side_encryption_configuration.state
  id = "retail-oi-terraform-state-981450247725"
}

import {
  to = aws_s3_bucket_policy.tls_only
  id = "retail-oi-terraform-state-981450247725"
}
