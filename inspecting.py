import sqlite3
from collections import defaultdict

DB_PATH = "electoral.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def print_section(title):
    print("\n" + "=" * 60)
    print(f"{title}")
    print("=" * 60)


# ---------------- BASIC STATS ---------------- #

def total_constituencies(cursor):
    cursor.execute("SELECT COUNT(DISTINCT constituency) FROM voter")
    return cursor.fetchone()[0]


def parts_per_constituency(cursor):
    cursor.execute("""
        SELECT constituency, COUNT(DISTINCT part)
        FROM voter
        GROUP BY constituency
        ORDER BY CAST(constituency AS INTEGER)
    """)
    return cursor.fetchall()


def rows_per_constituency(cursor):
    cursor.execute("""
        SELECT constituency, COUNT(*)
        FROM voter
        GROUP BY constituency
        ORDER BY CAST(constituency AS INTEGER)
    """)
    return cursor.fetchall()


def rows_per_part(cursor):
    cursor.execute("""
        SELECT constituency, part, COUNT(*)
        FROM voter
        GROUP BY constituency, part
        ORDER BY CAST(constituency AS INTEGER), CAST(part AS INTEGER)
    """)
    return cursor.fetchall()


def gender_distribution(cursor):
    cursor.execute("""
        SELECT gender, COUNT(*)
        FROM voter
        GROUP BY gender
    """)
    return cursor.fetchall()


def largest_part(cursor):
    cursor.execute("""
        SELECT constituency, part, COUNT(*) as total
        FROM voter
        GROUP BY constituency, part
        ORDER BY total DESC
        LIMIT 1
    """)
    return cursor.fetchone()


# ---------------- MAIN ---------------- #

def main():
    conn = get_connection()
    cursor = conn.cursor()

    # Total constituencies
    print_section("TOTAL CONSTITUENCIES")
    total = total_constituencies(cursor)
    print(f"Total Constituencies: {total}")

    # Parts per constituency
    print_section("PARTS PER CONSTITUENCY")
    parts = parts_per_constituency(cursor)
    for c, p in parts:
        print(f"Constituency {c} → {p} parts")

    # Rows per constituency
    print_section("ROWS PER CONSTITUENCY")
    rows_const = rows_per_constituency(cursor)
    for c, r in rows_const:
        print(f"Constituency {c} → {r} voters")

    # Rows per part
    print_section("ROWS PER PART")
    rows_part = rows_per_part(cursor)
    for c, p, r in rows_part[:50]:  # limit print
        print(f"C{c} - Part {p} → {r} voters")

    print("\n... (showing first 50 only)")

    # Gender distribution
    print_section("GENDER DISTRIBUTION")
    genders = gender_distribution(cursor)
    for g, count in genders:
        print(f"{g} → {count}")

    # Largest part
    print_section("LARGEST PART")
    c, p, total = largest_part(cursor)
    print(f"Constituency {c}, Part {p} → {total} voters")

    conn.close()


if __name__ == "__main__":
    main()