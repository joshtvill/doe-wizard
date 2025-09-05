# Environment Setup (PowerShell, Windows)
Version: v1 (2025-08-29)

## Python / Conda
- Target **Python 3.11** for best package compatibility.

```powershell
# Create env
conda create -y -n doe-wizard python=3.11
conda activate doe-wizard

# Install requirements
pip install -r requirements_mvp_v1_20250829.txt

# Verify
python -c "import streamlit, pandas, sklearn, xgboost; print('env ok')"
```

## Run Streamlit (once slices are wired)
```powershell
streamlit run app.py
```

## Common Issues
- DLL load errors → re-install VC++ redistributables; ensure consistent py/numpy versions.
- ImportErrors for GPU packages → use CPU-only wheels (we don't need GPU).
