import boto3
import sqlite3
import gzip
import io
import time
import datetime
import sys
import os

# Fix path for direct execution
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import get_connection
from src.logger import log

class FlowLogIngester:
    def __init__(self, bucket_name="consolidated-flow-logs", region="us-gov-west-1"):
        self.bucket = bucket_name
        self.region = region
        self.s3 = boto3.client('s3', region_name=region)
        self.account_id = boto3.client('sts').get_caller_identity().get('Account')
        
    def get_latest_prefix(self):
        """Constructs the S3 prefix for TODAY to minimize scanning."""
        now = datetime.datetime.now(datetime.timezone.utc)
        # Format: AWSLogs/{account_id}/vpcflowlogs/{region}/{year}/{month}/{day}/
        prefix = f"AWSLogs/{self.account_id}/vpcflowlogs/{self.region}/{now.year}/{now.month:02d}/{now.day:02d}/"
        print(f"DEBUG: Searching prefix: s3://{self.bucket}/{prefix}")
        return prefix

    def process_logs(self):
        print("Starting S3 Flow Log Ingestion...")
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            prefix = self.get_latest_prefix()
            # List objects
            response = self.s3.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
            
            if 'Contents' not in response:
                print(f"WARNING: No logs found today in {self.bucket}/{prefix}")
                return

            # Sort by LastModified desc to get newest logs first
            objects = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)
            print(f"Found {len(objects)} files. Processing newest 5...")
            
            # Process last 5 files (approx last 10-20 mins)
            for obj in objects[:5]: 
                key = obj['Key']
                self.process_file(key, cursor)
                
            conn.commit()
            
        except Exception as e:
            print(f"Ingestion Loop Error: {e}")
        finally:
            conn.close()

    def process_file(self, key, cursor):
        try:
            print(f"Downloading {key}...")
            obj = self.s3.get_object(Bucket=self.bucket, Key=key)
            
            with gzip.GzipFile(fileobj=io.BytesIO(obj['Body'].read())) as gz:
                content = gz.read().decode('utf-8')
                
            lines = content.strip().split('\n')
            # Header is usually first line
            start_idx = 1 if lines[0].startswith('version') else 0
            
            records = 0
            for line in lines[start_idx:]:
                parts = line.split(' ')
                # Default v2 format: version account-id interface-id srcaddr dstaddr srcport dstport protocol packets bytes start end action log-status
                if len(parts) >= 13:
                    src_addr = parts[3]
                    dst_addr = parts[4]
                    bytes_transferred = int(parts[9])
                    start_time = int(parts[10])
                    action = parts[12] # ACCEPT/REJECT
                    
                    # Store significant traffic
                    if bytes_transferred > 0:
                        cursor.execute('''
                            INSERT OR IGNORE INTO vpc_flow_logs 
                            (record_id, interface_id, src_addr, dst_addr, bytes, action, timestamp)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            f"{src_addr}-{dst_addr}-{start_time}", # Composite ID to dedupe
                            parts[2],
                            src_addr,
                            dst_addr,
                            bytes_transferred,
                            action,
                            start_time
                        ))
                        records += 1
            print(f" > Parsed {records} records.")
            
        except Exception as e:
            print(f"Error processing file {key}: {e}")

if __name__ == "__main__":
    # Single run for debug
    ingester = FlowLogIngester()
    ingester.process_logs()
