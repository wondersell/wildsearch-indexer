data "aws_iam_policy_document" "instance-assume-role-policy" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com", "ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "instance_role" {
  name               = local.aws_iam_instance_role
  assume_role_policy = data.aws_iam_policy_document.instance-assume-role-policy.json
}

resource "aws_iam_role" "ecs_task_execution_role" {
  name               = local.aws_iam_task_execution_role
  assume_role_policy = data.aws_iam_policy_document.instance-assume-role-policy.json
}

resource "aws_iam_role_policy" "password_policy_secretsmanager" {
  name = local.aws_iam_policy_secrets_name
  role = aws_iam_role.ecs_task_execution_role.id

  policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Effect": "Allow",
      "Resource": [
        "${local.secrets_database_url_arn}",
        "${local.secrets_sh_apikey_arn}",
        "${local.secrets_sh_project_id_arn}",
        "${local.django_secret_arn}"
      ]
    }
  ]
}
EOF
}

resource "aws_iam_role_policy_attachment" "ecs_iam_policy_attachment" {
  role       = aws_iam_role.instance_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
  role       = aws_iam_role.ecs_task_execution_role.name
}

resource "aws_iam_instance_profile" "instance_profile" {
  name = local.aws_iam_instance_profile
  path = "/"
  role = aws_iam_role.instance_role.name
}

module "vpc" {
  source = "terraform-aws-modules/vpc/aws"

  name = local.aws_ecs_stack_name
  cidr = local.vpc_cidr

  azs                 = local.availability_zones
  private_subnets     = local.private_subnets
  public_subnets      = local.public_subnets
  elasticache_subnets = local.elasticache_subnets

  enable_nat_gateway = true
}

data "aws_ami" "latest-ecs" {
  most_recent = true
  owners = ["amazon", "aws-marketplace"]

  filter {
    name   = "name"
    values = ["amzn2-ami-ecs-*"]
  }
}

resource "aws_cloudformation_stack" "stack" {
  name = local.aws_ecs_stack_name

  template_body = file("aws-templates/aws-ecs-stack.yml")
  depends_on    = [aws_iam_instance_profile.instance_profile, module.vpc]

  parameters = {
    VpcId = module.vpc.vpc_id

    AsgMaxSize              = local.ecs_instances_count
    AutoAssignPublicIp      = "INHERIT"
    ConfigureDataVolume     = false
    ConfigureRootVolume     = true
    DeviceName              = "/dev/xvdcz"
    EbsVolumeSize           = 22
    EbsVolumeType           = "gp2"
    EcsAmiId                = data.aws_ami.latest-ecs.id
    EcsClusterName          = local.aws_ecs_cluster_name
    EcsInstanceType         = local.ecs_instance_size
    IamRoleInstanceProfile  = aws_iam_instance_profile.instance_profile.arn
    IsWindows               = false
    KeyName                 = local.ssh_key_name
    RootDeviceName          = "/dev/xvda"
    RootEbsVolumeSize       = 30
    SecurityIngressCidrIp   = "0.0.0.0/0"
    SecurityIngressFromPort = 1
    SecurityIngressToPort   = 65535
    SpotAllocationStrategy  = "diversified"
    SubnetIds               = join(",", module.vpc.public_subnets)
    UseSpot                 = false
    UserData                = "#!/bin/bash\necho ECS_CLUSTER=${local.aws_ecs_cluster_name} >> /etc/ecs/ecs.config;echo ECS_BACKEND_HOST= >> /etc/ecs/ecs.config;"
  }
}