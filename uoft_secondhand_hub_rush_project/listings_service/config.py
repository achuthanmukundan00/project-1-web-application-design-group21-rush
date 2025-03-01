import os
from dotenv import load_dotenv

load_dotenv()

# AWS S3 configuration
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_S3_LISTINGS_BUCKET_NAME = os.getenv('AWS_S3_LISTINGS_BUCKET_NAME')
AWS_DB_LISTINGS_TABLE_NAME = os.getenv('AWS_DB_LISTINGS_TABLE_NAME')
AWS_S3_REGION = os.getenv('AWS_S3_REGION', 'us-east-2') 
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
