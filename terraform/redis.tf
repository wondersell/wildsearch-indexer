resource "aws_security_group" "redis" {
  vpc_id = module.vpc.vpc_id
  name   = local.aws_redis_sg_name
}

resource "aws_security_group_rule" "redis_egress" {
  description       = "Allow all egress traffic"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = join("", aws_security_group.redis.*.id)
  type              = "egress"
}

resource "aws_security_group_rule" "redis_ingress" {
  description       = "Allow all ingress traffic to redis port"
  from_port         = 6379
  to_port           = 6379
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = join("", aws_security_group.redis.*.id)
  type              = "ingress"
}

resource "aws_elasticache_parameter_group" "default" {
  name   = local.aws_redis_parameter_group_name
  family = "redis${local.aws_redis_engine_version}"
}

resource "aws_elasticache_replication_group" "default" {
  auth_token                    = null
  replication_group_id          = local.aws_redis_replication_group
  replication_group_description = "Redis replication group"
  node_type                     = "cache.t3.small"
  number_cache_clusters         = 1
  port                          = 6379
  parameter_group_name          = join("", aws_elasticache_parameter_group.default.*.name)
  availability_zones            = null
  automatic_failover_enabled    = false
  subnet_group_name             = module.vpc.elasticache_subnet_group_name
  security_group_ids            = [join("", aws_security_group.redis.*.id)]
  maintenance_window            = "wed:03:00-wed:04:00"
  notification_topic_arn        = ""
  engine_version                = local.aws_redis_engine_version
  at_rest_encryption_enabled    = false
  transit_encryption_enabled    = false
  kms_key_id                    = null
  snapshot_window               = "06:30-07:30"
  snapshot_retention_limit      = 0
  apply_immediately             = true
}