output "memory_id" {
  description = "The ID of the AgentCore memory resource"
  value       = aws_bedrockagentcore_memory.this.id
}

output "memory_arn" {
  description = "The ARN of the AgentCore memory resource"
  value       = aws_bedrockagentcore_memory.this.arn
}
