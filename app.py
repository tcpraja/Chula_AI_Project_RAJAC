"""Heater C advisory dashboard (Phase 5). Run: streamlit run app.py  (SYNTHETIC SIMULATION - NOT FOR PLANT OPERATION)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st  # noqa: E402

from src.dashboard import common, p1_live, p2_combustion, p3_recs, p4_whatif, p5_decisions, p6_value  # noqa: E402

common.setup()
pages = [st.Page(p1_live.render, title="Live Performance", default=True),
         st.Page(p2_combustion.render, title="Combustion Diagnostics", url_path="combustion"),
         st.Page(p3_recs.render, title="AI Recommendations", url_path="recommendations"),
         st.Page(p4_whatif.render, title="What-if Simulator", url_path="whatif"),
         st.Page(p5_decisions.render, title="Operator Decisions", url_path="decisions"),
         st.Page(p6_value.render, title="Business Value", url_path="value")]
st.navigation(pages, position="top").run()
