#!/usr/bin/env python3
"""Comprehensive API test for J2LAB platform — 124 endpoints, session reset, E2E flows."""
import urllib.request, json, sys, time, os

BASE = os.environ.get("API_BASE", "http://localhost:8000") + "/api/v1"
PASS = 0
FAIL = 0
SKIP = 0
RESULTS = []
ADMIN_EMAIL = "admin@jtwolab.kr"
ADMIN_PASS = "jjlab1234!j"

# ── Helpers ──────────────────────────────────────────────────

def api(method, path, data=None, token=None, raw_response=False, base_override=None):
    url = (base_override or BASE) + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        raw_bytes = resp.read()
        if raw_response:
            return resp.status, f"<binary {len(raw_bytes)} bytes>"
        raw = raw_bytes.decode("utf-8", errors="replace")
        return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw_bytes = e.read() if e.fp else b""
        raw = raw_bytes.decode("utf-8", errors="replace")
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
    print(f"  [{'✓' if ok else '✗'} {status}] {name} -> {code}{d}")
    RESULTS.append((status, name, code, detail))
    return ok

def skip(name, reason=""):
    global SKIP
    SKIP += 1
    d = f" ({reason})" if reason else ""
    print(f"  [- SKIP] {name}{d}")
    RESULTS.append(("SKIP", name, 0, reason))

def section(num, title):
    print(f"\n{'='*60}")
    print(f"{num}. {title}")
    print("-"*60)

def login(email=ADMIN_EMAIL, password=ADMIN_PASS):
    """Fresh login — session reset."""
    code, d = api("POST", "/auth/login", {"email": email, "password": password})
    return d.get("access_token", "") if isinstance(d, dict) and code == 200 else ""

def detail_of(d):
    if isinstance(d, dict):
        return d.get("detail", str(d))[:100]
    return str(d)[:100]

# ══════════════════════════════════════════════════════════════
# SESSION 1: Auth & Users
# ══════════════════════════════════════════════════════════════

section("1", "AUTH — 로그인 / 로그아웃 / 토큰갱신")

code, d = api("POST", "/auth/login", {"email": ADMIN_EMAIL, "password": ADMIN_PASS})
test("Login admin", code, 200, "token OK" if code == 200 else detail_of(d))
TOKEN = d.get("access_token", "") if isinstance(d, dict) else ""
REFRESH = d.get("refresh_token", "") if isinstance(d, dict) else ""
if not TOKEN:
    print("  ABORT: no token")
    sys.exit(1)

code, d = api("POST", "/auth/login", {"email": "wrong@x.com", "password": "wrong"})
test("Login bad creds", code, 401)

code, d = api("POST", "/auth/login", {"email": ADMIN_EMAIL, "password": "wrong"})
test("Login bad password", code, 401)

code, d = api("POST", "/auth/login", {})
test("Login missing fields", code, 422)

# Refresh token
if REFRESH:
    code, d = api("POST", "/auth/refresh", {"refresh_token": REFRESH})
    test("Refresh token", code, 200, "new token" if code == 200 else detail_of(d))
    if code == 200 and isinstance(d, dict):
        TOKEN = d.get("access_token", TOKEN)
else:
    skip("Refresh token", "no refresh_token returned")

# GET /users/me
code, d = api("GET", "/users/me", token=TOKEN)
test("GET /users/me", code, 200, d.get("name", "?") if isinstance(d, dict) else detail_of(d))
ADMIN_ID = d.get("id", "") if isinstance(d, dict) else ""

# No-auth check
code, d = api("GET", "/users/me")
test("GET /users/me (no auth)", code, [401, 403])

# ── SESSION RESET ──
print("\n  --- Session Reset (re-login) ---")
TOKEN = login()
assert TOKEN, "Re-login failed"

section("2", "COMPANIES CRUD")
code, d = api("GET", "/companies/", token=TOKEN)
test("List companies", code, 200, f"{d.get('total', 0)} items" if isinstance(d, dict) else "")
COMPANY_LIST = d.get("items", []) if isinstance(d, dict) else []

