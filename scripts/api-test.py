#!/usr/bin/env python3
"""Comprehensive API CRUD test for J2LAB platform."""
import urllib.request, json, sys

BASE = "http://localhost:8000/api/v1"
PASS = 0
FAIL = 0
RESULTS = []

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

def test(name, code, expected, detail=""):
    global PASS, FAIL
    exp_list = expected if isinstance(expected, (list, tuple)) else [expected]
    ok = code in exp_list
    status = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    d = f" ({detail})" if detail else ""
    print(f"  [{status}] {name} -> {code}{d}")
    RESULTS.append((status, name, code, detail))
    return ok

def detail_of(d, code):
    if isinstance(d, dict):
        return str(d)[:80]
    return str(d)[:80]

# ============================================================
print("=" * 60)
print("1. AUTH")
code, d = api("POST", "/auth/login", {"email": "admin@jtwolab.kr", "password": "jjlab1234!j"})
test("Login admin", code, 200, "token obtained" if code == 200 else detail_of(d, code))
TOKEN = d.get("access_token", "") if isinstance(d, dict) else ""
if not TOKEN:
    print("  ABORT: no token")
    sys.exit(1)

code, d = api("POST", "/auth/login", {"email": "wrong@x.com", "password": "wrong"})
test("Login invalid creds", code, 401)

code, d = api("GET", "/auth/me", token=TOKEN)
test("GET /auth/me", code, 200, d.get("name", "?") if isinstance(d, dict) else "")

# ============================================================
print("\n" + "=" * 60)
print("2. COMPANIES")
code, d = api("GET", "/companies/", token=TOKEN)
test("List companies", code, 200, f"{d.get('total', 0)} items" if isinstance(d, dict) else "")

# ============================================================
print("\n" + "=" * 60)
print("3. USERS")
code, d = api("GET", "/users/", token=TOKEN)
test("List users", code, 200, f"{d.get('total', 0)} items" if isinstance(d, dict) else "")

code, d = api("GET", "/users/?role=distributor", token=TOKEN)
test("List distributors", code, 200, f"{d.get('total', 0)} items" if isinstance(d, dict) else "")

code, d = api("GET", "/users/?role=sub_account", token=TOKEN)
test("List sub_accounts", code, 200, f"{d.get('total', 0)} items" if isinstance(d, dict) else "")

# ============================================================
print("\n" + "=" * 60)
print("4. CATEGORIES CRUD")
code, d = api("GET", "/categories/", token=TOKEN)
test("List categories", code, 200, f"{d.get('total', 0)} items" if isinstance(d, dict) else "")

code, d = api("POST", "/categories/", {"name": "__TEST__", "icon": "star", "description": "api test"}, token=TOKEN)
test("Create category", code, 201, f"id={d.get('id')}" if code == 201 else detail_of(d, code))
tc_id = d.get("id") if code == 201 else None

if tc_id:
    code, d = api("PUT", f"/categories/{tc_id}", {"name": "__TEST_UPD__", "icon": "tag"}, token=TOKEN)
    test("Update category", code, 200, f"icon={d.get('icon')}" if code == 200 else detail_of(d, code))

    code, d = api("POST", "/categories/reorder", {"items": [{"id": tc_id, "sort_order": 99}]}, token=TOKEN)
    test("Reorder categories", code, 200)

    code, d = api("DELETE", f"/categories/{tc_id}", token=TOKEN)
    test("Delete category", code, 204)

# ============================================================
print("\n" + "=" * 60)
print("5. PRODUCTS CRUD")
code, d = api("GET", "/products/", token=TOKEN)
test("List products", code, 200, f"{d.get('total', 0)} items" if isinstance(d, dict) else "")

code, d = api("POST", "/products/", {
    "name": "__TEST_PROD__", "code": "__tp__", "base_price": 100000, "category": "traffic",
    "form_schema": [
        {"name": "f1", "label": "Field1", "type": "text", "required": True, "color": "#4472C4"},
        {"name": "qty", "label": "Qty", "type": "number", "required": True, "is_quantity": True},
    ]
}, token=TOKEN)
test("Create product", code, 201, f"id={d.get('id')}" if code == 201 else detail_of(d, code))
tp_id = d.get("id") if code == 201 else None

