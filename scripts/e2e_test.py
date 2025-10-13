import json
import sys
import time

import requests


BASE = "http://127.0.0.1"


def main() -> int:
    s = requests.Session()
    # 1) health
    r = s.get(f"{BASE}/health", timeout=5)
    print("health:", r.status_code, r.text)

    # 2) register
    payload = {"username": "tester2", "password": "Admin1234"}
    r = s.post(f"{BASE}/auth/register", json=payload, timeout=10)
    print("register:", r.status_code, r.text)

    # 3) login
    r = s.post(f"{BASE}/auth/login", json=payload, timeout=10)
    print("login:", r.status_code, r.text)
    token = ""
    try:
        token = r.json().get("access_token", "")
    except Exception:
        pass
    print("token_len:", len(token))
    if not token:
        return 1

    headers = {"Authorization": f"Bearer {token}"}

    # 4) oauth device start
    r = s.post(f"{BASE}/oauth/device/start", headers=headers, timeout=10)
    print("device_start:", r.status_code, r.text)

    # 5) token masked
    r = s.get(f"{BASE}/oauth/token", headers=headers, timeout=10)
    print("token_masked:", r.status_code, r.text)

    # 6) mcp quota (may fail if not authorized)
    try:
        r = s.get(f"{BASE}/mcp/quota", headers=headers, timeout=10)
        print("mcp_quota:", r.status_code, r.text[:200])
    except Exception as e:
        print("mcp_quota error:", e)

    return 0


if __name__ == "__main__":
    sys.exit(main())


