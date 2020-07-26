data "aws_ami" "ubuntu" {
  most_recent = true

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-trusty-14.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  owners = ["099720109477"] # Canonical
}

resource "aws_security_group" "ssh_access" {
  vpc_id = aws_vpc.main_vpc.id
  ingress {
    from_port = 22
    to_port = 22
    protocol = "tcp"
    cidr_blocks = ["177.68.248.159/32"]
  }
}

resource "aws_instance" "ec2_instance" {
  ami = data.aws_ami.ubuntu.id
  instance_type = "t1.micro"
  key_name = "investing_scrapping"
  subnet_id = aws_subnet.main_subnet.id
  vpc_security_group_ids = [aws_security_group.ssh_access.id]
  associate_public_ip_address = true
}

output "ec2_public_ip" {
  value = aws_instance.ec2_instance.public_ip
}