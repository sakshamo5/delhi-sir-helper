import sqlite3
import os

SOURCE_DB = "electoral.db"
OUTPUT_DIR = "constituency_dbs"

os.makedirs(OUTPUT_DIR, exist_ok=True)

conn = sqlite3.connect(SOURCE_DB)
cursor = conn.cursor()

cursor.execute("SELECT DISTINCT constituency FROM voter_index")
constituencies = [row[0] for row in cursor.fetchall()]

print(f"Found {len(constituencies)} constituencies")

for cons in constituencies:
    print(f"Processing: {cons}")

    safe_name = cons.replace(" ", "_").replace("/", "_")
    new_db_path = os.path.join(OUTPUT_DIR, f"{safe_name}.db")

    new_conn = sqlite3.connect(new_db_path)
    new_cursor = new_conn.cursor()

    new_cursor.execute("""
        CREATE TABLE voter_index (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            constituency TEXT,
            part         TEXT,
            sNo          INTEGER,
            gender       TEXT,
            age          INTEGER,
            raw          TEXT,
            norm         TEXT
        )
    """)

    cursor.execute("""
        SELECT constituency, part, sNo, gender, age, raw, norm
        FROM voter_index
        WHERE constituency = ?
    """, (cons,))
    rows = cursor.fetchall()

    new_cursor.executemany("""
        INSERT INTO voter_index (constituency, part, sNo, gender, age, raw, norm)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, rows)

    new_conn.commit()
    new_conn.close()

conn.close()

print("Done splitting voter_index DB ✅")
