import sqlite3, json, os

db_path = 'attendance.db'
if not os.path.exists(db_path):
    print("No attendance.db found")
else:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM event_schedules").fetchall()
    for r in rows:
        d = dict(r)
        print(f"ID: {d['event_id']}, Title: {d['title']}")
        print(f"Teachers JSON: {d['teacher_usernames_json']}")
    conn.close()
