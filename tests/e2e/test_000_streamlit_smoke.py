import os
import subprocess
import sys
import time
import pathlib

def test_streamlit_app_boots_quickly():
    app_path = pathlib.Path("app.py")
    assert app_path.exists(), "app.py not found at repo root"
    cmd = [sys.executable, "-m", "streamlit", "run", "app.py", "--server.headless", "true", "--server.port", "8799"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        time.sleep(6)
        assert proc.poll() is None, "Streamlit exited prematurely"
    finally:
        proc.terminate()