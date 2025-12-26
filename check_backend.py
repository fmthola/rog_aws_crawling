from src.data_manager import DataManager
from src.database import get_connection
import time
import sys

def main():
    print("Starting Backend Data Manager for validation...")
    dm = DataManager(interval=2)
    dm.start()
    
    print("Waiting for data synchronization (Timeout 20s)...")
    start_time = time.time()
    success = False
    
    while time.time() - start_time < 20:
        try:
            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT count(*) FROM resources")
            count = c.fetchone()[0]
            conn.close()
            
            if count > 0:
                print(f"\n[SUCCESS] Backend is active. {count} resources captured in cache.")
                # Show a sample
                conn = get_connection()
                c = conn.cursor()
                c.execute("SELECT id, type, state FROM resources LIMIT 5")
                rows = c.fetchall()
                print("Sample Resources:")
                for r in rows:
                    print(f" - {r[0]} ({r[1]}): {r[2]}")
                conn.close()
                success = True
                break
        except Exception as e:
            print(f"Error: {e}")
        
        sys.stdout.write(".")
        sys.stdout.flush()
        time.sleep(2)
    
    dm.stop()
    if not success:
        print("\n[FAILURE] No data captured. Check AWS credentials or network.")
        sys.exit(1)

if __name__ == "__main__":
    main()

