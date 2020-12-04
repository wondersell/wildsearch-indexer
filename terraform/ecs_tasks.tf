#
# Set of ECS resources for Celery
#
resource "aws_cloudwatch_log_group" "celery" {
  name              = local.aws_ecs_service_celery_name
  retention_in_days = 5
}

data "template_file" "container_image_celery" {
  template   = file("aws-ecs-task-definitions/celery.json")
  depends_on = [aws_elasticache_replication_group.default]
  vars = {
    service_name      = local.aws_ecs_service_celery_name
    image_name        = aws_ecr_repository.wdf.repository_url
    aws_region        = var.aws_region
    log_stream_prefix = "celery_"
    command           = "celery -A app worker --concurrency=4 -Ofair"
    cpu               = 680
    memory            = 315

    # Secrets
    database_url  = local.secrets_database_url_arn
    sh_apikey     = local.secrets_sh_apikey_arn
    sh_project_id = local.secrets_sh_project_id_arn
    django_secret = local.django_secret_arn

    # Envs
    redis_url               = "redis://${aws_elasticache_replication_group.default.primary_endpoint_address}:${aws_elasticache_replication_group.default.port}"
    indexer_get_chunk_size  = local.indexer_get_chunk_size
    indexer_save_chunk_size = local.indexer_save_chunk_size
  }
}

resource "aws_ecs_task_definition" "celery" {
  container_definitions = data.template_file.container_image_celery.rendered
  family                = local.aws_ecs_task_celery_name
  execution_role_arn    = aws_iam_role.ecs_task_execution_role.arn
  network_mode          = "bridge"
}

#
# Set of ECS resources for Flower
#
resource "aws_cloudwatch_log_group" "flower" {
  name              = local.aws_ecs_service_flower_name
  retention_in_days = 5
}

data "template_file" "container_image_flower" {
  template   = file("aws-ecs-task-definitions/flower.json")
  depends_on = [aws_elasticache_replication_group.default]
  vars = {
    service_name      = local.aws_ecs_service_flower_name
    image_name        = aws_ecr_repository.wdf.repository_url
    aws_region        = var.aws_region
    log_stream_prefix = "flower_"
    command           = "flower -A app --port=80"
    cpu               = 680
    memory            = 315

    # Secrets
    database_url  = local.secrets_database_url_arn
    sh_apikey     = local.secrets_sh_apikey_arn
    sh_project_id = local.secrets_sh_project_id_arn
    django_secret = local.django_secret_arn

    # Envs
    redis_url               = "redis://${aws_elasticache_replication_group.default.primary_endpoint_address}:${aws_elasticache_replication_group.default.port}"
    indexer_get_chunk_size  = local.indexer_get_chunk_size
    indexer_save_chunk_size = local.indexer_save_chunk_size
  }
}

resource "aws_ecs_task_definition" "flower" {
  container_definitions = data.template_file.container_image_flower.rendered
  family                = local.aws_ecs_task_flower_name
  execution_role_arn    = aws_iam_role.ecs_task_execution_role.arn
  network_mode          = "bridge"
}

#
# Set of ECS resources for Console
#
resource "aws_cloudwatch_log_group" "console" {
  name              = local.aws_ecs_service_console_name
  retention_in_days = 5
}

data "template_file" "container_image_console" {
  template   = file("aws-ecs-task-definitions/console.json")
  depends_on = [aws_elasticache_replication_group.default]
  vars = {
    service_name      = local.aws_ecs_service_console_name
    image_name        = aws_ecr_repository.wdf.repository_url
    aws_region        = var.aws_region
    log_stream_prefix = "console_"
    cpu               = 680
    memory            = 315

    # Secrets
    database_url  = local.secrets_database_url_arn
    sh_apikey     = local.secrets_sh_apikey_arn
    sh_project_id = local.secrets_sh_project_id_arn
    django_secret = local.django_secret_arn

    # Envs
    redis_url               = "redis://${aws_elasticache_replication_group.default.primary_endpoint_address}:${aws_elasticache_replication_group.default.port}"
    indexer_get_chunk_size  = local.indexer_get_chunk_size
    indexer_save_chunk_size = local.indexer_save_chunk_size
  }
}

resource "aws_ecs_task_definition" "console" {
  container_definitions = data.template_file.container_image_console.rendered
  family                = local.aws_ecs_task_console_name
  execution_role_arn    = aws_iam_role.ecs_task_execution_role.arn
  network_mode          = "bridge"
}
