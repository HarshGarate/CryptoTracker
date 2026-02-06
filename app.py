import boto3
from moto import mock_aws
import os

# Mock AWS Creds
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

from app_aws import application

@mock_aws
def run_local():
    print("--- STARTING LOCAL MOCK SERVER ---")
    db = boto3.resource('dynamodb', region_name='us-east-1')
    
    # Create Tables matching Production
    db.create_table(
        TableName='Users',
        KeySchema=[{'AttributeName': 'username', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'username', 'AttributeType': 'S'}],
        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
    )
    db.create_table(
        TableName='Watchlist',
        KeySchema=[{'AttributeName': 'user_id', 'KeyType': 'HASH'}, {'AttributeName': 'crypto_symbol', 'KeyType': 'RANGE'}],
        AttributeDefinitions=[{'AttributeName': 'user_id', 'AttributeType': 'S'}, {'AttributeName': 'crypto_symbol', 'AttributeType': 'S'}],
        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
    )
    db.create_table(
        TableName='MarketPrices',
        KeySchema=[{'AttributeName': 'symbol', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'symbol', 'AttributeType': 'S'}],
        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
    )
    
    application.run(debug=True, port=5000)

if __name__ == '__main__':
    run_local()