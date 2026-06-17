output "arn" {
  value = aws_bedrockagentcore_api_key_credential_provider.this.credential_provider_arn
}

output "name" {
  value = aws_bedrockagentcore_api_key_credential_provider.this.name
}
