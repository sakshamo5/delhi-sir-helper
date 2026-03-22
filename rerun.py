"""
Rerunner for constituency which had low pdf count 
"""

import logging
import random
import shutil
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager



STATE_CODE   = "U05"
OUTPUT_DIR   = Path("eci_pdfs")
TEMP_DIR     = Path("eci_pdfs/_tmp_rerun")
LOG_FILE     = Path("eci_rerun.log")

# Constituencies to re-check (those with suspiciously low counts)
RERUN_CONSTITUENCIES = [3, 6, 7, 8]

MAX_PARTS      = 300
MAX_RETRIES    = 3
DELAY_MIN      = 1.5
DELAY_MAX      = 3.5
DOWNLOAD_WAIT  = 45
POLL_INTERVAL  = 0.5



logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)



def make_url(state, c, p):
    return f"https://www.eci.gov.in/sir/f4/U05/data/OLDSIRROLL/{state}/{c}/{state}_{c}_{p}.pdf"

def make_dest(state, c, p):
    return OUTPUT_DIR / state / str(c) / f"{state}_{c}_{p}.pdf"

def filename_from_url(url):
    return url.rstrip("/").split("/")[-1]

def build_driver(download_dir: Path) -> webdriver.Chrome:
    abs_dl = str(download_dir.resolve())
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("prefs", {
        "download.default_directory":         abs_dl,
        "download.prompt_for_download":       False,
        "download.directory_upgrade":         True,
        "plugins.always_open_pdf_externally": True,
        "safebrowsing.enabled":               True,
    })
    service = Service(ChromeDriverManager().install())
    driver  = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    driver.execute_cdp_cmd(
        "Browser.setDownloadBehavior",
        {"behavior": "allow", "downloadPath": abs_dl},
    )
    driver.set_page_load_timeout(30)
    return driver

def wait_for_download(temp_dir, filename):
    expected = temp_dir / filename
    partial  = temp_dir / (filename + ".crdownload")
    deadline = time.time() + DOWNLOAD_WAIT
    while time.time() < deadline:
        if expected.exists() and not partial.exists() and expected.stat().st_size > 0:
            return expected
        time.sleep(POLL_INTERVAL)
    return None

def download_one(driver, url, dest_path, temp_dir):
    filename = filename_from_url(url)
    if dest_path.exists() and dest_path.stat().st_size > 1024:
        return "skip"
    for stale in temp_dir.glob(f"{filename}*"):
        stale.unlink(missing_ok=True)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            driver.get(url)
        except Exception as exc:
            log.debug("driver.get raised: %s", exc)
        completed = wait_for_download(temp_dir, filename)
        if completed:
            with open(completed, "rb") as f:
                header = f.read(4)
            if header == b"%PDF":
                shutil.move(str(completed), str(dest_path))
                return "ok"
            else:
                completed.unlink(missing_ok=True)
                return "404"
        else:
            # Nothing downloaded → 404
            return "404"
    return "fail"



def main():
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    log.info("Current PDF counts for target constituencies:")
    for c in RERUN_CONSTITUENCIES:
        folder = OUTPUT_DIR / STATE_CODE / str(c)
        count  = len(list(folder.glob("*.pdf"))) if folder.exists() else 0
        log.info("  AC %3d : %d PDFs", c, count)

    driver = build_driver(TEMP_DIR)
    failed = []

    try:
        for c in RERUN_CONSTITUENCIES:
            log.info("─" * 50)
            log.info("▶ Re-running constituency %d", c)
            saved = skipped = 0

            for p in range(1, MAX_PARTS + 1):
                url  = make_url(STATE_CODE, c, p)
                dest = make_dest(STATE_CODE, c, p)

                result = download_one(driver, url, dest, TEMP_DIR)

                if result == "ok":
                    saved += 1
                    log.info("  SAVED  C%-3d P%-4d", c, p)
                    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
                elif result == "skip":
                    skipped += 1
                elif result == "404":
                    log.info("  404 at part %d → AC %d done (saved=%d, skipped=%d)",
                             p, c, saved, skipped)
                    break
                elif result == "fail":
                    log.error("  FAIL C%-3d P%-4d", c, p)
                    failed.append(url)
                    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    finally:
        driver.quit()
        shutil.rmtree(TEMP_DIR, ignore_errors=True)

    log.info("=" * 50)
    log.info("Updated PDF counts:")
    for c in RERUN_CONSTITUENCIES:
        folder = OUTPUT_DIR / STATE_CODE / str(c)
        count  = len(list(folder.glob("*.pdf"))) if folder.exists() else 0
        log.info("  AC %3d : %d PDFs", c, count)

    if failed:
        Path("eci_rerun_failed.txt").write_text("\n".join(failed), encoding="utf-8")
        log.warning("Failed URLs: eci_rerun_failed.txt")

if __name__ == "__main__":
    main()
