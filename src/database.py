import sqlite3
import time
from src.logger import log

DB_PATH = "cloud_cache.db"

def init_db():
    """Initializes the SQLite database with the required schema."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Resources Table (Stores base info for EC2, Lambda, etc.)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS resources (
        id TEXT PRIMARY KEY,
        name TEXT,
        type TEXT, -- 'ec2', 'lambda', 'rds'
        state TEXT, -- 'running', 'stopped', 'pending'
        region TEXT,
        last_updated REAL,
        details TEXT -- JSON blob for extra metadata
    )
    ''')
    
    # Migration for existing DB (since we are iterating)
    try:
        cursor.execute("ALTER TABLE resources ADD COLUMN details TEXT")
    except sqlite3.OperationalError:
        pass # Column likely exists

    # Metrics Table (Stores data specific to modes: CPU, Network, Security)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS metrics (
        resource_id TEXT PRIMARY KEY,
        cpu_usage REAL DEFAULT 0.0,
        network_in_bytes REAL DEFAULT 0.0,
        network_out_bytes REAL DEFAULT 0.0,
        security_issues_count INTEGER DEFAULT 0,
        health_status TEXT DEFAULT 'OK',
        flow_log_size REAL DEFAULT 0.0,
        FOREIGN KEY(resource_id) REFERENCES resources(id)
    )
    ''')

    # AI Analysis Cache (To avoid re-querying Gemini constantly)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ai_analysis (
        resource_id TEXT PRIMARY KEY,
        summary TEXT,
        timestamp REAL,
        FOREIGN KEY(resource_id) REFERENCES resources(id)
    )
    ''')

    # App State (For music persistence, etc.)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS app_state (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    ''')

    # CloudTrail Logs
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cloudtrail_logs (
        event_id TEXT PRIMARY KEY,
        event_name TEXT,
        event_time REAL,
        resource_id TEXT,
        username TEXT,
        raw_data TEXT
    )
    ''')

    # VPC Flow Logs (Simplified)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS vpc_flow_logs (
        record_id TEXT PRIMARY KEY,
        interface_id TEXT,
        src_addr TEXT,
        dst_addr TEXT,
        bytes INTEGER,
        action TEXT,
        timestamp REAL
    )
    ''')

    conn.commit()
    conn.close()
    log.info(f"Database initialized at {DB_PATH}")

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)
