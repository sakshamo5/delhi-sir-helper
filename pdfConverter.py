from pathlib import Path
import pdfplumber
from multiprocessing.pool import ThreadPool
from tqdm import tqdm

INPUT_ROOT  = Path('./U05')        # local folder
OUTPUT_ROOT = Path('./U05_txt')    # output folder
WORKERS     = 15

OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

all_pdfs = sorted(INPUT_ROOT.rglob('*.pdf'))
print(f'PDFs found : {len(all_pdfs)}')
print(f'Output     : {OUTPUT_ROOT}')

def convert(args):
    pdf_path, txt_path = args
    try:
        txt_path.parent.mkdir(parents=True, exist_ok=True)
        lines = []

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text(x_tolerance=3, y_tolerance=3)
                if text:
                    lines.append(text.strip())

        txt_path.write_text('\n'.join(lines), encoding='utf-8')
        return True

    except Exception as e:
        return str(e)

tasks, skipped = [], 0
for pdf in all_pdfs:
    txt = OUTPUT_ROOT / pdf.relative_to(INPUT_ROOT).with_suffix('.txt')

    if txt.exists() and txt.stat().st_size > 0:
        skipped += 1
    else:
        tasks.append((pdf, txt))

print(f'To convert : {len(tasks)}  |  Skipped : {skipped}')

failed = []

with ThreadPool(WORKERS) as pool:
    results = list(tqdm(
        pool.imap(convert, tasks),
        total=len(tasks),
        desc='Converting'
    ))

for (pdf, _), result in zip(tasks, results):
    if result is not True:
        failed.append(f'{pdf}  →  {result}')

print(f'\n✅ Done   : {len(tasks) - len(failed)}')
print(f'❌ Failed : {len(failed)}')

if failed:
    (OUTPUT_ROOT / 'failed.txt').write_text('\n'.join(failed), encoding='utf-8')

sample = next(OUTPUT_ROOT.rglob('*.txt'), None)
if sample:
    print(f'\nSample ({sample.name}):\n')
    print('\n'.join(sample.read_text(encoding='utf-8').splitlines()[:20]))
