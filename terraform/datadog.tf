# Based on https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/SubscriptionFilters.html#FirehoseExample

resource "aws_s3_bucket" "clowdwatch_logs" {
  bucket = "clowdwatch-logs-backup"
  acl    = "private"
}

data "aws_iam_policy_document" "trust_policy_for_firehose" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["firehose.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "firehose" {
  name               = "firehose"
  assume_role_policy = data.aws_iam_policy_document.trust_policy_for_firehose.json
}

resource "aws_iam_role_policy" "permissions_for_firehose" {
  name = "permissions-for-firehose"
  role = aws_iam_role.firehose.id

  policy = <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "",
            "Effect": "Allow",
            "Action": [
                "glue:GetTable",
                "glue:GetTableVersion",
                "glue:GetTableVersions"
            ],
            "Resource": [
                "arn:aws:glue:${var.aws_region}:${var.aws_account_id}:catalog",
                "arn:aws:glue:${var.aws_region}:${var.aws_account_id}:database/%FIREHOSE_POLICY_TEMPLATE_PLACEHOLDER%",
                "arn:aws:glue:${var.aws_region}:${var.aws_account_id}:table/%FIREHOSE_POLICY_TEMPLATE_PLACEHOLDER%/%FIREHOSE_POLICY_TEMPLATE_PLACEHOLDER%"
            ]
        },
        {
            "Sid": "",
            "Effect": "Allow",
            "Action": [
                "s3:AbortMultipartUpload",
                "s3:GetBucketLocation",
                "s3:GetObject",
                "s3:ListBucket",
                "s3:ListBucketMultipartUploads",
                "s3:PutObject"
            ],
            "Resource": [
                "${aws_s3_bucket.clowdwatch_logs.arn}",
                "${aws_s3_bucket.clowdwatch_logs.arn}/*"
            ]
        },
        {
            "Sid": "",
            "Effect": "Allow",
            "Action": [
                "lambda:InvokeFunction",
                "lambda:GetFunctionConfiguration"
            ],
            "Resource": "arn:aws:lambda:${var.aws_region}:${var.aws_account_id}:function:%FIREHOSE_POLICY_TEMPLATE_PLACEHOLDER%"
        },
        {
            "Effect": "Allow",
            "Action": [
                "kms:GenerateDataKey",
                "kms:Decrypt"
            ],
            "Resource": [
                "arn:aws:kms:${var.aws_region}:${var.aws_account_id}:key/%FIREHOSE_POLICY_TEMPLATE_PLACEHOLDER%"
            ],
            "Condition": {
                "StringEquals": {
                    "kms:ViaService": "s3.${var.aws_region}.amazonaws.com"
                },
                "StringLike": {
                    "kms:EncryptionContext:aws:s3:arn": [
                        "arn:aws:s3:::%FIREHOSE_POLICY_TEMPLATE_PLACEHOLDER%/*"
                    ]
                }
            }
        },
        {
            "Sid": "",
            "Effect": "Allow",
            "Action": [
                "logs:PutLogEvents"
            ],
            "Resource": [
                "arn:aws:logs:${var.aws_region}:${var.aws_account_id}:log-group:/aws/kinesisfirehose/DatadogCWLogsforwarder:log-stream:*"
            ]
        },
        {
            "Sid": "",
            "Effect": "Allow",
            "Action": [
                "kinesis:DescribeStream",
                "kinesis:GetShardIterator",
                "kinesis:GetRecords",
                "kinesis:ListShards"
            ],
            "Resource": "arn:aws:kinesis:${var.aws_region}:${var.aws_account_id}:stream/%FIREHOSE_POLICY_TEMPLATE_PLACEHOLDER%"
        },
        {
            "Effect": "Allow",
            "Action": [
                "kms:Decrypt"
            ],
            "Resource": [
                "arn:aws:kms:${var.aws_region}:${var.aws_account_id}:key/%FIREHOSE_POLICY_TEMPLATE_PLACEHOLDER%"
            ],
            "Condition": {
                "StringEquals": {
                    "kms:ViaService": "kinesis.${var.aws_region}.amazonaws.com"
                },
                "StringLike": {
                    "kms:EncryptionContext:aws:kinesis:arn": "arn:aws:kinesis:${var.aws_region}:${var.aws_account_id}:stream/%FIREHOSE_POLICY_TEMPLATE_PLACEHOLDER%"
                }
            }
        }
    ]
}
EOF
}

resource "aws_kinesis_firehose_delivery_stream" "datadog_log_forwarder" {
  name        = "datadog-log-forwarder"
  destination = "http_endpoint"

  s3_configuration {
    role_arn   = aws_iam_role.firehose.arn
    bucket_arn = aws_s3_bucket.clowdwatch_logs.arn
  }

  http_endpoint_configuration {
    url                = "https://aws-kinesis-http-intake.logs.datadoghq.eu/v1/input"
    name               = "Datadog"
    access_key         = var.datadog_api_key
    buffering_size     = 1
    buffering_interval = 60
    role_arn           = aws_iam_role.firehose.arn
    s3_backup_mode     = "FailedDataOnly"

    request_configuration {
      content_encoding = "GZIP"
    }
  }
}

data "aws_iam_policy_document" "trust_policy_for_cwl" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["logs.${var.aws_region}.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "cwl_to_kinesis_firehose" {
  name               = "cwl-to-kinesis-firehose"
  assume_role_policy = data.aws_iam_policy_document.trust_policy_for_cwl.json
}

resource "aws_iam_role_policy" "permissions_for_cwl" {
  role   = aws_iam_role.cwl_to_kinesis_firehose.id
  policy = <<EOF
{
    "Statement":[
      {
        "Effect":"Allow",
        "Action":["firehose:*"],
        "Resource":["arn:aws:firehose:${var.aws_region}:${var.aws_account_id}:*"]
      }
    ]
}
EOF
}

resource "aws_cloudwatch_log_subscription_filter" "filter_celery" {
  name = "filter-celery"

  destination_arn = aws_kinesis_firehose_delivery_stream.datadog_log_forwarder.arn
  role_arn        = aws_iam_role.cwl_to_kinesis_firehose.arn
  filter_pattern  = ""
  log_group_name  = aws_cloudwatch_log_group.celery.name
}

resource "aws_cloudwatch_log_subscription_filter" "filter_flower" {
  name = "filter-celery"

  destination_arn = aws_kinesis_firehose_delivery_stream.datadog_log_forwarder.arn
  role_arn        = aws_iam_role.cwl_to_kinesis_firehose.arn
  filter_pattern  = ""
  log_group_name  = aws_cloudwatch_log_group.flower.name
}

resource "aws_cloudwatch_log_subscription_filter" "filter_console" {
  name = "filter-celery"

  destination_arn = aws_kinesis_firehose_delivery_stream.datadog_log_forwarder.arn
  role_arn        = aws_iam_role.cwl_to_kinesis_firehose.arn
  filter_pattern  = ""
  log_group_name  = aws_cloudwatch_log_group.console.name
}