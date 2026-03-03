#!/usr/bin/env python3
"""Seed extra data: missing products, sub_account user, role-based prices."""
import urllib.request, json, sys

BASE = "http://localhost:8000/api/v1"

def api(method, path, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req)
        raw = resp.read().decode()
        return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read().decode() if e.fp else ""
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw

# Login
code, d = api("POST", "/auth/login", {"email": "admin@jtwolab.kr", "password": "jjlab1234!j"})
if code != 200:
    print("Login failed:", d)
    sys.exit(1)
TOKEN = d["access_token"]
print("Logged in as admin")

# Standard schema
SCHEMA = [
    {"name": "place_url", "label": "플레이스 URL", "type": "url", "required": True, "color": "#4472C4"},
    {"name": "campaign_type", "label": "캠페인 유형", "type": "select", "required": True, "options": ["traffic", "save"], "color": "#00B050"},
    {"name": "duration_days", "label": "기간(일)", "type": "number", "required": True, "color": "#FFC000"},
    {"name": "daily_limit", "label": "일일 한도", "type": "number", "required": True, "color": "#FF6B35"},
    {"name": "total_limit", "label": "총 한도", "type": "number", "required": True, "color": "#4472C4", "is_quantity": True},
    {"name": "place_name", "label": "업체명", "type": "text", "required": False, "color": "#333D4B"},
]

# Check existing
code, d = api("GET", "/products/?size=50", token=TOKEN)
existing_codes = set()
for p in d.get("items", []):
    existing_codes.add(p["code"])
print("Existing product codes:", existing_codes)

# Create missing products
new_products = [
    {"name": "저장 30일", "code": "save_30", "category": "저장", "base_price": 250000},
    {"name": "트래픽 60일", "code": "traffic_60", "category": "트래픽", "base_price": 550000},
    {"name": "저장 60일", "code": "save_60", "category": "저장", "base_price": 450000},
]

for p in new_products:
    if p["code"] in existing_codes:
        print("SKIP product:", p["name"])
        continue
    payload = dict(p)
    payload["form_schema"] = SCHEMA
    code, d = api("POST", "/products/", payload, token=TOKEN)
    if code == 201:
        print("Created product:", p["name"], "id=", d["id"])
    else:
        print("FAIL product:", p["name"], code, str(d)[:80])

# Get company ID for j2lab
code, d = api("GET", "/companies/", token=TOKEN)
j2lab_id = None
for c in d.get("items", []):
    if c["code"] == "j2lab":
        j2lab_id = c["id"]
        break
print("j2lab company_id:", j2lab_id)

# Check existing users
code, d = api("GET", "/users/?size=100", token=TOKEN)
existing_emails = set()
for u in d.get("items", []):
    existing_emails.add(u["email"])

# Create sub_account user
if "seller1@jtwolab.kr" not in existing_emails:
    code, d = api("POST", "/users/", {
        "email": "seller1@jtwolab.kr",
        "password": "seller1234!",
        "name": "j2lab 셀러",
        "role": "sub_account",
        "company_id": j2lab_id,
    }, token=TOKEN)
    if code == 201:
        print("Created user: j2lab 셀러 (sub_account), id=", d["id"])
    else:
        print("FAIL user:", code, str(d)[:80])
else:
    print("SKIP user: seller1@jtwolab.kr exists")

# Create role-based price policies for all active products
code, d = api("GET", "/products/?size=50&is_active=true", token=TOKEN)
active_products = d.get("items", [])

for p in active_products:
    pid = p["id"]
    bp = p["base_price"]

    # Check existing policies
    code2, d2 = api("GET", "/products/" + str(pid) + "/prices?size=50", token=TOKEN)
    existing_roles = set()
    if isinstance(d2, dict):
        for pol in d2.get("items", []):
            if pol.get("role"):
                existing_roles.add(pol["role"])

    for role, pct in [("distributor", 0.85), ("sub_account", 0.90)]:
        if role in existing_roles:
            print("SKIP price:", p["name"], role)
            continue
        price = int(bp * pct)
        code3, d3 = api("POST", "/products/" + str(pid) + "/prices", {
            "product_id": pid,
            "role": role,
            "unit_price": price,
            "effective_from": "2026-01-01",
        }, token=TOKEN)
        if code3 == 201:
            print("Created price:", p["name"], role, "=", price)
        else:
            print("FAIL price:", p["name"], role, code3, str(d3)[:80])

# Final verification
print()
print("=== FINAL STATE ===")
code, d = api("GET", "/products/?size=50&is_active=true", token=TOKEN)
items = d.get("items", [])
print("Active products:", len(items))
for p in items:
    print("  ", p["name"], "(" + p["code"] + ")", "cat=" + str(p.get("category")), "price=" + str(p["base_price"]))

code, d = api("GET", "/products/prices/user-matrix", token=TOKEN)
print("Users:", len(d.get("users", [])))
for u in d.get("users", []):
    role = u["role"]
    up = d["prices"].get(u["id"], {})
    print("  ", u["name"], "(" + role + ")", len(up), "prices")

print()
print("SEED COMPLETE")
