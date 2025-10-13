import json, time, sys
import requests

BASE = 'http://127.0.0.1'
USER = 'tester2'
PASS = 'Admin1234'

s = requests.Session()

def login():
    # ensure register
    s.post(f{BASE}/auth/register, json={username: USER, password: PASS})
    r = s.post(f{BASE}/auth/login, json={username: USER, password: PASS})
    r.raise_for_status()
    token = r.json().get('access_token','')
    if not token:
        print('no token'); sys.exit(1)
    return token


def device_start(token: str):
    r = s.post(f{BASE}/oauth/device/start, headers={Authorization: fBearer
