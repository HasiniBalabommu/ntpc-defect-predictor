import pandas as pd
import sqlite3
import os
from datetime import datetime

# Paths
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCEL_PATH= os.path.join(BASE_DIR, 'data', 'korba_defects.xlsx')
DB_PATH   = os.path.join(BASE_DIR, 'database', 'ntpc_records.db')
LOG_PATH  = os.path.join(BASE_DIR, 'scripts', 'sync_log.txt')

def log(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line      = f"[{timestamp}] {message}"
    print(line)
    with open(LOG_PATH, 'a') as f:
        f.write(line + '\n')

def sync_excel_to_db():
    log("Starting Excel sync...")

    try:
        # Load Excel
        df = pd.read_excel(EXCEL_PATH)
        log(f"Excel loaded: {df.shape[0]} rows")

        # Connect to database
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()

        # Create excel_records table if not exists
        c.execute('''
            CREATE TABLE IF NOT EXISTS excel_records (
                id           INTEGER PRIMARY KEY,
                notification INTEGER UNIQUE,
                equipment    TEXT,
                notif_date   TEXT,
                priority     TEXT,
                notif_type   TEXT,
                synced_on    TEXT
            )
        ''')

        # Count existing records
        c.execute("SELECT COUNT(*) FROM excel_records")
        existing = c.fetchone()[0]
        log(f"Existing records in database: {existing}")

        # Add only new rows
        new_count = 0
        for _, row in df.iterrows():
            try:
                c.execute('''
                    INSERT OR IGNORE INTO excel_records
                    VALUES (NULL, ?, ?, ?, ?, ?, ?)
                ''', (
                    row['Notification'],
                    str(row['equipment']).strip().upper(),
                    str(row['Notif.date']),
                    str(row['Priority']),
                    str(row['Notifictn type']),
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))
                if c.rowcount > 0:
                    new_count += 1
            except Exception as e:
                continue

        conn.commit()
        conn.close()

        log(f"New rows added: {new_count}")
        log("Excel sync complete!")

        # Trigger retrain if new rows found
        if new_count > 0:
            log("New rows found → triggering retrain...")
            from retrain import retrain
            success, accuracy = retrain()
            if success:
                log(f"Retrain successful! Accuracy: {accuracy}%")
            else:
                log("Retrain failed!")

    except Exception as e:
        log(f"Sync failed: {e}")

if __name__ == "__main__":
    sync_excel_to_db()