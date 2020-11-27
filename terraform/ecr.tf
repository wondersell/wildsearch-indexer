resource "aws_ecr_repository" "wdf" {
  name = local.aws_ecr_repository_name
}

resource "aws_ecr_lifecycle_policy" "max_images" {
  repository = aws_ecr_repository.wdf.name

  policy = <<EOF
{
    "rules": [
        {
            "rulePriority": 1,
            "description": "Keeping only 3 youngest images; expires the old ones",
            "selection": {
                "tagStatus": "any",
                "countType": "imageCountMoreThan",
                "countNumber": 3
            },
            "action": {
                "type": "expire"
            }
        }
    ]
}
EOF
}