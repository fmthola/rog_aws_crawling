import time
import json
import datetime
from src.database import get_connection, init_db
from src.aws_client import AWSClient
from src.logger import log

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))

def populate():
    print("--- STARTING HISTORICAL DATA POPULATION ---")
    print("This may take a moment...")
    
    init_db()
    aws = AWSClient(region="us-gov-west-1", mock_mode=False)
    conn = get_connection()
    c = conn.cursor()
    
    # 1. CloudTrail
    print("Fetching CloudTrail Logs (Last 24h)...")
    events = aws.fetch_cloudtrail_events(hours=24)
    print(f" > Found {len(events)} events.")
    
    for e in events:
        try:
            # Extract Resource ID if possible
            res_id = "N/A"
            if e.get('Resources'):
                res_id = e['Resources'][0].get('ResourceName', 'N/A')
                
            c.execute('''
                INSERT OR REPLACE INTO cloudtrail_logs (event_id, event_name, event_time, resource_id, username, raw_data)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                e['EventId'], 
                e['EventName'], 
                e['EventTime'].timestamp(), 
                res_id, 
                e.get('Username', 'Unknown'),
                json.dumps(e, default=json_serial) # Use custom serializer
            ))
        except Exception as err:
            log.error(f"Error inserting trail: {err}")

    # 2. VPC Flow Logs
    print("Fetching VPC Flow Logs (Last 24h)...")
    flow_logs = aws.fetch_vpc_flow_logs(hours=24)
    print(f" > Found {len(flow_logs)} records.")
    
    for f in flow_logs:
        try:
            # Basic parsing of standard flow log format: version account-id interface-id srcaddr dstaddr ...
            # Message is space separated
            parts = f['message'].split(' ')
            if len(parts) >= 10:
                c.execute('''
                    INSERT OR REPLACE INTO vpc_flow_logs (record_id, interface_id, src_addr, dst_addr, bytes, action, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    f['eventId'],
                    parts[2], # interface-id
                    parts[3], # srcaddr
                    parts[4], # dstaddr
                    int(parts[9]) if parts[9].isdigit() else 0, # bytes
                    parts[12] if len(parts) > 12 else 'UNKNOWN', # action (ACCEPT/REJECT)
                    f['timestamp'] / 1000.0
                ))
        except Exception as err:
            pass # Skip malformed logs

    conn.commit()
    conn.close()
    print("--- POPULATION COMPLETE ---")

if __name__ == "__main__":
    populate()
