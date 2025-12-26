import boto3
from botocore.exceptions import ClientError

def check_vpcs():
    print("--- Checking VPC Flow Log Configuration ---")
    ec2 = boto3.client('ec2', region_name='us-gov-west-1')
    
    try:
        # 1. Get all VPCs
        vpcs = ec2.describe_vpcs()['Vpcs']
        print(f"Found {len(vpcs)} VPCs.\n")
        
        for vpc in vpcs:
            vpc_id = vpc['VpcId']
            is_default = vpc.get('IsDefault', False)
            tags = {t['Key']: t['Value'] for t in vpc.get('Tags', [])}
            name = tags.get('Name', 'Unnamed')
            
            print(f"VPC: {vpc_id} ({name}){' [DEFAULT]' if is_default else ''}")
            
            # 2. Check for Flow Logs attached to this VPC
            flow_logs = ec2.describe_flow_logs(
                Filters=[{'Name': 'resource-id', 'Values': [vpc_id]}]
            )['FlowLogs']
            
            if not flow_logs:
                print("  > STATUS: [ DISABLED ] - No flow logs configured for this VPC.")
            else:
                for fl in flow_logs:
                    fl_id = fl['FlowLogId']
                    dest_type = fl['LogDestinationType'] # cloud-watch-logs or s3
                    status = fl['FlowLogStatus']
                    dest = fl.get('LogGroupName') or fl.get('LogDestination')
                    
                    print(f"  > STATUS: [ ENABLED ] ({status})")
                    print(f"    - ID: {fl_id}")
                    print(f"    - Destination Type: {dest_type}")
                    print(f"    - Destination: {dest}")
            print("-" * 40)

    except Exception as e:
        print(f"Error checking VPCs: {e}")

if __name__ == "__main__":
    check_vpcs()
