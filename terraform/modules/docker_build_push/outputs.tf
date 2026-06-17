output "repository_url" {
  description = "The URL of the repository"
  value       = aws_ecr_repository.this.repository_url
}

output "ecr_uri" {
  description = "The URI of the pushed image (repo_url:tag)"
  value       = "${aws_ecr_repository.this.repository_url}:${var.image_tag}-${local.source_hash}"
  depends_on  = [null_resource.trigger_build]
}
