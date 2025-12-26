from src.database import get_connection

def check():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT count(*) FROM cloudtrail_logs")
    ct_count = c.fetchone()[0]
    c.execute("SELECT count(*) FROM vpc_flow_logs")
    flow_count = c.fetchone()[0]
    c.execute("SELECT count(*) FROM resources")
    res_count = c.fetchone()[0]
    conn.close()
    
    print(f"VERIFICATION RESULTS:")
    print(f" - Resources: {res_count}")
    print(f" - CloudTrail Events: {ct_count}")
    print(f" - Flow Logs: {flow_count}")

if __name__ == "__main__":
    check()
