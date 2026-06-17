output "agent_runtime_arn" {
  value = aws_bedrockagentcore_agent_runtime.this.agent_runtime_arn
}

output "agent_runtime_role_name" {
  value = aws_iam_role.agent_runtime_role.name
}
