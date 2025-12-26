import boto3
from botocore.exceptions import NoCredentialsError

def debug_log_groups():
    print("--- Listing CloudWatch Log Groups ---")
    try:
        logs = boto3.client('logs', region_name='us-gov-west-1')
        paginator = logs.get_paginator('describe_log_groups')
        
        count = 0
        for page in paginator.paginate():
            for group in page['logGroups']:
                print(f"Name: {group['logGroupName']}")
                print(f" - Stored Bytes: {group.get('storedBytes', 0)}")
                count += 1
                if count > 50:
                    print("... (Stopping after 50 groups)")
                    return
        
        if count == 0:
            print("No Log Groups found in this region.")
            
    except NoCredentialsError:
        print("Error: No AWS Credentials found.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_log_groups()
