resource "aws_bedrockagentcore_oauth2_credential_provider" "this" {
  name = var.name

  credential_provider_vendor = "CustomOauth2"
  oauth2_provider_config {
    custom_oauth2_provider_config {
      client_id_wo                  = var.client_id
      client_secret_wo              = var.client_secret
      client_credentials_wo_version = 1

      oauth_discovery {
        discovery_url = var.discovery_url
      }

    }
  }
}
