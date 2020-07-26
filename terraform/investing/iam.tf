resource "aws_iam_role" "lambda_iam_role" {
  name = "iam_role_for_lambda"
  description = "IAM role used for the lambda functions in the project"
  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Effect": "Allow",
      "Sid": ""
    }
  ]
}
EOF
}
output "lambda_iam_arn"{
  value = aws_iam_role.lambda_iam_role.arn
}
output "lambda_iam_id"{
  value = aws_iam_role.lambda_iam_role.id
}
output "lambda_iam_name"{
  value = aws_iam_role.lambda_iam_role.name
}


resource "aws_iam_policy" "lambda_logging_policy" {
  name        = "lambda_logging_policy"
  path        = "/"
  description = "IAM policy that allows logging to CloudWatch"
  policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "logs:*",
      "Resource": "*",
      "Effect": "Allow"
    }
  ]
}
EOF
}
resource "aws_iam_role_policy_attachment" "lambda_logging_policy_role_attachment" {
  role       = aws_iam_role.lambda_iam_role.name
  policy_arn = aws_iam_policy.lambda_logging_policy.arn
}
