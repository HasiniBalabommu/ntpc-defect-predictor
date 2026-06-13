import sqlite3
import os

# This automatically finds your database
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, 'database', 'ntpc_records.db')

conn = sqlite3.connect(DB_PATH)
conn.execute("DELETE FROM new_records")
conn.execute("DELETE FROM upload_history")
conn.commit()
conn.close()
print("Done! All records cleared.")