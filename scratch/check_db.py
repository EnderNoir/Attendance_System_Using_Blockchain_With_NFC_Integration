import sys
sys.path.append('.')
from dotenv import load_dotenv
load_dotenv()
from services.ops.db_compat import connect_db

try:
    conn = connect_db()
    rows = conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name='students'").fetchall()
    cols = [r[0] for r in rows]
    print(f"Columns in students table: {cols}")
    
    # Check if first_name exists
    if 'first_name' not in cols:
        print("first_name NOT found. Adding it...")
        conn.execute("ALTER TABLE students ADD COLUMN first_name TEXT DEFAULT ''")
        conn.execute("ALTER TABLE students ADD COLUMN middle_initial TEXT DEFAULT ''")
        conn.execute("ALTER TABLE students ADD COLUMN last_name TEXT DEFAULT ''")
        conn.commit()
        print("Columns added successfully.")
    else:
        print("Columns already exist.")
except Exception as e:
    print(f"Error: {e}")
