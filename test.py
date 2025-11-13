import boto3, os, io

from dotenv import load_dotenv


# Load the .env file explicitly
load_dotenv(dotenv_path=".env")

# Print check — should not be None
print("AWS_ACCESS_KEY_ID:", os.getenv("AWS_ACCESS_KEY_ID"))
print("AWS_SECRET_ACCESS_KEY:", os.getenv("AWS_SECRET_ACCESS_KEY")[:4] + "..." if os.getenv("AWS_SECRET_ACCESS_KEY") else None)

bucket = "finallcpreports"
case_id = "4848"
key = "4848/Output/20251023152059-4848-RedactedReport.pdf"
s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION", "us-east-1"),
)


pdf = io.BytesIO()
s3.download_fileobj(bucket, key, pdf)
print("✅ Download success:", len(pdf.getvalue()), "bytes")