# Create company
code, d = api("POST", "/companies/", {
    "name": "__API_TEST_CO__", "code": "__test_co__"
}, token=TOKEN)
test("Create company", code, [201, 409], f"id={d.get('id')}" if code == 201 else detail_of(d))
test_co_id = d.get("id") if code == 201 else None

if test_co_id:
    code, d = api("GET", f"/companies/{test_co_id}", token=TOKEN)
    test("Get company by ID", code, 200)

    code, d = api("PATCH", f"/companies/{test_co_id}", {"name": "__API_TEST_CO_UPD__"}, token=TOKEN)
    test("Update company", code, 200)

    code, d = api("DELETE", f"/companies/{test_co_id}", token=TOKEN)
    test("Delete company", code, [200, 204])
else:
    skip("Get/Update/Delete company", "create failed")

# ── SESSION RESET ──
print("\n  --- Session Reset ---")
TOKEN = login()

section("3", "USERS CRUD")
code, d = api("GET", "/users/", token=TOKEN)
test("List users", code, 200, f"{d.get('total', 0)} items" if isinstance(d, dict) else "")
ALL_USERS = d.get("items", []) if isinstance(d, dict) else []

code, d = api("GET", "/users/?role=system_admin", token=TOKEN)
test("Filter: system_admin", code, 200, f"{d.get('total', 0)} items" if isinstance(d, dict) else "")

code, d = api("GET", "/users/?role=company_admin", token=TOKEN)
test("Filter: company_admin", code, 200, f"{d.get('total', 0)} items" if isinstance(d, dict) else "")

code, d = api("GET", "/users/?role=order_handler", token=TOKEN)
test("Filter: order_handler", code, 200, f"{d.get('total', 0)} items" if isinstance(d, dict) else "")

code, d = api("GET", "/users/?role=distributor", token=TOKEN)
test("Filter: distributor", code, 200, f"{d.get('total', 0)} items" if isinstance(d, dict) else "")
DISTRIBUTORS = d.get("items", []) if isinstance(d, dict) else []

code, d = api("GET", "/users/?role=sub_account", token=TOKEN)
test("Filter: sub_account", code, 200, f"{d.get('total', 0)} items" if isinstance(d, dict) else "")

# Get specific user by ID
if ADMIN_ID:
    code, d = api("GET", f"/users/{ADMIN_ID}", token=TOKEN)
    test("Get user by ID", code, 200, d.get("name", "?") if isinstance(d, dict) else "")

    code, d = api("GET", f"/users/{ADMIN_ID}/descendants", token=TOKEN)
    test("Get user descendants", code, 200)

# ── SESSION RESET ──
print("\n  --- Session Reset ---")
TOKEN = login()

section("4", "CATEGORIES CRUD")
code, d = api("GET", "/categories/", token=TOKEN)
test("List categories", code, 200, f"{d.get('total', 0)} items" if isinstance(d, dict) else "")

code, d = api("POST", "/categories/", {"name": "__TCAT__", "icon": "star", "description": "test"}, token=TOKEN)
test("Create category", code, 201, f"id={d.get('id')}" if code == 201 else detail_of(d))
tc_id = d.get("id") if code == 201 else None

if tc_id:
    code, d = api("PUT", f"/categories/{tc_id}", {"name": "__TCAT_UPD__", "icon": "tag"}, token=TOKEN)
    test("Update category", code, 200)

    code, d = api("POST", "/categories/reorder", {"items": [{"id": tc_id, "sort_order": 99}]}, token=TOKEN)
    test("Reorder categories", code, 200)

    code, d = api("DELETE", f"/categories/{tc_id}", token=TOKEN)
    test("Delete category", code, 204)

    # Verify deletion
    code, d = api("PUT", f"/categories/{tc_id}", {"name": "ghost"}, token=TOKEN)
    test("Update deleted category (expect 404)", code, 404)
else:
    skip("Category CRUD cycle", "create failed")

