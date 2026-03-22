"""
ECI PDF Downloader — Full Automated
=====================================
Downloads all Electoral Roll PDFs for Delhi (U05) from the ECI website.

URL pattern:
  https://www.eci.gov.in/sir/f4/U05/data/OLDSIRROLL/U05/{C}/U05_{C}_{P}.pdf
  C = constituency number (1 to 70)
  P = part number (1 to N, stop when server returns 404)

Directory structure saved:
  eci_pdfs/
    U05/
      1/
        U05_1_1.pdf
        U05_1_2.pdf
        ...
      2/
        U05_2_1.pdf
        ...

Strategy:
  - One Chrome driver per worker thread (thread pool = NUM_WORKERS)
  - Each worker handles one constituency at a time
  - Parts are downloaded sequentially within a constituency (stop on 404)
  - Skip already-downloaded files
  - Retry logic with exponential backoff
  - All failures logged to failed_urls.txt for re-runs

Dependencies:
    pip install selenium webdriver-manager
"""

import logging
import queue
import random
import shutil
import threading
import time
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


# ---------------------------------------------------------------------------
# Configuration — tweak these as needed
# ---------------------------------------------------------------------------

STATE_CODE    = "U05"
CONSTITUENCIES = range(1, 71)          # 1 to 70 inclusive
MAX_PARTS      = 300                   # Safety cap per constituency (stop earlier on 404)

OUTPUT_DIR     = Path("eci_pdfs")      # Root output folder
LOG_FILE       = Path("eci_download.log")

NUM_WORKERS    = 10                     # Parallel Chrome instances (raise carefully)
MAX_RETRIES    = 3
DELAY_MIN      = 1.5                   # Seconds between part downloads (per worker)
DELAY_MAX      = 3.5
DOWNLOAD_WAIT  = 45                    # Max seconds to wait for a single file
POLL_INTERVAL  = 0.5


# ---------------------------------------------------------------------------
# Logging — thread-safe (Python's logging module handles this)
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(threadName)-12s]  %(levelname)-8s  %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# Global list to collect failed URLs (protected by a lock)
failed_urls: list[str] = []
failed_lock = threading.Lock()


# ---------------------------------------------------------------------------
# URL + path helpers
# ---------------------------------------------------------------------------

def make_url(state: str, constituency: int, part: int) -> str:
    return (
        f"https://www.eci.gov.in/sir/f4/U05/data/OLDSIRROLL"
        f"/{state}/{constituency}/{state}_{constituency}_{part}.pdf"
    )

def make_dest_path(state: str, constituency: int, part: int) -> Path:
    """Mirror the URL structure locally under OUTPUT_DIR."""
    return OUTPUT_DIR / state / str(constituency) / f"{state}_{constituency}_{part}.pdf"

def make_temp_dir(worker_id: int) -> Path:
    """Each worker gets its own isolated temp download directory."""
    d = OUTPUT_DIR / f"_tmp_worker_{worker_id}"
    d.mkdir(parents=True, exist_ok=True)
    return d

