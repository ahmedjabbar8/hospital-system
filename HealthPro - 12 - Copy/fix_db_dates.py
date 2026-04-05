import sqlite3
import datetime

def fix_dates():
    try:
        conn = sqlite3.connect('HospitalSystem.db')
        cur = conn.cursor()
        
        # Tables to check
        tables = ['radiology_requests', 'lab_requests', 'appointments', 'patients', 'triage', 'consultations', 'invoices', 'prescriptions', 'referrals']
        
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for table in tables:
            try:
                # Check if current_at contains the broken string
                cur.execute(f"UPDATE {table} SET created_at = ? WHERE created_at = 'CURRENT_DATETIME'", (now,))
                print(f"Fixed {cur.rowcount} rows in {table}")
            except sqlite3.OperationalError as e:
                # Table might not have created_at
                print(f"Skipping {table}: {e}")
        
        conn.commit()
        conn.close()
        print("Done fixing dates.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_dates()
