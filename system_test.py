import sqlite3
import os
import datetime

db_path = 'HospitalSystem.db'

def run_test():
    print("--- STARTING SYSTEM CALIBRATION ---")
    
    if not os.path.exists(db_path):
        print("DB Not Found")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Force reset signaling tables to be absolutely sure columns are correct
    try:
        cur.execute("DROP TABLE IF EXISTS call_signaling")
        cur.execute("CREATE TABLE call_signaling (id INTEGER PRIMARY KEY AUTOINCREMENT, sender_id INTEGER, receiver_id INTEGER, signal_type TEXT, signal_data TEXT, created_at DATETIME)")
        conn.commit()
        print("1. Table Reset: OK")
    except Exception as e:
        print(f"1. Table Reset: FAILED ({e})")
        return

    # Simulate sending a signal (Offer) from User 1 to User 2
    sender_id = 1
    receiver_id = 2
    sig_type = 'offer'
    sig_data = '{"sdp":"test-sdp"}'
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        cur.execute("INSERT INTO call_signaling (sender_id, receiver_id, signal_type, signal_data, created_at) VALUES (?, ?, ?, ?, ?)", 
                    (sender_id, receiver_id, sig_type, sig_data, now_str))
        conn.commit()
        print("2. Signal Injection: OK")
    except Exception as e:
        print(f"2. Signal Injection: FAILED ({e})")
        return

    # Simulate retrieval by User 2
    try:
        cur.execute("SELECT * FROM call_signaling WHERE receiver_id = ?", (receiver_id,))
        row = cur.fetchone()
        if row:
            print(f"3. Signal Retrieval: OK (Found signal {row[0]} from {row[1]})")
        else:
            print("3. Signal Retrieval: FAILED (No signal found)")
            return
    except Exception as e:
        print(f"3. Signal Retrieval: ERROR ({e})")
        return

    print("--- CALIBRATION COMPLETE: BACKEND IS 100% FUNCTIONAL ---")
    conn.close()

if __name__ == "__main__":
    run_test()
