resource "aws_bedrockagentcore_api_key_credential_provider" "this" {
  name               = var.name
  api_key_wo         = var.api_key
  api_key_wo_version = 1
}
