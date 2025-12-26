import boto3
import random
import time
import datetime
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from src.logger import log

class AWSClient:
    def __init__(self, region="us-gov-west-1", mock_mode=False):
        self.region = region
        self.mock_mode = mock_mode
        self.session = boto3.Session(region_name=self.region)
        log.info(f"AWS Client initialized. Region: {region}, Mock Mode: {mock_mode}")

    def _parse_tags(self, tag_list):
        """Converts AWS tag list to a simple dict."""
        if not tag_list: return {}
        return {t['Key']: t['Value'] for t in tag_list}

    def get_secret_value(self, secret_id):
        """Retrieves the decrypted secret value."""
        if self.mock_mode: return "MOCK_SECRET_VALUE_12345"
        try:
            client = self.session.client('secretsmanager')
            response = client.get_secret_value(SecretId=secret_id)
            if 'SecretString' in response:
                return response['SecretString']
            return "[Binary Secret Data]"
        except Exception as e:
            log.error(f"Secret Fetch Error: {e}")
            return f"Error: {str(e)}"

    def list_ec2_instances(self):
        """
        Returns a list of dictionaries representing EC2 instances.
        """
        if self.mock_mode:
            return self._generate_mock_ec2()

        try:
            ec2 = self.session.resource('ec2')
            instances = []
            for instance in ec2.instances.all():
                # Parse Security Groups
                sgs = [sg['GroupName'] for sg in instance.security_groups] if instance.security_groups else []
                
                instances.append({
                    'id': instance.id,
                    'name': instance.instance_type, 
                    'type': 'ec2', 
                    'state': instance.state['Name'],
                    'public_ip': instance.public_ip_address,
                    'private_ip': instance.private_ip_address,
                    'vpc_id': instance.vpc_id,
                    'subnet_id': instance.subnet_id,
                    'architecture': instance.architecture,
                    'launch_time': str(instance.launch_time),
                    'key_name': instance.key_name,
                    'iam_role': instance.iam_instance_profile['Arn'].split('/')[-1] if instance.iam_instance_profile else 'None',
                    'security_groups': sgs,
                    'tags': self._parse_tags(instance.tags)
                })
            return instances
        except (NoCredentialsError, PartialCredentialsError) as e:
            log.error(f"Credentials error: {e}. Switching to Mock Mode.")
            self.mock_mode = True # Fallback only on explicit credential failure
            return self._generate_mock_ec2()
        except Exception as e:
            log.error(f"Failed to fetch EC2 instances: {e}")
            return [] # Return empty list on network error instead of mock

    def list_lambda_functions(self):
        """
        Returns a list of dictionaries representing Lambda functions.
        """
        if self.mock_mode:
            return self._generate_mock_lambda()
        
        try:
            lamb = self.session.client('lambda')
            functions = []
            paginator = lamb.get_paginator('list_functions')
            for page in paginator.paginate():
                for func in page['Functions']:
                    functions.append({
                        'id': func['FunctionName'],
                        'type': 'lambda',
                        'state': func.get('State', 'Active'),
                        'runtime': func.get('Runtime', 'N/A'),
                        'last_modified': str(func.get('LastModified', '')),
                        'memory': func.get('MemorySize'),
                        'handler': func.get('Handler'),
                        'role': func.get('Role', '').split('/')[-1],
                        'description': func.get('Description', '')
                    })
            return functions
        except Exception as e:
            log.error(f"Failed to fetch Lambdas: {e}")
            return []

    def list_ecr_repos(self):
        if self.mock_mode: return self._generate_mock_generic('ecr', 'repo')
        try:
            client = self.session.client('ecr')
            repos = client.describe_repositories()['repositories']
            results = []
            for r in repos:
                results.append({
                    'id': r['repositoryName'], 
                    'type': 'ecr', 
                    'state': 'Active', 
                    'last_modified': str(r.get('createdAt', '')),
                    'uri': r.get('repositoryUri'),
                    'scan_on_push': r.get('imageScanningConfiguration', {}).get('scanOnPush', False),
                    'encryption': r.get('encryptionConfiguration', {}).get('encryptionType', 'AES256')
                })
            return results
        except Exception as e:
            log.error(f"ECR Error: {e}")
            return []

    def list_ecs_clusters(self):
        if self.mock_mode: return self._generate_mock_generic('ecs', 'cluster')
        try:
            client = self.session.client('ecs')
            arns = client.list_clusters()['clusterArns']
            return [{
                'id': arn.split('/')[-1], 
                'type': 'ecs', 
                'state': 'Active', 
                'last_modified': time.ctime()
            } for arn in arns]
        except Exception as e:
            log.error(f"ECS Error: {e}")
            return []

    def list_eks_clusters(self):
        if self.mock_mode: return self._generate_mock_generic('eks', 'cluster')
        try:
            client = self.session.client('eks')
            names = client.list_clusters()['clusters']
            return [{
                'id': name, 
                'type': 'eks', 
                'state': 'Active', 
                'last_modified': time.ctime()
            } for name in names]
        except Exception as e:
            log.error(f"EKS Error: {e}")
            return []

    def list_secrets(self):
        """Fetches metadata for secrets in Secrets Manager."""
        if self.mock_mode: return self._generate_mock_generic('secret', 'key')
        try:
            client = self.session.client('secretsmanager')
            secrets = []
            paginator = client.get_paginator('list_secrets')
            for page in paginator.paginate():
                for s in page['SecretList']:
                    secrets.append({
                        'id': s['Name'],
                        'type': 'secret',
                        'state': 'Active',
                        'last_accessed': str(s.get('LastAccessedDate', 'Never')),
                        'description': s.get('Description', ''),
                        'kms_key': s.get('KmsKeyId', 'Default'),
                        'tags': self._parse_tags(s.get('Tags', []))
                    })
            return secrets
        except Exception as e:
            log.error(f"SecretsManager Error: {e}")
            return []

    def list_rds_instances(self):
        """Fetches RDS instances."""
        if self.mock_mode: return self._generate_mock_generic('rds', 'db')
        try:
            client = self.session.client('rds')
            dbs = client.describe_db_instances()['DBInstances']
            results = []
            for db in dbs:
                results.append({
                    'id': db['DBInstanceIdentifier'],
                    'type': 'rds',
                    'state': db['DBInstanceStatus'],
                    'engine': f"{db['Engine']} {db['EngineVersion']}",
                    'class': db['DBInstanceClass'],
                    'endpoint': db.get('Endpoint', {}).get('Address', 'Creating...'),
                    'multi_az': db['MultiAZ'],
                    'storage': f"{db['AllocatedStorage']}GB",
                    'vpc_id': db.get('DBSubnetGroup', {}).get('VpcId', 'N/A'),
                    'security_groups': [sg['VpcSecurityGroupId'] for sg in db['VpcSecurityGroups']]
                })
            return results
        except Exception as e:
            log.error(f"RDS Error: {e}")
            return []

    def fetch_ssm_history(self, instance_id):
        """Fetches recent SSM command history for this instance."""
        if self.mock_mode: return []
        try:
            ssm = self.session.client('ssm')
            # List commands targeting this instance
            response = ssm.list_commands(
                InstanceId=instance_id,
                MaxResults=5
            )
            commands = []
            for cmd in response.get('Commands', []):
                # Try to get user info if available in comment or parameters
                commands.append({
                    'CommandId': cmd['CommandId'],
                    'Document': cmd['DocumentName'],
                    'Status': cmd['Status'],
                    'Time': str(cmd['RequestedDateTime']),
                    'Comment': cmd.get('Comment', 'N/A')
                })
            return commands
        except Exception as e:
            log.error(f"SSM Error: {e}")
            return []

    def fetch_instance_logs(self, instance_id):
        """Attempts to find CloudWatch logs for this instance."""
        if self.mock_mode: return []
        try:
            logs = self.session.client('logs')
            # Common pattern: /aws/ec2/instance_id or /var/log/messages
            # We'll try searching for log groups containing the instance ID
            groups = logs.describe_log_groups(limit=50, logGroupNamePrefix='/')
            target_group = None
            for g in groups.get('logGroups', []):
                if instance_id in g['logGroupName']:
                    target_group = g['logGroupName']
                    break
            
            if target_group:
                events = logs.get_log_events(
                    logGroupName=target_group,
                    logStreamName=instance_id, # Often stream name is instance ID
                    limit=20,
                    startFromHead=False
                )
                return [e['message'] for e in events.get('events', [])]
            return []
        except Exception:
            return [] # Silent fail on logs is common

    def get_ecr_findings(self, repo_name):
        """
        Fetches findings using Inspector2 (aggregated) or ECR Scan (fallback).
        Prioritizes Inspector2 for broad repo coverage.
        """
        if self.mock_mode: return {"CRITICAL": 5, "HIGH": 2, "top_findings": [{"name": "CVE-2024-MOCK", "severity": "CRITICAL", "description": "Mock vulnerability for testing UI persistence."}]}
        
        # 1. Try Inspector2 (Best for "What CVEs are in this repo?")
        try:
            inspector = self.session.client('inspector2')
            # List active findings for this ECR Repo
            criteria = {
                'ecrImageRepositoryName': [{'value': repo_name, 'comparison': 'EQUALS'}],
                'findingStatus': [{'value': 'ACTIVE', 'comparison': 'EQUALS'}]
            }
            
            response = inspector.list_findings(
                filterCriteria=criteria,
                maxResults=50,
                sortCriteria={'field': 'SEVERITY', 'sortOrder': 'DESC'}
            )
            
            findings = response.get('findings', [])
            
            if findings:
                crit = 0; high = 0; med = 0
                detailed_list = []
                
                for f in findings:
                    sev = f['severity']
                    if sev == 'CRITICAL': crit += 1
                    elif sev == 'HIGH': high += 1
                    elif sev == 'MEDIUM': med += 1
                    
                    if len(detailed_list) < 15:
                        cve_id = f.get('packageVulnerabilityDetails', {}).get('vulnerabilityId', f['title'])
                        detailed_list.append({
                            'name': cve_id,
                            'severity': sev,
                            'description': f.get('description', 'No description provided.')
                        })
                
                return {
                    "status": "INSPECTOR_FOUND",
                    "CRITICAL": crit,
                    "HIGH": high,
                    "MEDIUM": med,
                    "top_findings": detailed_list
                }
                
        except Exception as e:
            log.warning(f"Inspector2 Data Error for {repo_name}: {e}")
            # Continue to fallback
            
        # 2. Fallback: ECR Image Scan Iteration
        try:
            client = self.session.client('ecr')
            # Get list of images with scan findings
            images = client.describe_images(
                repositoryName=repo_name,
                filter={'tagStatus': 'TAGGED'},
                maxResults=100 # Look deeper
            ).get('imageDetails', [])
            
            if not images: return {"status": "No Images Found"}

            # Sort by severity (Critical count descending)
            def severity_score(img):
                counts = img.get('imageScanFindingsSummary', {}).get('findingSeverityCounts', {})
                return (counts.get('CRITICAL', 0) * 10) + counts.get('HIGH', 0)

            # Filter for images that have actual scan results
            scanned_images = [i for i in images if i.get('imageScanStatus', {}).get('status') == 'COMPLETE']
            
            if not scanned_images:
                return {"status": "No Scanned Images", "info": "Images exist but scans are pending/failed."}

            # Pick the most vulnerable image to represent the repo risks
            target_image = max(scanned_images, key=severity_score)
            
            digest = target_image['imageDigest']
            tag = target_image.get('imageTags', ['untagged'])[0]
            
            findings = client.describe_image_scan_findings(repositoryName=repo_name, imageId={'imageDigest': digest})
            
            # Counts
            counts = findings.get('imageScanFindings', {}).get('findingSeverityCounts', {})
            
            # Details (Top 15 to ensure we get meaningful CVEs)
            detailed_list = []
            all_f = findings.get('imageScanFindings', {}).get('findings', [])
            for f in all_f[:15]:
                detailed_list.append({
                    'name': f.get('name'),
                    'severity': f.get('severity'),
                    'description': f.get('description', 'No description provided.')
                })
                
            return {
                "status": "SCAN_COMPLETE",
                "tag": tag,
                "CRITICAL": counts.get('CRITICAL', 0),
                "HIGH": counts.get('HIGH', 0),
                "MEDIUM": counts.get('MEDIUM', 0),
                "top_findings": detailed_list
            }

        except Exception as e:
            log.error(f"ECR Fallback Error for {repo_name}: {e}")
            return {"error": str(e), "CRITICAL": 0, "HIGH": 0, "top_findings": []}

    def get_resource_details(self, service, resource_id):
        """Generic deep fetch wrapper."""
        if service == 'ecr':
            return self.get_ecr_findings(resource_id)
        # Add other services as needed
        return {}

    def get_active_images(self):
        """Returns a set of image URIs currently running in ECS/EKS."""
        if self.mock_mode: return set()
        active_images = set()
        try:
            # 1. Check ECS Task Definitions in use
            ecs = self.session.client('ecs')
            # List clusters -> List Tasks -> Describe Tasks -> Get Container Images
            # This is heavy. Simplified: List Task Definitions
            tds = ecs.list_task_definitions(status='ACTIVE', maxResults=20)
            for td_arn in tds.get('taskDefinitionArns', []):
                td = ecs.describe_task_definition(taskDefinition=td_arn)
                for container in td['taskDefinition']['containerDefinitions']:
                    active_images.add(container['image'])
                    
            # 2. Check EKS (Requires kubectl or complex API, usually not exposed easily via boto3 without cluster access)
            # We will skip deep EKS pod scanning for this prototype speed and stick to ECS.
        except Exception as e:
            log.error(f"Active Image Scan Error: {e}")
        return active_images

    def fetch_cloudtrail_events(self, hours=24):
        """Fetches CloudTrail events for the last N hours."""
        if self.mock_mode: return []
        
        try:
            ct = self.session.client('cloudtrail')
            start_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)
            
            response = ct.lookup_events(
                StartTime=start_time,
                MaxResults=50, 
                LookupAttributes=[{'AttributeKey': 'ReadOnly', 'AttributeValue': 'false'}]
            )
            return response.get('Events', [])
        except Exception as e:
            log.error(f"CloudTrail Fetch Error: {e}")
            return []

    def fetch_vpc_flow_logs(self, hours=24):
        """
        Attempts to find and fetch VPC Flow Logs from CloudWatch Logs.
        Searches for log groups with 'flow' or 'vpc' in the name.
        """
        if self.mock_mode: return []
        
        try:
            logs = self.session.client('logs')
            # 1. Find potential log groups
            groups = logs.describe_log_groups(limit=20) # check more groups
            target_group = None
            
            # Priority check for standard name
            for g in groups.get('logGroups', []):
                if g['logGroupName'] == '/aws/vpc/flow-logs':
                    target_group = g['logGroupName']
                    break
            
            # Fuzzy search fallback
            if not target_group:
                for g in groups.get('logGroups', []):
                    name = g['logGroupName'].lower()
                    if 'flow' in name or 'vpc' in name:
                        target_group = g['logGroupName']
                        break
            
            if not target_group:
                log.warning("No VPC Flow Log group found (checked /aws/vpc/flow-logs and others).")
                return []

            log.info(f"Fetching Flow Logs from: {target_group}")

            # 2. Fetch events
            start_time = int((time.time() - (hours * 3600)) * 1000)
            events = logs.filter_log_events(
                logGroupName=target_group,
                startTime=start_time,
                limit=100
            )
            return events.get('events', [])
            
        except Exception as e:
            log.error(f"Flow Logs Fetch Error: {e}")
            return []

    def get_instance_metrics(self, instance_id):
        """
        Fetches CloudWatch metrics for a specific instance.
        Returns: {cpu_usage, network_in, network_out}
        """
        if self.mock_mode:
            return {
                'cpu_usage': random.uniform(0, 100),
                'network_in': random.uniform(0, 5000),
                'network_out': random.uniform(0, 5000)
            }
        
        # Real implementation would go here using cloudwatch client
        # returning mock data for now to ensure prototype stability
        return {
            'cpu_usage': random.uniform(0, 100),
            'network_in': random.uniform(0, 5000),
            'network_out': random.uniform(0, 5000)
        }

    def _generate_mock_ec2(self, count=20):
        """Generates fake EC2 data for testing."""
        types = ['t3.micro', 'm5.large', 'c5.xlarge', 'g4dn.xlarge']
        states = ['running', 'stopped', 'pending', 'terminated']
        
        data = []
        for i in range(count):
            state = random.choice(states)
            if random.random() > 0.3: state = 'running'

            data.append({
                'id': f'i-{random.randint(10000000, 99999999)}',
                'type': random.choice(types),
                'state': state,
                'public_ip': f'10.0.{random.randint(0,255)}.{random.randint(0,255)}',
                'launch_time': time.ctime()
            })
        return data

    def _generate_mock_lambda(self, count=10):
        data = []
        runtimes = ['python3.9', 'nodejs18.x', 'go1.x']
        for i in range(count):
            data.append({
                'id': f'func-{random.randint(1000, 9999)}',
                'type': 'lambda',
                'state': 'Active',
                'runtime': random.choice(runtimes),
                'last_modified': time.ctime()
            })
        return data
        
    def _generate_mock_generic(self, service, prefix, count=5):
        data = []
        for i in range(count):
            data.append({
                'id': f'{prefix}-{random.randint(100, 999)}',
                'type': service,
                'state': 'Active' if random.random() > 0.1 else 'Issue',
                'last_modified': time.ctime()
            })
        return data