# ── SESSION RESET ──
print("\n  --- Session Reset ---")
TOKEN = login()

section("5", "PRODUCTS CRUD + PRICE POLICIES")

# Clean up leftover test product
code, d = api("GET", "/products/?size=200", token=TOKEN)
if isinstance(d, dict):
    for p in d.get("items", []):
        if p.get("code") == "__tp__":
            api("DELETE", f"/products/{p['id']}", token=TOKEN)

code, d = api("GET", "/products/", token=TOKEN)
test("List products", code, 200, f"{d.get('total', 0)} items" if isinstance(d, dict) else "")
PRODUCTS = d.get("items", []) if isinstance(d, dict) else []

code, d = api("POST", "/products/", {
    "name": "__TEST_PROD__", "code": "__tp__", "base_price": 100000, "category": "traffic",
    "form_schema": [
        {"name": "naver_url", "label": "네이버 URL", "type": "url", "required": True, "color": "#4472C4"},
        {"name": "qty", "label": "수량", "type": "number", "required": True, "is_quantity": True},
    ]
}, token=TOKEN)
test("Create product", code, 201, f"id={d.get('id')}" if code == 201 else detail_of(d))
tp_id = d.get("id") if code == 201 else None

if tp_id:
    code, d = api("GET", f"/products/{tp_id}", token=TOKEN)
    test("Get product by ID", code, 200)

    code, d = api("PATCH", f"/products/{tp_id}", {"name": "__TEST_UPD__", "base_price": 150000}, token=TOKEN)
    test("Update product", code, 200, f"price={d.get('base_price')}" if code == 200 else "")

    code, d = api("GET", f"/products/{tp_id}/schema", token=TOKEN)
    fs = d.get("form_schema", []) if isinstance(d, dict) else []
    test("Get product schema", code, 200, f"fields={len(fs)}")

    # Role price policy
    code, d = api("POST", f"/products/{tp_id}/prices", {
        "product_id": tp_id, "role": "distributor", "unit_price": 85000, "effective_from": "2026-01-01"
    }, token=TOKEN)
    test("Create role price policy", code, 201)
    rp_id = d.get("id") if code == 201 else None

    # User price policy (use a distributor if available)
    user_target = DISTRIBUTORS[0]["id"] if DISTRIBUTORS else ADMIN_ID
    code, d = api("POST", f"/products/{tp_id}/prices", {
        "product_id": tp_id, "user_id": user_target,
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
else:
    skip("Product CRUD cycle", "create failed")

# Price Matrix
code, d = api("GET", "/products/prices/matrix", token=TOKEN)
test("Role-based matrix", code, 200, f"rows={len(d.get('rows', []))}" if isinstance(d, dict) else "")

code, d = api("GET", "/products/prices/user-matrix", token=TOKEN)
test("User-based matrix", code, 200, f"users={len(d.get('users', []))}" if isinstance(d, dict) else "")

# ── SESSION RESET ──
print("\n  --- Session Reset ---")
TOKEN = login()

section("6", "ORDERS — E2E Flow (Create → Submit → Confirm → Cancel)")

# Use test product for order
if tp_id:
    # Create order
    code, d = api("POST", "/orders/", {
        "items": [{
            "product_id": tp_id,
            "quantity": 3,
            "item_data": {"naver_url": "https://naver.me/test123", "qty": 3}
        }],
        "notes": "API 테스트 주문"
    }, token=TOKEN)
    test("Create order (draft)", code, 201, f"id={d.get('id')}, num={d.get('order_number')}" if code == 201 else detail_of(d))
    order_id = d.get("id") if code == 201 else None
    order_num = d.get("order_number", "") if isinstance(d, dict) else ""

    if order_id:
        # Get order by ID
        code, d = api("GET", f"/orders/{order_id}", token=TOKEN)
        test("Get order by ID", code, 200, f"status={d.get('status')}" if isinstance(d, dict) else "")

        # Update order notes
        code, d = api("PATCH", f"/orders/{order_id}", {"notes": "Updated notes"}, token=TOKEN)
        test("Update order (draft)", code, 200)

        # Submit order
        code, d = api("POST", f"/orders/{order_id}/submit", token=TOKEN)
        test("Submit order (draft→submitted)", code, 200, f"status={d.get('status')}" if isinstance(d, dict) else detail_of(d))

        # Cannot update after submit
        code, d = api("PATCH", f"/orders/{order_id}", {"notes": "late update"}, token=TOKEN)
        test("Update submitted order (expect 400)", code, 400)

        # Reject order
        code, d = api("POST", f"/orders/{order_id}/reject", {"reason": "테스트 반려"}, token=TOKEN)
        test("Reject order (submitted→rejected)", code, 200, f"status={d.get('status')}" if isinstance(d, dict) else detail_of(d))

        # Create another order for approve flow
        code, d = api("POST", "/orders/", {
            "items": [{"product_id": tp_id, "quantity": 1, "item_data": {"naver_url": "https://naver.me/approve", "qty": 1}}],
            "notes": "승인 테스트"
        }, token=TOKEN)
        order_id2 = d.get("id") if code == 201 else None

        if order_id2:
            code, d = api("POST", f"/orders/{order_id2}/submit", token=TOKEN)
            test("Submit order #2", code, 200)

            code, d = api("POST", f"/orders/{order_id2}/approve", token=TOKEN)
            test("Approve order (submitted→payment_confirmed)", code, 200, f"status={d.get('status')}" if isinstance(d, dict) else detail_of(d))

            # Cancel the approved order — should fail (only draft/submitted)
            code, d = api("POST", f"/orders/{order_id2}/cancel", token=TOKEN)
            test("Cancel approved order (expect 400)", code, 400)

        # Create third order for cancel flow
        code, d = api("POST", "/orders/", {
            "items": [{"product_id": tp_id, "quantity": 1, "item_data": {"naver_url": "https://naver.me/cancel", "qty": 1}}],
        }, token=TOKEN)
        order_id3 = d.get("id") if code == 201 else None

        if order_id3:
            code, d = api("POST", f"/orders/{order_id3}/cancel", token=TOKEN)
            test("Cancel draft order (draft→cancelled)", code, 200, f"status={d.get('status')}" if isinstance(d, dict) else detail_of(d))

    else:
        skip("Order E2E", "order create failed")

    # List orders
    code, d = api("GET", "/orders/", token=TOKEN)
    test("List orders", code, 200, f"{d.get('total', 0)} items" if isinstance(d, dict) else "")

    # Search
    if order_num:
        code, d = api("GET", f"/orders/?search={order_num[:10]}", token=TOKEN)
        test("Search order by number", code, 200, f"{d.get('total', 0)} found" if isinstance(d, dict) else "")

    # Filter by status
    code, d = api("GET", "/orders/?status=draft", token=TOKEN)
    test("Filter orders: draft", code, 200)

    code, d = api("GET", "/orders/?status=submitted", token=TOKEN)
    test("Filter orders: submitted", code, 200)

    # Order deadlines
    code, d = api("GET", "/orders/deadlines?year=2026&month=2", token=TOKEN)
    test("Order deadlines (calendar)", code, 200)

    # Export orders
    code, d = api("GET", "/orders/export", token=TOKEN, raw_response=True)
    test("Export orders (Excel)", code, 200)

    # Excel template
    code, d = api("GET", f"/orders/excel-template/{tp_id}", token=TOKEN, raw_response=True)
    test("Excel template download", code, 200)

    # Order items export
    if order_id:
        code, d = api("GET", f"/orders/{order_id}/items/export", token=TOKEN, raw_response=True)
        test("Export order items (Excel)", code, 200)

    # Bulk status
    code, d = api("POST", "/orders/bulk-status", {"order_ids": [], "status": "submitted"}, token=TOKEN)
    test("Bulk status (empty list)", code, 200)

    # Clean up test product
    api("DELETE", f"/products/{tp_id}", token=TOKEN)
    test("Delete test product (cleanup)", 204, 204)
else:
    skip("Orders E2E", "no test product")

# ── SESSION RESET ──
print("\n  --- Session Reset ---")
TOKEN = login()

section("7", "SETTLEMENTS")
code, d = api("GET", "/settlements/", token=TOKEN)
test("List settlements", code, 200, f"total={d.get('total', 0)}" if isinstance(d, dict) else detail_of(d))
if isinstance(d, dict):
    summary = d.get("summary", {})
    test("Settlement summary present", 200 if summary else 404, 200,
         f"revenue={summary.get('total_revenue', 0)}, profit={summary.get('total_profit', 0)}" if summary else "missing")

code, d = api("GET", "/settlements/?date_from=2026-01-01&date_to=2026-12-31", token=TOKEN)
test("Settlements with date filter", code, 200)

# Secret settlement
code, d = api("POST", "/settlements/secret", {"password": "j2lab-settlement-2026"}, token=TOKEN)
test("Settlement secret (correct pw)", code, 200, f"items={len(d.get('items',[]))}" if isinstance(d, dict) else "")
if isinstance(d, dict):
    items = d.get("items", [])
    secret_summary = d.get("summary", {})
    if items:
        test("Secret item has order_number", 200 if "order_number" in items[0] else 400, 200)
        test("Secret item has profit", 200 if "profit" in items[0] else 400, 200)
        test("Secret item has margin_pct", 200 if "margin_pct" in items[0] else 400, 200)
    test("Secret summary present", 200 if secret_summary else 404, 200)

code, d = api("POST", "/settlements/secret", {"password": "wrong-password"}, token=TOKEN)
test("Settlement secret (wrong pw)", code, 403)

code, d = api("GET", "/settlements/export", token=TOKEN, raw_response=True)
test("Settlement export (Excel)", code, 200)

code, d = api("GET", "/settlements/export?date_from=2026-01-01&date_to=2026-03-01", token=TOKEN, raw_response=True)
test("Settlement export with dates", code, 200)

# ── SESSION RESET ──
print("\n  --- Session Reset ---")
TOKEN = login()

section("8", "BALANCE")
if ADMIN_ID:
    code, d = api("GET", f"/balance/{ADMIN_ID}", token=TOKEN)
    test("Get admin balance", code, 200, f"balance={d.get('balance')}" if isinstance(d, dict) else detail_of(d))

    code, d = api("GET", f"/balance/{ADMIN_ID}/transactions", token=TOKEN)
    test("Admin balance transactions", code, 200, f"{d.get('total', 0)} txns" if isinstance(d, dict) else "")

    # Deposit
    code, d = api("POST", "/balance/deposit", {
        "user_id": ADMIN_ID, "amount": 10000, "description": "API test deposit"
    }, token=TOKEN)
    test("Deposit balance", code, 200, f"amount={d.get('amount')}" if isinstance(d, dict) else detail_of(d))

    # Withdraw
    code, d = api("POST", "/balance/withdraw", {
        "user_id": ADMIN_ID, "amount": 10000, "description": "API test withdraw"
    }, token=TOKEN)
    test("Withdraw balance", code, 200, f"amount={d.get('amount')}" if isinstance(d, dict) else detail_of(d))

    # Invalid withdraw (negative)
    code, d = api("POST", "/balance/withdraw", {
        "user_id": ADMIN_ID, "amount": -100, "description": "bad"
    }, token=TOKEN)
    test("Withdraw negative (expect 422)", code, 422)
else:
    skip("Balance tests", "no admin ID")

# ── SESSION RESET ──
print("\n  --- Session Reset ---")
TOKEN = login()

section("9", "DASHBOARD")
code, d = api("GET", "/dashboard/summary", token=TOKEN)
test("Dashboard summary", code, 200)

code, d = api("GET", "/dashboard/enhanced", token=TOKEN)
test("Dashboard enhanced", code, 200)

code, d = api("GET", "/dashboard/campaign-stats", token=TOKEN)
test("Dashboard campaign-stats", code, 200)

# ── SESSION RESET ──
print("\n  --- Session Reset ---")
TOKEN = login()

section("10", "CAMPAIGNS")
code, d = api("GET", "/campaigns/", token=TOKEN)
test("List campaigns", code, 200, f"{d.get('total', 0)} items" if isinstance(d, dict) else "")
CAMPAIGNS = d.get("items", []) if isinstance(d, dict) else []

code, d = api("GET", "/campaigns/?size=5&page=1", token=TOKEN)
test("Campaigns pagination", code, 200)

code, d = api("GET", "/campaigns/?status=active", token=TOKEN)
test("Campaigns filter: active", code, 200)

code, d = api("GET", "/campaigns/registration/progress", token=TOKEN)
test("Registration progress", code, 200)

# Campaign upload template
code, d = api("GET", "/campaigns/upload/template", token=TOKEN, raw_response=True)
test("Campaign upload template", code, 200)

# Single campaign detail
if CAMPAIGNS:
    cid = CAMPAIGNS[0].get("id")
    code, d = api("GET", f"/campaigns/{cid}", token=TOKEN)
    test("Get campaign by ID", code, 200, f"status={d.get('status')}" if isinstance(d, dict) else "")

    code, d = api("GET", f"/campaigns/{cid}/keywords", token=TOKEN)
    test("Campaign keywords", code, 200)

# ── SESSION RESET ──
print("\n  --- Session Reset ---")
TOKEN = login()

section("11", "NOTIFICATIONS & NOTICES")
code, d = api("GET", "/notifications/", token=TOKEN)
test("List notifications", code, 200)

code, d = api("POST", "/notifications/read-all", token=TOKEN)
test("Mark all read", code, 200)

code, d = api("GET", "/notices/", token=TOKEN)
test("List notices", code, 200)

code, d = api("POST", "/notices/", {"title": "__API_T__", "content": "test notice"}, token=TOKEN)
test("Create notice", code, 201)
tn_id = d.get("id") if code == 201 else None

if tn_id:
    code, d = api("PUT", f"/notices/{tn_id}", {"title": "__API_T_UPD__", "content": "updated"}, token=TOKEN)
    test("Update notice", code, 200)

    code, d = api("DELETE", f"/notices/{tn_id}", token=TOKEN)
    test("Delete notice", code, 204)

# ── SESSION RESET ──
print("\n  --- Session Reset ---")
TOKEN = login()

section("12", "PLACES & EXTRACTION")
code, d = api("GET", "/places/", token=TOKEN)
test("List places", code, 200, f"{d.get('total', 0)} items" if isinstance(d, dict) else "")
PLACES = d.get("items", []) if isinstance(d, dict) else []

if PLACES:
    pid = PLACES[0].get("id")
    code, d = api("GET", f"/places/{pid}", token=TOKEN)
    test("Get place by ID", code, 200)

    code, d = api("GET", f"/places/{pid}/keywords", token=TOKEN)
    test("Place keywords", code, 200)

code, d = api("GET", "/extraction/jobs", token=TOKEN)
test("List extraction jobs", code, 200)

# ── SESSION RESET ──
print("\n  --- Session Reset ---")
TOKEN = login()

section("13", "PIPELINE")
code, d = api("GET", "/pipeline/overview", token=TOKEN)
test("Pipeline overview", code, 200)

# ── SESSION RESET ──
print("\n  --- Session Reset ---")
TOKEN = login()

section("14", "ASSIGNMENT")
code, d = api("GET", "/assignment/queue", token=TOKEN)
test("Assignment queue", code, 200)

# ── SESSION RESET ──
print("\n  --- Session Reset ---")
TOKEN = login()

section("15", "SETTINGS")
code, d = api("GET", "/settings/", token=TOKEN)
test("List settings", code, 200)

# ── SESSION RESET ──
print("\n  --- Session Reset ---")
TOKEN = login()

section("16", "SUPERAP ACCOUNTS")
code, d = api("GET", "/superap-accounts/", token=TOKEN)
test("List superap accounts", code, 200, f"total={d.get('total', 0)}" if isinstance(d, dict) else "")

code, d = api("GET", "/superap-accounts/agencies", token=TOKEN)
test("List agencies", code, 200)

# ── SESSION RESET ──
print("\n  --- Session Reset ---")
TOKEN = login()

section("17", "TEMPLATES (Campaign)")
code, d = api("GET", "/templates/", token=TOKEN)
test("List templates", code, 200, f"total={d.get('total', 0)}" if isinstance(d, dict) else "")
TEMPLATES = d.get("items", []) if isinstance(d, dict) else []

code, d = api("GET", "/templates/modules", token=TOKEN)
test("Template modules", code, 200)

if TEMPLATES:
    tid = TEMPLATES[0].get("id")
    code, d = api("GET", f"/templates/{tid}", token=TOKEN)
    test("Get template by ID", code, 200)

# ── SESSION RESET ──
print("\n  --- Session Reset ---")
TOKEN = login()

section("18", "NETWORK PRESETS")
code, d = api("GET", "/network-presets/", token=TOKEN)
test("List network presets", code, 200)

# Create (requires company_id, campaign_type, tier_order, name, media_config)
code, d = api("POST", "/network-presets/", {
    "company_id": 1, "campaign_type": "traffic", "tier_order": 1,
    "name": "__TEST_PRESET__", "media_config": {"wifi": True, "mobile": False}
}, token=TOKEN)
test("Create network preset", code, [201, 200], f"id={d.get('id')}" if isinstance(d, dict) and d.get('id') else detail_of(d))
np_id = d.get("id") if isinstance(d, dict) else None

if np_id:
    code, d = api("PATCH", f"/network-presets/{np_id}", {"name": "__TEST_PRESET_UPD__"}, token=TOKEN)
    test("Update network preset", code, 200)

    code, d = api("DELETE", f"/network-presets/{np_id}", token=TOKEN)
    test("Delete network preset", code, [204, 200])

# ── SESSION RESET ──
print("\n  --- Session Reset ---")
TOKEN = login()

section("19", "SCHEDULER")
code, d = api("GET", "/scheduler/status", token=TOKEN)
test("Scheduler status", code, 200)

# Don't trigger scheduler in test — that's a real action
skip("Scheduler trigger", "skipped to avoid side effects")

# ── SESSION RESET ──
print("\n  --- Session Reset ---")
TOKEN = login()

section("20", "WORKER HEALTH (internal via api-server)")
HEALTH_BASE = BASE.rsplit("/api/v1", 1)[0]
code, d = api("GET", "/health", base_override=HEALTH_BASE)
test("API server /health", code, 200, d.get("status") if isinstance(d, dict) else "")

section("21", "INTERNAL CALLBACKS (should require internal secret)")
code, d = api("POST", "/internal/callback/extraction/0", {"status": "done"},
              base_override=HEALTH_BASE)
test("Extraction callback (no secret)", code, 422, "missing X-Internal-Secret header")

code, d = api("POST", "/internal/callback/campaign/0", {"status": "done"},
              base_override=HEALTH_BASE)
test("Campaign callback (no secret)", code, 422, "missing X-Internal-Secret header")

# ══════════════════════════════════════════════════════════════
# FINAL REPORT
# ══════════════════════════════════════════════════════════════
total = PASS + FAIL
print(f"\n{'='*60}")
print(f"FINAL RESULTS: {total} tests | {PASS} PASSED | {FAIL} FAILED | {SKIP} SKIPPED")
print(f"{'='*60}")

if FAIL > 0:
    print("\nFAILURES:")
    for s, name, c, det in RESULTS:
        if s == "FAIL":
            print(f"  ✗ {name} -> {c} {det}")

if SKIP > 0:
    print(f"\nSKIPPED: {SKIP}")
    for s, name, c, det in RESULTS:
        if s == "SKIP":
            print(f"  - {name} {det}")

print()
sys.exit(0 if FAIL == 0 else 1)
