"""Measure real wall-clock run times of the pipeline stages and the dashboard on THIS machine (MEASURED-IN-PROTOTYPE).

Runs each of generate / train / shadow `--repeats` times via `python -m src.pipeline --stage X`, times dashboard start-to-healthy
(streamlit on a spare port) and the render time of each of the 6 pages (AppTest). Writes reports/ai_runtime_measured.csv.
Outputs of the stages are deterministic, so tracked files should not change (checked by the caller with git status).
Run: python -m src.measure_runtime [--repeats 3]
"""
import argparse
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "ai_runtime_measured.csv"
PAGES = ["p1_live", "p2_combustion", "p3_recs", "p4_whatif", "p5_decisions", "p6_value"]
SCRIPT = "import sys\nsys.path.insert(0, r'{root}')\nfrom src.dashboard import common, {mod}\ncommon.setup()\n{mod}.render()\n"


def timed_stage(stage, repeats):
    walls, rc = [], 0
    for _ in range(repeats):
        t0 = time.perf_counter()
        p = subprocess.run([sys.executable, "-m", "src.pipeline", "--stage", stage], cwd=ROOT, capture_output=True)
        walls.append(time.perf_counter() - t0)
        rc = rc or p.returncode
    return walls, rc


def dashboard_ready(port=8502, timeout=90):
    t0 = time.perf_counter()
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app.py", "--server.port", str(port), "--server.headless", "true"],
                            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok = False
    try:
        while time.perf_counter() - t0 < timeout:
            try:
                if urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=2).read() == b"ok":
                    ok = True
                    break
            except Exception:
                time.sleep(0.25)
        ready = time.perf_counter() - t0
    finally:
        proc.terminate()
        proc.wait(timeout=20)
    return [ready], 0 if ok else 1


def page_renders(repeats):
    from streamlit.testing.v1 import AppTest
    rows = []
    for mod in PAGES:
        walls = []
        for _ in range(repeats):
            t0 = time.perf_counter()
            at = AppTest.from_string(SCRIPT.format(root=ROOT, mod=mod), default_timeout=180).run()
            walls.append(time.perf_counter() - t0)
        rows.append((f"dashboard_render_{mod}", f"AppTest render of {mod}", walls, 1 if at.exception else 0))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repeats", type=int, default=3)
    a = ap.parse_args()
    items = []
    for st in ("generate", "train", "shadow"):
        w, rc = timed_stage(st, a.repeats)
        items.append((st, f"python -m src.pipeline --stage {st}", w, rc))
    w, rc = dashboard_ready()
    items.append(("dashboard_start_to_healthy", "streamlit run app.py (headless) until /_stcore/health = ok", w, rc))
    items += page_renders(a.repeats)
    df = pd.DataFrame([{"step": s, "what": c, "n_runs": len(w), "wall_s_mean": sum(w) / len(w), "wall_s_min": min(w), "wall_s_max": max(w),
                        "exit_code": rc, "label": "MEASURED-IN-PROTOTYPE (wall clock, this PC, wall time not CPU time)"} for s, c, w, rc in items])
    df.round(3).to_csv(OUT, index=False)
    print(df[["step", "n_runs", "wall_s_mean", "wall_s_min", "wall_s_max", "exit_code"]].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
