# Start the Heater C advisory dashboard (SYNTHETIC SIMULATION - NOT FOR PLANT OPERATION). Opens http://localhost:8501
Set-Location -Path $PSScriptRoot
& "$PSScriptRoot\.venv\Scripts\Activate.ps1"
streamlit run app.py --server.port 8501
