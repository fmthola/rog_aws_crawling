from src.database import get_connection
import json

def check_instance(rid):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT details FROM resources WHERE id=?", (rid,))
    res = c.fetchone()
    conn.close()
    
    print(f"Checking {rid}...")
    if res and res[0]:
        print(f" > Data Size: {len(res[0])} bytes")
        print(f" > Content Preview: {res[0][:200]}...")
        try:
            data = json.loads(res[0])
            print(" > JSON Parse: SUCCESS")
            print(f" > Keys: {list(data.keys())}")
        except:
            print(" > JSON Parse: FAILED")
    else:
        print(" > NO DATA FOUND in DB.")

if __name__ == "__main__":
    check_instance("i-0e58880ef9ff9d3e9")
