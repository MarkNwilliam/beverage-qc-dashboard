"""Capture polished screenshots of the running Streamlit dashboard for the README.

Requires the Streamlit server to be running (e.g. streamlit run dashboard/app.py
--server.port 8611) and Playwright with chromium installed. Run:

    python tests/capture_screenshots.py

Writes PNGs to docs/screenshots/.
"""

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

BASE = "http://localhost:8611"

# (sidebar page label, output filename, sleep seconds for charts)
PAGES = [
    ("Overview", "overview.png", 6),
    ("Batch Testing", "batch_testing.png", 6),
    ("SPC Control Charts", "spc_control_charts.png", 7),
    ("Calibration", "calibration.png", 5),
    ("HACCP", "haccp.png", 5),
    ("Audit & CAPA", "audit.png", 5),
]


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            channel="chrome",
            args=["--no-sandbox", "--hide-scrollbars"],
        )
        page = browser.new_page(viewport={"width": 1500, "height": 950})
        page.goto(BASE, wait_until="networkidle", timeout=60000)
        time.sleep(4)  # let the first chart render

        for label, fname, wait in PAGES:
            # Intercept the sidebar radio to click the target nav item.
            # Streamlit renders nav as radio buttons; we target by visible label text.
            try:
                page.get_by_text(label, exact=True).first.click(timeout=15000)
            except Exception as e:
                print(f"  [!] could not click '{label}': {e}")
            time.sleep(wait)
            page.wait_for_timeout(500)
            page.screenshot(path=str(OUT / fname), full_page=False)
            print(f"  captured docs/screenshots/{fname}")

        # a full-page scroll capture of Overview top for a hero
        page.get_by_text("Overview", exact=True).first.click(timeout=15000)
        time.sleep(6)
        page.screenshot(path=str(OUT / "overview_full.png"), full_page=True)
        print("  captured docs/screenshots/overview_full.png")

        browser.close()


if __name__ == "__main__":
    main()
