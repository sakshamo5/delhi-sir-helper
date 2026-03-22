from pathlib import Path

root = Path("U05")
STATE = "U05"

total = 0
issues = []

for constituency in sorted(root.iterdir(), key=lambda p: int(p.name)):
    if not constituency.is_dir():
        continue

    c    = int(constituency.name)
    pdfs = sorted(constituency.glob("*.pdf"), key=lambda p: int(p.stem.split("_")[-1]))
    count = len(pdfs)
    total += count

    # Extract actual part numbers from filenames
    part_numbers = [int(p.stem.split("_")[-1]) for p in pdfs]

    # Find gaps: e.g. [1,2,3,5,6] → missing 4
    actual_missing = []
    if part_numbers:
        for i in range(part_numbers[0], part_numbers[-1] + 1):
            if i not in part_numbers:
                actual_missing.append(i)

    status = "OK" if not actual_missing else f"GAPS: {actual_missing}"
    flag   = "⚠ " if actual_missing else "  "

    print(f"{flag}AC {c:>3} : {count:>4} PDFs  [{status}]")

    if actual_missing:
        issues.append((c, actual_missing))

print(f"\n  TOTAL : {total} PDFs across {len(list(root.iterdir()))} constituencies")

if issues:
    print(f"\n  ⚠  {len(issues)} constituencies have gaps in part numbering:")
    for c, missing in issues:
        print(f"     AC {c:>3} → missing parts: {missing}")
else:
    print("\n  ✓  All constituencies have continuous part numbering!")