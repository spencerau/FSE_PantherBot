import subprocess
import time
import requests

def test_mcp_server_health():
    proc = subprocess.Popen(["python3", "-m", "src.mcp.server"])
    time.sleep(2)
    try:
        resp = requests.post("http://127.0.0.1:8765/tools/call", json={"tool": "health_check", "input": {}})
        assert resp.json()["ok"] is True
    finally:
        proc.terminate()
