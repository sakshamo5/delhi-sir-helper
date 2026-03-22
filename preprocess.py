"""
Run this ONCE locally before deploying to Streamlit Cloud:

    python preprocess.py

It reads the `voter` table, normalizes the `row` text,
and writes a `voter_index` table into the same electoral.db.
Streamlit app will then read directly from voter_index — no processing per session.
"""

import sqlite3
import re
import os

DB_PATH = "electoral.db"


def normalize(text):
    text = text.lower()
    text = re.sub(r'[^a-z\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def build_index():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    # Drop old index if re-running
    cur.execute("DROP TABLE IF EXISTS voter_index")

    # Create new index table with norm column
    cur.execute("""
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
    cur.execute("CREATE INDEX IF NOT EXISTS idx_constituency ON voter_index (constituency)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_gender       ON voter_index (gender)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_age          ON voter_index (age)")

    # Read source table
    cur.execute("SELECT constituency, part, sNo, gender, age, row FROM voter")
    rows = cur.fetchall()
    total = len(rows)
    print(f"Processing {total:,} rows…")

    batch = []
    for i, (constituency, part, sNo, gender, age, row_text) in enumerate(rows, 1):
        raw  = str(row_text or "")
        if len(raw) <= 5:
            continue
        norm = normalize(raw)
        batch.append((constituency, part, sNo, gender, int(age or 0), raw, norm))

        if i % 10000 == 0:
            cur.executemany(
                "INSERT INTO voter_index (constituency, part, sNo, gender, age, raw, norm) VALUES (?,?,?,?,?,?,?)",
                batch
            )
            batch = []
            print(f"  {i:,} / {total:,} done…")

    if batch:
        cur.executemany(
            "INSERT INTO voter_index (constituency, part, sNo, gender, age, raw, norm) VALUES (?,?,?,?,?,?,?)",
            batch
        )

    conn.commit()
    conn.close()

    size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
    print(f"\n✅ Done. voter_index built with {total:,} rows.")
    print(f"   DB size now: {size_mb:.1f} MB")


if __name__ == "__main__":
    build_index()