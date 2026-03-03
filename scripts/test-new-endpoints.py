"""Quick test for new workflow enhancement endpoints."""
import json
import urllib.request
import urllib.error

BASE = "http://localhost/api/v1"

def post_json(url, data):
    req = urllib.request.Request(url, json.dumps(data).encode(), {"Content-Type": "application/json"})
    return urllib.request.urlopen(req)

def get_auth(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, resp.read().decode()[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]

# Login
resp = post_json(f"{BASE}/auth/login", {"email": "admin@jtwolab.kr", "password": "jjlab1234!j"})
token = json.loads(resp.read())["access_token"]
print(f"Login: OK (token={token[:20]}...)")

# Test endpoints
endpoints = [
    ("GET", "/settlements/", "Settlements list"),
    ("GET", "/settlements/by-handler", "Settlements by handler"),
    ("GET", "/settlements/by-company", "Settlements by company"),
    ("GET", "/settlements/by-date", "Settlements by date"),
    ("GET", "/assignment/queue", "Assignment queue"),
    ("GET", "/orders/sub-account-pending", "Sub-account pending"),
    ("GET", "/places/recommend?place_url=https://m.place.naver.com/restaurant/12345&company_id=1", "Places recommend"),
]

for method, path, name in endpoints:
    status, body = get_auth(f"{BASE}{path}", token)
    result = "PASS" if status == 200 else f"FAIL({status})"
    print(f"  {result} {name}: {status} - {body[:100]}")

print("\nDone!")
