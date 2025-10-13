#!/usr/bin/env python3
import json
import sys
import urllib.request

def main() -> None:
    url = "http://127.0.0.1:8000/auth/login"
    payload = {"username": "string", "password": "string"}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "accept": "application/json",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read()
    token = json.loads(body.decode("utf-8")).get("access_token", "")
    print(token)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"", end="")
        sys.exit(1)


