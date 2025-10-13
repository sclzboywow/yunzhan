import os
import sys
import time
import json
import urllib.parse as up
import requests


ENV_PATH = "/opt/web/.env"
BASE = "http://127.0.0.1"


def read_env_value(key: str) -> str:
    if not os.path.exists(ENV_PATH):
        return ""
    val = ""
    with open(ENV_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith(key + "="):
                val = line.split("=", 1)[1].strip().strip("\"").strip("'")
                break
    return val


def main() -> int:
    # Read config
    client_id = read_env_value("APP_BAIDU_CLIENT_ID")
    redirect_uri = read_env_value("APP_BAIDU_REDIRECT_URI") or f"{BASE}/oauth/service/callback"
    admin_secret = read_env_value("APP_ADMIN_SECRET")
    if not client_id or not admin_secret:
        print("Missing APP_BAIDU_CLIENT_ID or APP_ADMIN_SECRET in .env", file=sys.stderr)
        return 1

    # Build service callback with admin_secret in query
    # If redirect_uri already has query, append with &; otherwise, use ?
    parsed = up.urlparse(redirect_uri)
    q = up.parse_qs(parsed.query)
    q["admin_secret"] = [admin_secret]
    new_query = up.urlencode({k: v[0] if isinstance(v, list) else v for k, v in q.items()})
    redirect_with_secret = up.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

    authorize_base = "https://openapi.baidu.com/oauth/2.0/authorize"
    scope = "basic,netdisk"
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_with_secret,
        "scope": scope,
        "display": "page",
    }
    authorize_url = authorize_base + "?" + up.urlencode(params)

    print("authorization_url:", authorize_url)
    print("\n请在浏览器打开上述链接并同意授权，随后我会轮询服务端令牌状态。\n")

    s = requests.Session()
    # Poll service token masked endpoint until has_token true
    deadline = time.time() + 600  # 10 minutes
    while time.time() < deadline:
        try:
            r = s.get(f"{BASE}/oauth/service/token", timeout=5)
            if r.status_code == 200:
                data = r.json()
                if data.get("has_token"):
                    print("service_token_ready:", json.dumps(data))
                    # Quick quota test
                    rq = s.get(f"{BASE}/mcp/public/quota", timeout=10)
                    print("public_quota_status:", rq.status_code)
                    print((rq.text or "")[:400])
                    return 0
                else:
                    print("waiting_auth... (no service token yet)")
            else:
                print("service_token_check_http:", r.status_code)
        except Exception as e:
            print("poll_error:", e)
        time.sleep(5)

    print("timeout: 未在限定时间内完成授权")
    return 1


if __name__ == "__main__":
    sys.exit(main())


