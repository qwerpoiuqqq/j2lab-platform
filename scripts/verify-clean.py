#!/usr/bin/env python3
"""Verify clean database state after data reset."""
import urllib.request, json

BASE = "http://localhost:8000/api/v1"

def api(method, path, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 0, None

# Login
c, d = api("POST", "/auth/login", {"email": "admin@jtwolab.kr", "password": "jjlab1234!j"})
token = d.get("access_token", "") if isinstance(d, dict) else ""
print("Login:", "OK" if token else "FAIL")

if not token:
    exit(1)

# Check each endpoint
checks = [
    ("/users/me", "Admin user"),
    ("/companies/", "Companies"),
    ("/users/", "Users"),
    ("/orders/", "Orders"),
    ("/campaigns/", "Campaigns"),
    ("/products/", "Products"),
    ("/categories/", "Categories"),
    ("/campaign_templates/", "Templates"),
    ("/settlements/", "Settlements"),
    ("/superap-accounts/", "Superap"),
    ("/dashboard/summary", "Dashboard"),
    ("/notifications/", "Notifications"),
]

print("\n=== Clean State Verification ===")
for path, label in checks:
    c, d = api("GET", path, token=token)
    if isinstance(d, dict):
        total = d.get("total", "")
        name = d.get("name", "")
        items = len(d.get("items", [])) if "items" in d else ""
        extra = str(total or items or name or "ok")
    else:
        extra = str(c)
    print("  {:20s} {:30s} -> {} ({})".format(label, path, c, extra))

print("\nExpected: 1 user, 1 company, 0 orders/campaigns/products, 4 categories, 3 templates")
print("Done!")