if tp_id:
    code, d = api("GET", f"/products/{tp_id}", token=TOKEN)
    test("Get product by ID", code, 200)

    code, d = api("PATCH", f"/products/{tp_id}", {"name": "__TEST_UPD__", "base_price": 150000}, token=TOKEN)
    test("Update product", code, 200, f"price={d.get('base_price')}" if code == 200 else detail_of(d, code))

    code, d = api("GET", f"/products/{tp_id}/schema", token=TOKEN)
    fs = d.get("form_schema", []) if isinstance(d, dict) else []
    test("Get product schema", code, 200, f"fields={len(fs)}, type={type(fs).__name__}")

    # Price policies
    code, d = api("POST", f"/products/{tp_id}/prices", {
        "product_id": tp_id, "role": "distributor", "unit_price": 85000, "effective_from": "2026-01-01"
    }, token=TOKEN)
    test("Create role price policy", code, 201)
    rp_id = d.get("id") if code == 201 else None

    code, d = api("POST", f"/products/{tp_id}/prices", {
        "product_id": tp_id, "user_id": "9fbba161-3e16-46ef-a821-70b6843036a6",
        "unit_price": 80000, "effective_from": "2026-01-01"
    }, token=TOKEN)
    test("Create user price policy", code, 201)
    up_id = d.get("id") if code == 201 else None

    code, d = api("GET", f"/products/{tp_id}/prices", token=TOKEN)
    test("List price policies", code, 200, f"{d.get('total', 0)} policies" if isinstance(d, dict) else "")

    # Cleanup
    if rp_id:
        code, d = api("DELETE", f"/products/prices/{rp_id}", token=TOKEN)
        test("Delete role policy", code, 204)
    if up_id:
        code, d = api("DELETE", f"/products/prices/{up_id}", token=TOKEN)
        test("Delete user policy", code, 204)
    code, d = api("DELETE", f"/products/{tp_id}", token=TOKEN)
    test("Delete product", code, 204)

# ============================================================
print("\n" + "=" * 60)
print("6. PRICE MATRIX")
code, d = api("GET", "/products/prices/matrix", token=TOKEN)
test("Role-based matrix", code, 200, f"rows={len(d.get('rows', []))}" if isinstance(d, dict) else "")

code, d = api("GET", "/products/prices/user-matrix", token=TOKEN)
test("User-based matrix", code, 200, f"users={len(d.get('users', []))}, prods={len(d.get('products', []))}" if isinstance(d, dict) else detail_of(d, code))

# ============================================================
print("\n" + "=" * 60)
print("7. ORDERS")
code, d = api("GET", "/orders/", token=TOKEN)
test("List orders", code, 200, f"{d.get('total', 0)} items" if isinstance(d, dict) else "")

# ============================================================
print("\n" + "=" * 60)
print("8. DASHBOARD")
code, d = api("GET", "/dashboard/summary", token=TOKEN)
test("Dashboard summary", code, 200)

code, d = api("GET", "/dashboard/enhanced", token=TOKEN)
test("Dashboard enhanced", code, 200)

code, d = api("GET", "/dashboard/calendar", token=TOKEN)
test("Dashboard calendar", code, [200, 404])

# ============================================================
print("\n" + "=" * 60)
print("9. NOTIFICATIONS")
code, d = api("GET", "/notifications/", token=TOKEN)
test("List notifications", code, 200)

# ============================================================
print("\n" + "=" * 60)
print("10. NOTICES")
code, d = api("GET", "/notices/", token=TOKEN)
test("List notices", code, 200, f"{d.get('total', 0)} items" if isinstance(d, dict) else "")

code, d = api("POST", "/notices/", {"title": "API_TEST", "content": "test"}, token=TOKEN)
test("Create notice", code, 201)
tn_id = d.get("id") if code == 201 else None
if tn_id:
    code, d = api("PUT", f"/notices/{tn_id}", {"title": "API_TEST_UPD"}, token=TOKEN)
    test("Update notice", code, [200, 405], detail_of(d, code) if code != 200 else "")
    code, d = api("DELETE", f"/notices/{tn_id}", token=TOKEN)
    test("Delete notice", code, 204)

# ============================================================
print("\n" + "=" * 60)
print("11. SETTLEMENTS")
code, d = api("GET", "/settlements/", token=TOKEN)
test("List settlements", code, [200, 404])

# ============================================================
print("\n" + "=" * 60)
print("12. CAMPAIGNS")
code, d = api("GET", "/campaigns/", token=TOKEN)
test("List campaigns", code, [200, 404], f"{d.get('total', 0)} items" if isinstance(d, dict) and code == 200 else "")

# ============================================================
print("\n" + "=" * 60)
print("13. ASSIGNMENT")
code, d = api("GET", "/assignment/queue", token=TOKEN)
test("Assignment queue", code, 200)

# ============================================================
print("\n" + "=" * 60)
print("14. BALANCE")
code, d = api("GET", "/balance/transactions", token=TOKEN)
test("Balance transactions", code, [200, 404])

# ============================================================
print("\n" + "=" * 60)
total = PASS + FAIL
print(f"RESULTS: {total} tests | {PASS} PASSED | {FAIL} FAILED")
if FAIL > 0:
    print("\nFAILURES:")
    for s, name, c, det in RESULTS:
        if s == "FAIL":
            print(f"  {name} -> {c} {det}")
sys.exit(0 if FAIL == 0 else 1)
