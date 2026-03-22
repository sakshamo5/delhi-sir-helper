import sqlite3
import re
from pathlib import Path

FOLDER_PATH = Path("eci_pdfs/U05_txt")
DB_PATH = 'electoral.db'


conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("DROP TABLE IF EXISTS voter")

cursor.execute('''
CREATE TABLE voter (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    constituency TEXT,
    part TEXT,
    sNo INTEGER,
    gender TEXT,
    age INTEGER,
    row TEXT
)
''')

conn.commit()


def extract_sno(row):
    match = re.match(r'^\d+', row)
    return int(match.group()) if match else None


def extract_gender(row):
    matches = re.findall(r'\b[M|F]\b', row)
    return matches[-1] if matches else None


def extract_age(row):
    numbers = re.findall(r'\b\d{1,3}\b', row)

    # traverse from end → most reliable
    for num in reversed(numbers):
        age = int(num)
        if 18 <= age <= 120:
            return age

    return None


def is_valid_row(row):
    return (
        len(row) > 15 and
        re.match(r'^\d+', row) is not None
    )


def parse_file(file_path):
    with open(file_path, encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    parsed = []

    for line in lines:
        row = line.strip().upper()

        if not is_valid_row(row):
            continue

        try:
            sNo = extract_sno(row)
            gender = extract_gender(row)
            age = extract_age(row)

            if not sNo or gender not in ['M', 'F'] or age is None:
                continue

            parsed.append((sNo, gender, age, row))

        except:
            continue

    return parsed



def build_database():
    print("🚀 Building database (final robust mode)...")

    total = 0
    files = list(FOLDER_PATH.rglob('*.txt'))

    print(f"📂 Found {len(files)} files")

    for file_path in files:
        constituency = file_path.parent.name
        part = file_path.stem.split('_')[-1]

        rows = parse_file(file_path)

        structured = [
            (constituency, part, r[0], r[1], r[2], r[3])
            for r in rows
        ]

        cursor.executemany('''
            INSERT INTO voter 
            (constituency, part, sNo, gender, age, row)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', structured)

        conn.commit()

        total += len(structured)

        print(f"✔ {file_path.name} → {len(structured)} rows")

    print(f"\n✅ TOTAL INSERTED: {total}")



def inspect():
    print("\n📊 INSPECTION")

    cursor.execute("SELECT COUNT(*) FROM voter")
    print("Total Rows:", cursor.fetchone()[0])

    cursor.execute("SELECT COUNT(DISTINCT constituency) FROM voter")
    print("Total Constituencies:", cursor.fetchone()[0])

    cursor.execute("SELECT gender, COUNT(*) FROM voter GROUP BY gender")
    print("\nGender Distribution:")
    for g, c in cursor.fetchall():
        print(g, "→", c)

    cursor.execute("""
        SELECT constituency, part, COUNT(*) as total
        FROM voter
        GROUP BY constituency, part
        ORDER BY total DESC
        LIMIT 1
    """)
    result = cursor.fetchone()
    if result:
        print("\nLargest Part:", result)
    else:
        print("\nNo data found.")



if __name__ == "__main__":
    build_database()
    inspect()
    conn.close()
