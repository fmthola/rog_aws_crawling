import threading
import time
import json
from src.database import get_connection, init_db
from src.aws_client import AWSClient
from src.logger import log

class DataManager(threading.Thread):
    def __init__(self, region="us-gov-west-1", interval=30): 
        super().__init__()
        self.region = region
        self.interval = interval
        self.running = True
        self.daemon = True 
        self.aws = AWSClient(region=region, mock_mode=False) 
        self.last_sync_time = 0
        self.status = "Initializing..."
        self.detailed_status = "Starting..." # New detailed status

    def run(self):
        log.info("DataManager started (Real Mode).")
        init_db() 
        
        while self.running:
            try:
                self.status = "SYNCING..."
                self.detailed_status = "Connecting to AWS..."
                start_t = time.time()
                
                self.sync_resources()
                
                elapsed = time.time() - start_t
                self.last_sync_time = time.time()
                self.status = f"SYNCED ({elapsed:.1f}s)"
                log.info(f"Sync cycle completed in {elapsed:.2f}s")
            except Exception as e:
                log.error(f"Error in DataManager sync loop: {e}")
                self.status = "SYNC ERROR"
                self.detailed_status = f"Error: {str(e)[:20]}..."
            
            # Wait for interval
            for i in range(self.interval):
                if not self.running: break
                time.sleep(1)

    def stop(self):
        self.running = False

    def sync_resources(self):
        """Fetches EC2, Lambda, ECR, ECS, EKS, Secrets and RDS data."""
        self.detailed_status = "Scanning Active Workloads..."
        active_images = self.aws.get_active_images()
        
        self.detailed_status = "Fetching EC2 Instances..."
        ec2_instances = self.aws.list_ec2_instances()
        
        # ... (rest of fetches)
        lambda_functions = self.aws.list_lambda_functions()
        ecr_repos = self.aws.list_ecr_repos()
        ecs_clusters = self.aws.list_ecs_clusters()
        eks_clusters = self.aws.list_eks_clusters()
        rds_instances = self.aws.list_rds_instances()
        secrets = self.aws.list_secrets()
        
        all_resources = ec2_instances + lambda_functions + ecr_repos + ecs_clusters + eks_clusters + secrets + rds_instances
        
        self.detailed_status = f"Updating Cache ({len(all_resources)} items)..."
        conn = get_connection()
        cursor = conn.cursor()

        timestamp = time.time()
        updates_count = 0

        for res in all_resources:
            # Upsert into resources
            rname = res.get('name', res['id'])
            details_json = json.dumps(res)
            
            cursor.execute('''
                INSERT OR REPLACE INTO resources (id, name, type, state, region, last_updated, details)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (res['id'], rname, res['type'], res['state'], self.region, timestamp, details_json))

            # Metrics
            metrics = {'cpu_usage': 0, 'network_in': 0, 'network_out': 0}
            if res['type'] == 'ec2' and res['state'] == 'running':
                 metrics = self.aws.get_instance_metrics(res['id'])
            
            # ECR Usage Logic
            if res['type'] == 'ecr':
                repo_uri = res.get('uri', '')
                # Check if this repo URI is part of any active image string
                is_active = any(repo_uri in img for img in active_images)
                if is_active:
                    metrics['network_in'] = 1 # Mark as "In Use"
            
            # --- UNIFIED SECURITY LOGIC ---
            sec_issues = 0
            
            # 1. EC2 Security
            if res['type'] == 'ec2':
                # Check Tags
                if not res.get('tags'): sec_issues += 1
                # Check Public IP (Risk factor)
                if res.get('public_ip'): sec_issues += 1 
                # (Future: Check Inspector findings if available in details)

            # 2. ECR Security
            elif res['type'] == 'ecr':
                # Findings Check (Persistent from Deep Scans)
                cursor.execute("SELECT security_issues_count FROM metrics WHERE resource_id=?", (res['id'],))
                existing = cursor.fetchone()
                if existing and existing[0] > 0: sec_issues = max(sec_issues, existing[0])

            # 3. Lambda Security
            elif res['type'] == 'lambda':
                runtime = res.get('runtime', '')
                # Flag deprecated runtimes
                if 'python3.7' in runtime or 'python3.8' in runtime or 'nodejs12' in runtime:
                    sec_issues += 1
                # Check env vars encryption (Simulated check)
                if not res.get('kms_key_arn'): 
                    sec_issues += 1 # Default keys are less secure than CMK

            # 4. RDS Security
            elif res['type'] == 'rds':
                if not res.get('encrypted', False):
                    sec_issues += 1 # Unencrypted storage is CRITICAL
                if res.get('publicly_accessible', False):
                    sec_issues += 1 # Public DB is HIGH risk

            # 5. Secrets Manager
            elif res['type'] == 'secret':
                # Check rotation
                if not res.get('rotation_enabled', False):
                    # Not always a crit, but a warning. Let's flag it for visibility.
                    sec_issues += 1
            
            # Health Status Logic
            health = "OK"
            if res['state'] in ['stopped', 'Inactive']: health = "OFFLINE"
            if sec_issues > 0: health = "RISK DETECTED"

            # Lambda Metrics Setup
            if res['type'] == 'lambda':
                metrics['cpu_usage'] = res.get('memory', 128) / 10.0 

            cursor.execute('''
                INSERT OR REPLACE INTO metrics (resource_id, cpu_usage, network_in_bytes, network_out_bytes, security_issues_count, health_status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (res['id'], metrics['cpu_usage'], metrics['network_in'], metrics['network_out'], sec_issues, health))
            updates_count += 1
            
        # ... (rest of method)

        # --- Pruning Stale Data ---
        # Remove resources that were NOT updated in this cycle (meaning they no longer exist in AWS)
        # We use a small buffer (e.g. 5 seconds) to be safe against clock skew, 
        # but since we strictly use 'timestamp' from this function start, exact match logic or < start_t is fine.
        
        prune_threshold = timestamp - 1.0 
        cursor.execute("SELECT count(*) FROM resources WHERE last_updated < ?", (prune_threshold,))
        prune_count = cursor.fetchone()[0]
        
        if prune_count > 0:
            cursor.execute("DELETE FROM resources WHERE last_updated < ?", (prune_threshold,))
            # Cascade delete metrics? (SQLite FK handles it if enabled, but let's be explicit to keep DB clean)
            cursor.execute("DELETE FROM metrics WHERE resource_id NOT IN (SELECT id FROM resources)")
            log.info(f"Pruned {prune_count} stale resources.")

        conn.commit()
        conn.close()
        
        status_msg = f"Synced {updates_count}."
        if prune_count > 0: status_msg += f" Pruned {prune_count}."
        self.detailed_status = status_msg
