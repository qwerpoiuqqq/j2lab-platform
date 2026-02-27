#!/usr/bin/env python3
"""Clean up leftover test data from API tests."""
import urllib.request, json

BASE = "http://localhost:8000/api/v1"

def call(method, path, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req)
        raw = resp.read().decode("utf-8", errors="replace")
        return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return 0, str(e)

# Login
code, d = call("POST", "/auth/login", {"email": "admin@jtwolab.kr", "password": "jjlab1234!j"})
print("Login:", code)
token = d.get("access_token", "") if isinstance(d, dict) else ""
if not token:
    print("No token, abort")
    exit(1)

# Clean orders that reference __tp__ product first
code, d = call("GET", "/products/?size=200", token=token)
tp_ids = []
if isinstance(d, dict):
    for p in d.get("items", []):
        if p.get("code") == "__tp__":
            tp_ids.append(p["id"])

# Find and cancel/delete orders
if tp_ids:
    code, d = call("GET", "/orders/?size=500", token=token)
    if isinstance(d, dict):
        for o in d.get("items", []):
            order_id = o.get("id")
            # Cancel draft/submitted orders first
            if o.get("status") in ("draft", "submitted"):
                dc, _ = call("POST", "/orders/" + str(order_id) + "/cancel", token=token)
                print("  Cancel order", order_id, ":", dc)

# Delete test products
for pid in tp_ids:
    print("Deleting product __tp__ id=", pid)
    dc, _ = call("DELETE", "/products/" + str(pid), token=token)
    print("  Result:", dc)

# Clean companies
code, d = call("GET", "/companies/", token=token)
if isinstance(d, dict):
    for c in d.get("items", []):
        if c.get("code") == "__test_co__":
            cid = c["id"]
            print("Deleting company __test_co__ id=", cid)
            dc, _ = call("DELETE", "/companies/" + str(cid), token=token)
            print("  Result:", dc)

print("Done")
