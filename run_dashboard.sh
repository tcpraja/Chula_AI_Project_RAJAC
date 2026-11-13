#!/usr/bin/env bash
# Start the Heater C advisory dashboard (SYNTHETIC SIMULATION - NOT FOR PLANT OPERATION). Opens http://localhost:8501
cd "$(dirname "$0")" || exit 1
if [ -f .venv/Scripts/activate ]; then . .venv/Scripts/activate; elif [ -f .venv/bin/activate ]; then . .venv/bin/activate; fi
streamlit run app.py --server.port 8501