def filename_from_url(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


# ---------------------------------------------------------------------------
# Chrome driver factory
# ---------------------------------------------------------------------------

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
    options.add_experimental_option(
        "prefs",
        {
            "download.default_directory":         abs_dl,
            "download.prompt_for_download":       False,
            "download.directory_upgrade":         True,
            "plugins.always_open_pdf_externally": True,   # Disable PDF viewer → force download
            "safebrowsing.enabled":               True,
        },
    )

    service = Service(ChromeDriverManager().install())
    driver  = webdriver.Chrome(service=service, options=options)

    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    # Allow downloads in headless mode (blocked by default)
    driver.execute_cdp_cmd(
        "Browser.setDownloadBehavior",
        {"behavior": "allow", "downloadPath": abs_dl},
    )
    driver.set_page_load_timeout(30)
    return driver


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def wait_for_download(temp_dir: Path, filename: str) -> Optional[Path]:
    """Wait until the file exists and has no .crdownload partner."""
    expected = temp_dir / filename
    partial  = temp_dir / (filename + ".crdownload")
    deadline = time.time() + DOWNLOAD_WAIT

    while time.time() < deadline:
        if expected.exists() and not partial.exists() and expected.stat().st_size > 0:
            return expected
        time.sleep(POLL_INTERVAL)
    return None


def is_404_page(temp_dir: Path, filename: str) -> bool:
    """
    When Chrome 'downloads' an HTML 404 error page instead of a PDF,
    the file will exist but won't start with %PDF.
    Also handles the case where Chrome doesn't download anything (true 404
    that the browser just shows as an error — nothing lands in temp_dir).
    """
    f = temp_dir / filename
    if not f.exists():
        return True   # Nothing downloaded — treat as 404
    with open(f, "rb") as fh:
        header = fh.read(4)
    if header != b"%PDF":
        f.unlink(missing_ok=True)
        return True
    return False


def download_one(driver: webdriver.Chrome, url: str,
                 dest_path: Path, temp_dir: Path) -> str:
    """
    Download a single PDF.

    Returns:
        "ok"      — downloaded and saved successfully
        "skip"    — already exists locally
        "404"     — server returned 404 (stop iterating parts)
        "fail"    — failed after all retries
    """
    filename = filename_from_url(url)

    # Skip already-downloaded
    if dest_path.exists() and dest_path.stat().st_size > 1024:
        return "skip"

    # Clean stale temp files
    for stale in temp_dir.glob(f"{filename}*"):
        stale.unlink(missing_ok=True)

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            driver.get(url)
        except Exception as exc:
            log.debug("driver.get raised (expected for downloads): %s", exc)

        completed = wait_for_download(temp_dir, filename)

        if completed is None:
            # Nothing appeared — likely a 404 or network error
            if is_404_page(temp_dir, filename):
                return "404"
            log.warning("Attempt %d — timeout waiting for %s", attempt, filename)
        else:
            with open(completed, "rb") as f:
                header = f.read(4)
            if header == b"%PDF":
                shutil.move(str(completed), str(dest_path))
                return "ok"
            else:
                # Not a PDF — probably a 404 HTML page
                completed.unlink(missing_ok=True)
                return "404"

        if attempt < MAX_RETRIES:
            wait = random.uniform(DELAY_MIN * attempt, DELAY_MAX * attempt)
            time.sleep(wait)

    return "fail"


# ---------------------------------------------------------------------------
# Worker — processes one constituency at a time from the queue
# ---------------------------------------------------------------------------

def worker(worker_id: int, constituency_queue: queue.Queue) -> None:
    temp_dir = make_temp_dir(worker_id)
    driver   = build_driver(temp_dir)
    thread   = threading.current_thread()
    thread.name = f"Worker-{worker_id}"

    log.info("Worker %d started", worker_id)

    try:
        while True:
            try:
                constituency = constituency_queue.get_nowait()
            except queue.Empty:
                break

            log.info("▶ Starting constituency %d", constituency)
            saved = 0
            skipped = 0

            for part in range(1, MAX_PARTS + 1):
                url       = make_url(STATE_CODE, constituency, part)
                dest_path = make_dest_path(STATE_CODE, constituency, part)

                result = download_one(driver, url, dest_path, temp_dir)

                if result == "ok":
                    saved += 1
                    log.info("  SAVED  C%-3d  P%-4d  %s", constituency, part,
                             dest_path.name)
                    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

                elif result == "skip":
                    skipped += 1
                    log.debug("  SKIP   C%-3d  P%-4d", constituency, part)

                elif result == "404":
                    log.info("  404 at part %d — constituency %d complete "
                             "(saved=%d, skipped=%d)", part, constituency, saved, skipped)
                    break

                elif result == "fail":
                    log.error("  FAIL   C%-3d  P%-4d  %s", constituency, part, url)
                    with failed_lock:
                        failed_urls.append(url)
                    # Don't stop on a failed part — try the next one
                    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

            constituency_queue.task_done()
            log.info("◀ Done constituency %d", constituency)

    finally:
        driver.quit()
        # Clean up this worker's temp dir
        shutil.rmtree(temp_dir, ignore_errors=True)
        log.info("Worker %d stopped", worker_id)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log.info("Output root : %s", OUTPUT_DIR.resolve())
    log.info("Constituencies: %d  |  Workers: %d", len(CONSTITUENCIES), NUM_WORKERS)

    # Fill the work queue
    q: queue.Queue = queue.Queue()
    for c in CONSTITUENCIES:
        q.put(c)

    # Launch worker threads
    threads = []
    for i in range(NUM_WORKERS):
        t = threading.Thread(target=worker, args=(i + 1, q), daemon=True)
        t.start()
        threads.append(t)
        time.sleep(1.5)   # Stagger driver startup to avoid Chrome conflicts

    # Wait for all work to finish
    for t in threads:
        t.join()

    # Summary
    log.info("=" * 60)
    log.info("All done.  Failed URLs: %d", len(failed_urls))

    if failed_urls:
        failed_path = OUTPUT_DIR / "failed_urls.txt"
        failed_path.write_text("\n".join(failed_urls), encoding="utf-8")
        log.warning("Failed URLs written to: %s", failed_path)
    else:
        log.info("No failures!")


if __name__ == "__main__":
    main()