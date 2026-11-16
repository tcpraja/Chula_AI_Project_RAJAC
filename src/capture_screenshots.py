"""Capture the six dashboard screens to assets/screenshots/screen_1..6.png with a headless Edge/Chrome already installed on this PC.
Starts the app on a spare port, waits for it, takes the shots, stops it. No installs, no network beyond localhost. SYNTHETIC data only.
Run: python -m src.capture_screenshots
"""
import argparse
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "screenshots"
PAGES = ["", "combustion", "recommendations", "whatif", "decisions", "value"]
BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe", "/usr/bin/chromium", "/usr/bin/google-chrome"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8503)
    a = ap.parse_args()
    browser = next((b for b in BROWSERS if Path(b).exists()), None)
    if not browser:
        raise SystemExit("no Edge/Chrome found; take the six screenshots by hand")
    OUT.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app.py", "--server.port", str(a.port), "--server.headless", "true"], cwd=ROOT,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(120):
            try:
                if urllib.request.urlopen(f"http://127.0.0.1:{a.port}/_stcore/health", timeout=2).read() == b"ok":
                    break
            except Exception:
                time.sleep(0.5)
        shot = lambda i, pg: subprocess.run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1500,1900", "--virtual-time-budget=40000",
                                             f"--screenshot={OUT / f'screen_{i}.png'}", f"http://127.0.0.1:{a.port}/{pg}"], capture_output=True, timeout=180)
        shot(1, "")                                   # warm-up: first run loads and caches the data
        for i, pg in enumerate(PAGES, 1):
            prev = None
            for attempt in range(8):                  # accept only when two consecutive captures are byte-identical (page fully rendered)
                shot(i, pg)
                cur = (OUT / f"screen_{i}.png").read_bytes()
                if cur == prev and len(cur) > 100_000:
                    break
                prev = cur
                time.sleep(2)
            print(f"screen_{i}.png", len(cur), "bytes", "(stable)" if cur == prev and len(cur) > 100_000 else "(NOT stable)")
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
