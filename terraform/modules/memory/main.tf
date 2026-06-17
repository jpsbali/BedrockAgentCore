resource "aws_bedrockagentcore_memory" "this" {
  name                  = "${var.name}_${var.suffix}"
  event_expiry_duration = 7
}
