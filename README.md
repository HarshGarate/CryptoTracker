# AWS Scalable Cryptocurrency Tracker

## Deployment Instructions
1. **AWS Setup**:
   - Go to DynamoDB in us-east-1 and create 3 tables:
     - `Users`: Partition Key = `username` (String)
     - `Watchlist`: Partition Key = `user_id` (String), Sort Key = `crypto_symbol` (String)
     - `MarketPrices`: Partition Key = `symbol` (String)
   - Go to IAM and create a Role with `AmazonDynamoDBFullAccess`.

2. **Deploy**:
   - Zip these files: `app_aws.py`, `requirements.txt`, `static/`, `templates/`.
   - Upload to Elastic Beanstalk (Python 3.11+).
   - In Configuration -> Service Access, select the IAM Role you created.
   - **Important**: In Elastic Beanstalk Configuration -> Software, set "WSGI Path" to `app_aws:application`.