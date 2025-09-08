Terraform hints:

- Create S3 bucket for attachments and policy docs
- Create IAM role for Lambda with permissions: s3:GetObject, textract:StartDocumentTextDetection, textract:GetDocumentTextDetection
- Bedrock permissions require appropriate AWS managed policies; check AWS docs for Bedrock access
- Create VPC endpoints for S3, Textract if you require private networking
