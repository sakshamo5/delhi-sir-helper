# Delhi Electoral Roll Search 🏛️

A simple tool to help you find voter records in Delhi (**U05**) more easily. It handles the boring stuff—downloading PDFs, extracting text, and building a searchable database—so you can find names even when they're misspelled (Fuzzy Search!).

## ✨ What it does
- **Automated Downloads:** Grabs electoral PDFs from the ECI site using Selenium.
- **Smart Text Extraction:** Pulls out Names, Ages, Genders, and Serial Nos using `pdfplumber`.
- **Fuzzy Search:** Uses `rapidfuzz` to find people even with typos or weird OCR errors.
- **Fast Dashboard:** A clean Streamlit UI for quick filtering and searching.

## 🛠️ Quick Start

1. **Install:** `pip install -r requirements.txt`
2. **Process Data (The Sequence):**
   - `python download.py` (Get PDFs)
   - `python pdfConverter.py` (PDF → Text)
   - `python parsingText.py` (Text → Database)
   - `python db_split.py` (Split for speed)
3. **Launch Search:** `streamlit run app.py`

## 📂 Project Flow
`PDFs` ➡️ `Text` ➡️ `Master DB` ➡️ `Split DBs` ➡️ `Search UI`

---
Built with Python, Streamlit, and SQLite.
