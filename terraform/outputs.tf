output "kyc_agent_runtime_arn" {
  value = module.runtime_kyc_agent.agent_runtime_arn
}

output "kyc_agent_arn" {
  value = module.runtime_kyc_agent.agent_runtime_arn
}

output "doc_extraction_agent_runtime_arn" {
  value = module.runtime_doc_extraction_agent.agent_runtime_arn
}

output "doc_extraction_agent_arn" {
  value = module.runtime_doc_extraction_agent.agent_runtime_arn
}

output "property_research_agent_runtime_arn" {
  value = module.runtime_property_research_agent.agent_runtime_arn
}

output "property_research_agent_arn" {
  value = module.runtime_property_research_agent.agent_runtime_arn
}

output "consolidation_agent_runtime_arn" {
  value = module.runtime_consolidation_agent.agent_runtime_arn
}

output "consolidation_agent_arn" {
  value = module.runtime_consolidation_agent.agent_runtime_arn
}

output "kyc_tools_runtime_url" {
  value = local.kyc_tools_url
}

output "kyc_tools_arn" {
  value = module.runtime_kyc_tools.agent_runtime_arn
}

output "secrets_manager_secret_arn" {
  value = aws_secretsmanager_secret.client_creds.arn
}

output "geocoding_gateway_url" {
  value = module.geocoding_gateway.gateway_url
}

output "memory_id" {
  description = "AgentCore Memory ID for session persistence"
  value       = module.memory.memory_id
}
