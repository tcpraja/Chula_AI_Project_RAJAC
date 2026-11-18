"""Streamlit Community Cloud entry point (SYNTHETIC SIMULATION - NOT FOR PLANT OPERATION).

Set "Main file path" to deploy/streamlit_app.py. Streamlit Cloud then installs deploy/requirements.txt (lean, pinned
dashboard runtime) instead of the root requirements.txt (dev + document-building tools). This file only runs app.py.
"""
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

runpy.run_path(str(ROOT / "app.py"), run_name="__main__")
