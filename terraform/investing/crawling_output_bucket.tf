resource "aws_s3_bucket" "stock_crawling_output" {
  bucket = "preti-stock-crawling-output"
  acl = "private"
  versioning {
    enabled = false
  }
  tags = {
    project = "investing_scrapping_v2"
  }
}
output "stock_crawling_output_id" {
  value = aws_s3_bucket.stock_crawling_output.id
}
output "stock_crawling_output_arn" {
  value = aws_s3_bucket.stock_crawling_output.arn
}

resource "aws_iam_policy" "stock_crawling_output_write_policy" {
  name        = "stock_crawling_output_write_policy"
  path        = "/"
  description = "IAM policy for logging from a lambda"
  policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:PutObjectLegalHold",
        "s3:PutObjectRetention",
        "s3:PutObjectTagging",
        "s3:PutObjectVersionAcl",
        "s3:PutObjectVersionTagging"
      ],
      "Resource": "${aws_s3_bucket.stock_crawling_output.arn}/*",
      "Effect": "Allow"
    }
  ]
}
EOF
}
resource "aws_iam_role_policy_attachment" "stock_crawling_output_write_policy_role_attachment" {
  role       = aws_iam_role.lambda_iam_role.name
  policy_arn = aws_iam_policy.stock_crawling_output_write_policy.arn
}