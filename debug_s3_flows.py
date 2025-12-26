import boto3
from botocore.exceptions import ClientError

def check_s3_flow_logs():
    print("--- Checking S3 for VPC Flow Logs ---")
    s3 = boto3.client('s3', region_name='us-gov-west-1')
    
    try:
        response = s3.list_buckets()
        buckets = response['Buckets']
        print(f"Found {len(buckets)} buckets.")
        
        candidates = []
        for b in buckets:
            name = b['Name']
            if 'flow' in name.lower() or 'vpc' in name.lower() or 'log' in name.lower():
                candidates.append(name)
        
        if not candidates:
            print("No obvious flow-log buckets found.")
            # Check first 5 buckets anyway just in case
            candidates = [b['Name'] for b in buckets[:5]]
            
        for bucket in candidates:
            print(f"Checking bucket: {bucket}...")
            try:
                # Look for standard prefix
                objs = s3.list_objects_v2(Bucket=bucket, Prefix="AWSLogs", MaxKeys=5)
                if 'Contents' in objs:
                    print(f" > Found 'AWSLogs' in {bucket}. Checking for vpcflowlogs...")
                    for obj in objs['Contents']:
                        if 'vpcflowlogs' in obj['Key']:
                            print(f" >> CONFIRMED: VPC Flow Logs found in {bucket}!")
                            return
            except ClientError as e:
                print(f" > Access Denied/Error: {e}")
                
        print("No VPC Flow Logs found in checked buckets.")

    except Exception as e:
        print(f"Error listing buckets: {e}")

if __name__ == "__main__":
    check_s3_flow_logs()
