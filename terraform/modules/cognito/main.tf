resource "aws_cognito_user_pool" "this" {
  name = var.pool_name
}

resource "aws_cognito_user_pool_domain" "this" {
  domain       = var.domain_prefix
  user_pool_id = aws_cognito_user_pool.this.id
}

resource "aws_cognito_resource_server" "this" {
  identifier   = var.resource_server_identifier
  name         = "Resource Server for ${var.pool_name}"
  user_pool_id = aws_cognito_user_pool.this.id

  scope {
    scope_name        = "access"
    scope_description = "Access scope"
  }
}

resource "aws_cognito_user_pool_client" "this" {
  name = var.client_name

  user_pool_id    = aws_cognito_user_pool.this.id
  generate_secret = true

  allowed_oauth_flows                  = ["client_credentials"]
  allowed_oauth_scopes                 = ["${var.resource_server_identifier}/access"]
  allowed_oauth_flows_user_pool_client = true
  prevent_user_existence_errors        = "ENABLED"

  depends_on = [aws_cognito_resource_server.this]
}
