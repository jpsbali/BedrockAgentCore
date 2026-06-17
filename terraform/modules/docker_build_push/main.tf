locals {
  # CodeBuild Environment configurations
  is_arm = upper(var.target_arch) == "ARM64"

  compute_type = "BUILD_GENERAL1_SMALL"
  image        = local.is_arm ? "aws/codebuild/amazonlinux2-aarch64-standard:3.0" : "aws/codebuild/standard:7.0"
  type         = local.is_arm ? "ARM_CONTAINER" : "LINUX_CONTAINER"

  # Calculate a hash of the source directory to trigger rebuilds
  source_hash = sha1(join("", [for f in fileset(var.source_path, "**") : filesha1("${var.source_path}/${f}")]))
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# 1. ECR Repository
resource "aws_ecr_repository" "this" {
  name                 = var.repo_name
  image_tag_mutability = "MUTABLE"
  force_delete         = var.force_delete

  image_scanning_configuration {
    scan_on_push = true
  }
}

# 2. S3 Bucket for Source
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "source" {
  bucket        = "codebuild-source-${var.repo_name}-${random_id.bucket_suffix.hex}"
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "source" {
  bucket = aws_s3_bucket.source.id
  versioning_configuration {
    status = "Disabled"
  }
}

# 3. Zip and Upload Source
data "archive_file" "source_zip" {
  type        = "zip"
  source_dir  = var.source_path
  output_path = "${path.module}/source-${local.source_hash}.zip"
}

resource "aws_s3_object" "source_zip" {
  bucket = aws_s3_bucket.source.id
  key    = "source-${local.source_hash}.zip"
  source = data.archive_file.source_zip.output_path
  etag   = data.archive_file.source_zip.output_md5
}

# 4. IAM Role for CodeBuild
resource "aws_iam_role" "codebuild" {
  name = "codebuild-${var.repo_name}-${random_id.bucket_suffix.hex}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "codebuild.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "codebuild" {
  role = aws_iam_role.codebuild.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:CompleteLayerUpload",
          "ecr:GetDownloadUrlForLayer",
          "ecr:InitiateLayerUpload",
          "ecr:PutImage",
          "ecr:UploadLayerPart"
        ]
        Resource = aws_ecr_repository.this.arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion"
        ]
        Resource = "${aws_s3_bucket.source.arn}/*"
      }
    ]
  })
}

# 5. CodeBuild Project
resource "aws_codebuild_project" "this" {
  name          = "build-${var.repo_name}-${random_id.bucket_suffix.hex}"
  description   = "Builds docker image for ${var.repo_name}"
  build_timeout = "10"
  service_role  = aws_iam_role.codebuild.arn

  artifacts {
    type = "NO_ARTIFACTS"
  }

  environment {
    compute_type                = local.compute_type
    image                       = local.image
    type                        = local.type
    image_pull_credentials_type = "CODEBUILD"
    privileged_mode             = true # Required for Docker

    environment_variable {
      name  = "AWS_DEFAULT_REGION"
      value = data.aws_region.current.region
    }
    environment_variable {
      name  = "AWS_ACCOUNT_ID"
      value = data.aws_caller_identity.current.account_id
    }
    environment_variable {
      name  = "IMAGE_REPO_NAME"
      value = aws_ecr_repository.this.name
    }
    environment_variable {
      name  = "IMAGE_TAG"
      value = "${var.image_tag}-${local.source_hash}"
    }
    environment_variable {
      name  = "REPOSITORY_URI"
      value = aws_ecr_repository.this.repository_url
    }
    environment_variable {
      name  = "DOCKERFILE_PATH"
      value = var.dockerfile_path
    }
  }

  source {
    type      = "S3"
    location  = "${aws_s3_bucket.source.id}/${aws_s3_object.source_zip.key}"
    buildspec = <<EOF
version: 0.2

phases:
  pre_build:
    commands:
      - echo Logging in to Amazon ECR...
      - aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com
  build:
    commands:
      - echo Build started on `date`
      - echo Building the Docker image...
      - docker build -f $DOCKERFILE_PATH -t $REPOSITORY_URI:$IMAGE_TAG .
  post_build:
    commands:
      - echo Build completed on `date`
      - echo Pushing the Docker image...
      - docker push $REPOSITORY_URI:$IMAGE_TAG
EOF
  }
}

# 6. Trigger Build
resource "null_resource" "trigger_build" {
  triggers = {
    source_hash   = local.source_hash
    build_project = aws_codebuild_project.this.name
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<EOF
      set -e
      echo "Starting CodeBuild project: ${aws_codebuild_project.this.name}"
      BUILD_ID=$(aws codebuild start-build --project-name ${aws_codebuild_project.this.name} --region ${data.aws_region.current.region} --output text --query 'build.id')
      echo "Build started with ID: $BUILD_ID"

      while true; do
        STATUS=$(aws codebuild batch-get-builds --ids $BUILD_ID --region ${data.aws_region.current.region} --output text --query 'builds[0].buildStatus')
        echo "Current Build Status: $STATUS"

        if [ "$STATUS" == "SUCCEEDED" ]; then
          echo "Build completed successfully."
          exit 0
        elif [ "$STATUS" == "FAILED" ] || [ "$STATUS" == "FAULT" ] || [ "$STATUS" == "TIMED_OUT" ] || [ "$STATUS" == "STOPPED" ]; then
          echo "Build failed with status: $STATUS"
          exit 1
        fi

        sleep 10
      done
    EOF
  }
}
