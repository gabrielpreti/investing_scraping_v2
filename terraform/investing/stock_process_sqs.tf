#Queue
resource "aws_sqs_queue" "stock_process_queue" {
  name = "stock_process_queue"
  receive_wait_time_seconds = 20
  visibility_timeout_seconds = 180
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.stock_process_queue_dlq.arn
    maxReceiveCount    = 4
  })
  tags = {
    project = "investing_scrapping_v2"
  }
}
output "stock_process_queue_id" {
  value = aws_sqs_queue.stock_process_queue.id
}
output "stock_process_queue_arn" {
  value = aws_sqs_queue.stock_process_queue.arn
}


#Dlq
resource "aws_sqs_queue" "stock_process_queue_dlq" {
  name = "stock_process_queue_dlq"
  tags = {
    project = "investing_scrapping_v2"
  }
}
output "stock_process_queue_dlq_id" {
  value = aws_sqs_queue.stock_process_queue_dlq.id
}
output "stock_process_queue_dlq_arn" {
  value = aws_sqs_queue.stock_process_queue_dlq.arn
}


#Iam policy
resource "aws_iam_policy" "stock_process_queue_policy" {
  name        = "stock_process_queue_policy"
  path        = "/"
  description = "IAM policy for stock process SQS queue"
  policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sqs:*",
      "Resource": "${aws_sqs_queue.stock_process_queue.arn}",
      "Effect": "Allow"
    }
  ]
}
EOF
}
resource "aws_iam_role_policy_attachment" "stock_process_queue_policy_role_attachment" {
  role       = aws_iam_role.lambda_iam_role.name
  policy_arn = aws_iam_policy.stock_process_queue_policy.arn
}