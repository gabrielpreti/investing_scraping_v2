variable "vpc_cidr" {
  type = string
}

variable "subnet_cidr" {
  type = string
}

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "main_vpc" {
  cidr_block = var.vpc_cidr
  tags = {
    Name = "main_vpc"
    Description = "main vpc for personal projects"
  }
}

resource "aws_internet_gateway" "main_vpc_internet_gateway" {
  vpc_id = aws_vpc.main_vpc.id
}

resource "aws_subnet" "main_subnet" {
  cidr_block = var.subnet_cidr
  vpc_id = aws_vpc.main_vpc.id
  map_public_ip_on_launch = true
  availability_zone = data.aws_availability_zones.available.names[0]
}

resource "aws_network_acl" "main_subnet_nacl" {
  vpc_id = aws_vpc.main_vpc.id
  subnet_ids = [aws_subnet.main_subnet.id]
  ingress {
    rule_no = 100
    action = "allow"
    protocol = "tcp"
    from_port = 22
    to_port = 22
    cidr_block = "177.68.248.159/32"
  }

  ingress {
    rule_no = 101
    action = "allow"
    protocol = "tcp"
    from_port = 1024
    to_port = 65535
    cidr_block = "0.0.0.0/0"
  }

  ingress {
    rule_no = 102
    action = "allow"
    protocol = "tcp"
    from_port = 2375
    to_port = 2375
    cidr_block = "177.68.248.159/32"
  }

  ingress {
    rule_no = 103
    action = "allow"
    protocol = "tcp"
    from_port = 27017
    to_port = 27017
    cidr_block = "177.68.248.159/32"
  }

  egress {
    rule_no = 200
    action = "allow"
    protocol = "tcp"
    from_port = 1024
    to_port = 65535
    cidr_block = "177.68.248.159/32"
  }

  egress {
    rule_no = 201
    action = "allow"
    protocol = "tcp"
    from_port = 80
    to_port = 80
    cidr_block = "0.0.0.0/0"
  }

  egress {
    rule_no = 202
    action = "allow"
    protocol = "tcp"
    from_port = 443
    to_port = 443
    cidr_block = "0.0.0.0/0"
  }
}

resource "aws_route_table" "route_table" {
  vpc_id = aws_vpc.main_vpc.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main_vpc_internet_gateway.id
  }
}

resource "aws_route_table_association" "route_table_association" {
  route_table_id = aws_route_table.route_table.id
  subnet_id = aws_subnet.main_subnet.id
}
output "vpc_id" {
  value = aws_vpc.main_vpc.id
}
output "vpc_arn" {
  value = aws_vpc.main_vpc.arn
}
output "vpc_cidr" {
  value = aws_vpc.main_vpc.cidr_block
}