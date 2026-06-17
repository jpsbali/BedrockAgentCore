data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  log_group_name = "/aws/vendedlogs/bedrock-agentcore/${var.resource_id}"
}

resource "aws_cloudwatch_log_group" "this" {
  name              = local.log_group_name
  retention_in_days = var.log_retention_days
}

# Allow the vended-logs delivery service to write to this log group
resource "aws_cloudwatch_log_resource_policy" "vended_logs_delivery" {
  policy_name = "bedrock-agentcore-vended-logs-${var.resource_id}"

  policy_document = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowVendedLogsDelivery"
      Effect    = "Allow"
      Principal = { Service = "delivery.logs.amazonaws.com" }
      Action    = ["logs:CreateLogStream", "logs:PutLogEvents"]
      Resource  = "${aws_cloudwatch_log_group.this.arn}:*"
      Condition = {
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
        ArnLike      = { "aws:SourceArn" = "arn:aws:logs:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:*" }
      }
    }]
  })
}

resource "aws_cloudwatch_log_delivery_source" "logs" {
  count        = var.enable_app_logs ? 1 : 0
  name         = "${var.resource_id}-logs-source"
  log_type     = "APPLICATION_LOGS"
  resource_arn = var.resource_arn
}

resource "aws_cloudwatch_log_delivery_source" "traces" {
  name         = "${var.resource_id}-traces-source"
  log_type     = "TRACES"
  resource_arn = var.resource_arn
}

resource "aws_cloudwatch_log_delivery_destination" "logs" {
  count = var.enable_app_logs ? 1 : 0
  name  = "${var.resource_id}-logs-destination"
  delivery_destination_configuration {
    destination_resource_arn = aws_cloudwatch_log_group.this.arn
  }
}

resource "aws_cloudwatch_log_delivery_destination" "traces" {
  name                      = "${var.resource_id}-traces-destination"
  delivery_destination_type = "XRAY"
}

resource "aws_cloudwatch_log_delivery" "logs" {
  count                    = var.enable_app_logs ? 1 : 0
  delivery_source_name     = aws_cloudwatch_log_delivery_source.logs[0].name
  delivery_destination_arn = aws_cloudwatch_log_delivery_destination.logs[0].arn
  depends_on               = [aws_cloudwatch_log_resource_policy.vended_logs_delivery]
}

resource "aws_cloudwatch_log_delivery" "traces" {
  delivery_source_name     = aws_cloudwatch_log_delivery_source.traces.name
  delivery_destination_arn = aws_cloudwatch_log_delivery_destination.traces.arn
}
