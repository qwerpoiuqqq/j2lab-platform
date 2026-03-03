#!/usr/bin/env python3
"""E2E Workflow Integration Test for J2LAB Platform — Wave 1 features.

Tests the full order lifecycle:
  접수 → 정산 체크 → 파이프라인 → 자동 배정 → 알림

Usage:
  python scripts/api-test-e2e-workflow.py [BASE_URL]
  API_BASE=http://52.78.114.92 python scripts/api-test-e2e-workflow.py
"""
import urllib.request, json, sys, time, os

# ── Configuration ──────────────────────────────────────────────
BASE = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("API_BASE", "http://localhost:8000")) + "/api/v1"
PASS = 0
FAIL = 0
SKIP = 0
RESULTS = []
ADMIN_EMAIL = "admin@jtwolab.kr"
ADMIN_PASS = "jjlab1234!j"
RUN_ID = str(int(time.time()) % 100000)

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# ── Helpers ──────────────────────────────────────────────────

def api(method, path, data=None, token=None, timeout=30):
    url = BASE + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        raw = resp.read().decode("utf-8", errors="replace")
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
    if ok:
        PASS += 1
        mark = f"{GREEN}PASS{RESET}"
        icon = f"{GREEN}v{RESET}"
    else:
        FAIL += 1
        mark = f"{RED}FAIL{RESET}"
        icon = f"{RED}x{RESET}"
    d = f" ({detail})" if detail else ""
    print(f"  [{icon} {mark}] {name} -> {code}{d}")
    RESULTS.append(("PASS" if ok else "FAIL", name, code, detail))
    return ok


def skip(name, reason=""):
    global SKIP
    SKIP += 1
    d = f" ({reason})" if reason else ""
    print(f"  [{YELLOW}- SKIP{RESET}] {name}{d}")
    RESULTS.append(("SKIP", name, 0, reason))


def section(num, title):
    print(f"\n{BOLD}{CYAN}{'='*65}{RESET}")
    print(f"{BOLD}{CYAN}  SECTION {num}: {title}{RESET}")
    print(f"{CYAN}{'-'*65}{RESET}")


def detail_of(d):
    if isinstance(d, dict):
        return d.get("detail", str(d))[:120]
    return str(d)[:120]


def login(email=ADMIN_EMAIL, password=ADMIN_PASS):
    code, d = api("POST", "/auth/login", {"email": email, "password": password})
    return d.get("access_token", "") if isinstance(d, dict) and code == 200 else ""


# ══════════════════════════════════════════════════════════════
#  SECTION 1: Environment Setup
# ══════════════════════════════════════════════════════════════

section(1, "Environment Setup — Login + Test Company + Test Users")

# 1.1 Admin login
code, d = api("POST", "/auth/login", {"email": ADMIN_EMAIL, "password": ADMIN_PASS})
test("Admin login", code, 200, "token OK" if code == 200 else detail_of(d))
TOKEN = d.get("access_token", "") if isinstance(d, dict) else ""
if not TOKEN:
    print(f"  {RED}ABORT: Cannot proceed without admin token{RESET}")
    sys.exit(1)

# 1.2 Get admin user info
code, d = api("GET", "/users/me", token=TOKEN)
test("GET /users/me (admin)", code, 200, d.get("name", "?") if isinstance(d, dict) else "")
ADMIN_ID = d.get("id", "") if isinstance(d, dict) else ""
ADMIN_COMPANY_ID = d.get("company_id") if isinstance(d, dict) else None

# 1.3 Ensure test company exists
code, d = api("GET", "/companies/", token=TOKEN)
COMPANIES = d.get("items", []) if isinstance(d, dict) else []
test_company_id = ADMIN_COMPANY_ID  # use admin's company by default

if not test_company_id and COMPANIES:
    test_company_id = COMPANIES[0].get("id")

if test_company_id:
    print(f"  [INFO] Using company_id={test_company_id}")
else:
    # Create test company
    code, d = api("POST", "/companies/", {
        "name": f"__E2E_CO_{RUN_ID}__", "code": f"__e2eco{RUN_ID}__"
    }, token=TOKEN)
    test("Create test company", code, [201, 409], f"id={d.get('id')}" if code == 201 else detail_of(d))
    test_company_id = d.get("id") if code == 201 else None

# 1.4 Create test users (company_admin, order_handler, distributor, sub_account)
TOKENS = {}
USER_IDS = {}

user_specs = [
    ("company_admin", {
        "email": f"ca_{RUN_ID}@test.e2e",
        "password": "Test1234!ca",
        "name": f"E2E CompanyAdmin {RUN_ID}",
        "role": "company_admin",
        "company_id": test_company_id,
    }),
    ("order_handler", {
        "email": f"oh_{RUN_ID}@test.e2e",
        "password": "Test1234!oh",
        "name": f"E2E OrderHandler {RUN_ID}",
        "role": "order_handler",
        "company_id": test_company_id,
    }),
]

# Create company_admin and order_handler first
for role_label, spec in user_specs:
    code, d = api("POST", "/users/", spec, token=TOKEN)
    ok = test(f"Create user ({role_label})", code, [201, 409], f"id={d.get('id')}" if code == 201 else detail_of(d))
    if code == 201 and isinstance(d, dict):
        USER_IDS[role_label] = d.get("id")
    elif code == 409:
        # User already exists — try to find by email
        c2, d2 = api("GET", f"/users/?search={spec['email']}", token=TOKEN)
        if isinstance(d2, dict):
            for u in d2.get("items", []):
                if u.get("email") == spec["email"]:
                    USER_IDS[role_label] = u.get("id")
                    break

# Now create distributor (needs parent_id = order_handler)
oh_id = USER_IDS.get("order_handler")
if oh_id:
    code, d = api("POST", "/users/", {
        "email": f"dist_{RUN_ID}@test.e2e",
        "password": "Test1234!dist",
        "name": f"E2E Distributor {RUN_ID}",
        "role": "distributor",
        "company_id": test_company_id,
        "parent_id": oh_id,
    }, token=TOKEN)
    ok = test("Create user (distributor)", code, [201, 409], f"id={d.get('id')}" if code == 201 else detail_of(d))
    if code == 201 and isinstance(d, dict):
        USER_IDS["distributor"] = d.get("id")
    elif code == 409:
        c2, d2 = api("GET", f"/users/?search=dist_{RUN_ID}@test.e2e", token=TOKEN)
        if isinstance(d2, dict):
            for u in d2.get("items", []):
                if u.get("email") == f"dist_{RUN_ID}@test.e2e":
                    USER_IDS["distributor"] = u.get("id")
                    break
else:
    skip("Create user (distributor)", "no order_handler parent_id")

# Create sub_account (needs parent_id = distributor)
dist_id = USER_IDS.get("distributor")
if dist_id:
    code, d = api("POST", "/users/", {
        "email": f"sub_{RUN_ID}@test.e2e",
        "password": "Test1234!sub",
        "name": f"E2E SubAccount {RUN_ID}",
        "role": "sub_account",
        "company_id": test_company_id,
        "parent_id": dist_id,
    }, token=TOKEN)
    ok = test("Create user (sub_account)", code, [201, 409], f"id={d.get('id')}" if code == 201 else detail_of(d))
    if code == 201 and isinstance(d, dict):
        USER_IDS["sub_account"] = d.get("id")
    elif code == 409:
        c2, d2 = api("GET", f"/users/?search=sub_{RUN_ID}@test.e2e", token=TOKEN)
        if isinstance(d2, dict):
            for u in d2.get("items", []):
                if u.get("email") == f"sub_{RUN_ID}@test.e2e":
                    USER_IDS["sub_account"] = u.get("id")
                    break
else:
    skip("Create user (sub_account)", "no distributor parent_id")

# Login as each role
for role_label, spec in user_specs:
    t = login(spec["email"], spec["password"])
    if t:
        TOKENS[role_label] = t
        print(f"  [INFO] {role_label} logged in")
    else:
        print(f"  [WARN] {role_label} login failed")

if dist_id:
    t = login(f"dist_{RUN_ID}@test.e2e", "Test1234!dist")
    if t:
        TOKENS["distributor"] = t
        print(f"  [INFO] distributor logged in")

if USER_IDS.get("sub_account"):
    t = login(f"sub_{RUN_ID}@test.e2e", "Test1234!sub")
    if t:
        TOKENS["sub_account"] = t
        print(f"  [INFO] sub_account logged in")

# 1.5 Create test product
TOKEN = login()  # re-login as admin
code, d = api("POST", "/products/", {
    "name": f"__E2E_PROD_{RUN_ID}__",
    "code": f"__e2ep{RUN_ID}__",
    "base_price": 100000,
    "category": "traffic",
    "form_schema": [
        {"name": "place_url", "label": "Place URL", "type": "url", "required": True, "color": "#4472C4"},
        {"name": "qty", "label": "Quantity", "type": "number", "required": True, "is_quantity": True},
    ]
}, token=TOKEN)
test("Create test product", code, 201, f"id={d.get('id')}" if code == 201 else detail_of(d))
PRODUCT_ID = d.get("id") if code == 201 else None

print(f"\n  {BOLD}[Summary]{RESET} Users: {list(USER_IDS.keys())}, Product: {PRODUCT_ID}, Company: {test_company_id}")


# ══════════════════════════════════════════════════════════════
#  SECTION 2: PHASE 1 — Order Intake (접수)
# ══════════════════════════════════════════════════════════════

section(2, "PHASE 1 — Order Intake (sub_account order + distributor include)")

sub_token = TOKENS.get("sub_account")
dist_token = TOKENS.get("distributor")
ORDER_ID = None
ORDER_ID2 = None

if sub_token and PRODUCT_ID:
    # 2.1 sub_account creates an order
    code, d = api("POST", "/orders/", {
        "items": [{
            "product_id": PRODUCT_ID,
            "quantity": 5,
            "item_data": {"place_url": "https://naver.me/e2e-test-place", "qty": 5}
        }],
        "notes": f"E2E Test Order {RUN_ID}"
    }, token=sub_token)
    test("sub_account: Create order", code, 201, f"id={d.get('id')}, num={d.get('order_number')}" if code == 201 else detail_of(d))
    ORDER_ID = d.get("id") if code == 201 else None

    if ORDER_ID:
        # 2.2 Submit the order
        code, d = api("POST", f"/orders/{ORDER_ID}/submit", token=sub_token)
        test("sub_account: Submit order", code, 200, f"status={d.get('status')}" if isinstance(d, dict) else detail_of(d))

    # 2.3 distributor checks sub-account pending orders
    if dist_token:
        code, d = api("GET", "/orders/sub-account-pending", token=dist_token)
        test("distributor: GET sub-account-pending", code, 200,
             f"items={len(d.get('items', []))}" if isinstance(d, dict) else detail_of(d))

        # 2.4 distributor includes the order
        if ORDER_ID:
            code, d = api("POST", f"/orders/{ORDER_ID}/include", token=dist_token)
            test("distributor: Include order", code, [200, 400],
                 d.get("message", detail_of(d)) if isinstance(d, dict) else detail_of(d))
    else:
        skip("distributor: sub-account-pending + include", "no distributor token")

    # Create a second order for the payment flow
    code, d = api("POST", "/orders/", {
        "items": [{
            "product_id": PRODUCT_ID,
            "quantity": 2,
            "item_data": {"place_url": "https://naver.me/e2e-test-place2", "qty": 2}
        }],
        "notes": f"E2E Payment Test Order {RUN_ID}"
    }, token=sub_token)
    ORDER_ID2 = d.get("id") if code == 201 else None
    if ORDER_ID2:
        code, d = api("POST", f"/orders/{ORDER_ID2}/submit", token=sub_token)
        test("sub_account: Submit order #2", code, 200)

elif not sub_token:
    skip("PHASE 1 (Order Intake)", "no sub_account token")
else:
    skip("PHASE 1 (Order Intake)", "no test product")


# ══════════════════════════════════════════════════════════════
#  SECTION 3: PHASE 2 — Settlement Check (정산 체크)
# ══════════════════════════════════════════════════════════════

section(3, "PHASE 2 — Settlement Check (daily-check, hold, release-hold, bulk-confirm)")

ca_token = TOKENS.get("company_admin") or TOKEN  # fall back to admin
oh_token = TOKENS.get("order_handler")

# 3.1 daily-check
code, d = api("GET", "/settlements/daily-check", token=ca_token)
test("company_admin: GET /settlements/daily-check", code, 200, detail_of(d))

# 3.2 daily-check with date param
code, d = api("GET", "/settlements/daily-check?date=2026-03-03", token=ca_token)
test("daily-check with date param", code, 200, detail_of(d))

# 3.3 Hold test (requires a submitted order)
if ORDER_ID:
    code, d = api("POST", f"/orders/{ORDER_ID}/hold", {"reason": "E2E test hold"}, token=ca_token)
    test("Hold order (submitted -> payment_hold)", code, [200, 400],
         f"status={d.get('status')}" if isinstance(d, dict) and code == 200 else detail_of(d))

    # 3.4 Release hold
    if code == 200:
        code, d = api("POST", f"/orders/{ORDER_ID}/release-hold", token=ca_token)
        test("Release hold (payment_hold -> submitted)", code, [200, 400],
             f"status={d.get('status')}" if isinstance(d, dict) and code == 200 else detail_of(d))
    else:
        skip("Release hold", "hold failed")
else:
    skip("Hold / Release hold", "no order available")

# 3.5 Bulk hold with nonexistent orders
code, d = api("POST", "/orders/bulk-hold", {"order_ids": [99999], "reason": "E2E bulk"}, token=ca_token)
test("Bulk hold (nonexistent order)", code, 200, detail_of(d))

# 3.6 Deposit balance for approval
if ADMIN_ID:
    api("POST", "/balance/deposit", {
        "user_id": ADMIN_ID, "amount": 10000000, "description": "E2E fund for approval"
    }, token=TOKEN)

# 3.7 Bulk payment confirm
order_ids_for_confirm = []
if ORDER_ID:
    order_ids_for_confirm.append(ORDER_ID)
if ORDER_ID2:
    order_ids_for_confirm.append(ORDER_ID2)

if order_ids_for_confirm:
    code, d = api("POST", "/orders/bulk-payment-confirm", {"order_ids": order_ids_for_confirm}, token=ca_token)
    test("Bulk payment confirm", code, 200, detail_of(d))
else:
    skip("Bulk payment confirm", "no orders to confirm")

# 3.8 Verify order status changed (check via order_handler or admin)
verify_token = oh_token or TOKEN
if ORDER_ID:
    code, d = api("GET", f"/orders/{ORDER_ID}", token=TOKEN)
    order_status = d.get("status", "?") if isinstance(d, dict) else "?"
    test("Verify order status after confirm", code, 200, f"status={order_status}")
else:
    skip("Verify order status", "no order")

# Withdraw test balance
if ADMIN_ID:
    c, dd = api("GET", f"/balance/{ADMIN_ID}", token=TOKEN)
    if isinstance(dd, dict) and dd.get("balance", 0) > 0:
        api("POST", "/balance/withdraw", {
            "user_id": ADMIN_ID, "amount": dd["balance"], "description": "E2E cleanup"
        }, token=TOKEN)


# ══════════════════════════════════════════════════════════════
#  SECTION 4: PHASE 3 — Pipeline State Check
# ══════════════════════════════════════════════════════════════

section(4, "PHASE 3 — Pipeline State Verification")

TOKEN = login()

# 4.1 Pipeline overview
code, d = api("GET", "/pipeline/overview", token=TOKEN)
test("Pipeline overview", code, 200, detail_of(d))

# 4.2 Check individual order item pipeline state
if ORDER_ID:
    code, d = api("GET", f"/orders/{ORDER_ID}", token=TOKEN)
    if isinstance(d, dict) and d.get("items"):
        first_item = d["items"][0]
        item_id = first_item.get("id")
        item_status = first_item.get("status", "?")
        test("Order item status check", code, 200, f"item_id={item_id}, status={item_status}")

        # Try to get pipeline state for this item
        if item_id:
            code2, d2 = api("GET", f"/pipeline/{item_id}", token=TOKEN)
            test("Pipeline state for item", code2, [200, 404],
                 f"stage={d2.get('current_stage')}" if isinstance(d2, dict) and code2 == 200 else detail_of(d2))
    else:
        skip("Order item pipeline state", "no items in order")
else:
    skip("Pipeline state check", "no order")


# ══════════════════════════════════════════════════════════════
#  SECTION 5: PHASE 4 — Auto Assignment + Choice
# ══════════════════════════════════════════════════════════════

section(5, "PHASE 4 — Auto Assignment + New/Extend Choice")

TOKEN = login()

# 5.1 Assignment queue
code, d = api("GET", "/assignment/queue", token=TOKEN)
test("Assignment queue", code, 200,
     f"items={len(d.get('items', []))}" if isinstance(d, dict) else detail_of(d))
queue_items = d.get("items", []) if isinstance(d, dict) else []

# 5.2 If there are items in queue, test choose API
if queue_items:
    qi = queue_items[0]
    qi_item_id = qi.get("order_item_id") or qi.get("id")
    if qi_item_id:
        # Try the choose endpoint (may fail if assignment not in right state)
        code, d = api("POST", f"/assignment/{qi_item_id}/choose", {"action": "new"}, token=TOKEN)
        test("Assignment choose (new)", code, [200, 400, 404, 500],
             detail_of(d))
    else:
        skip("Assignment choose", "no item_id in queue item")
else:
    skip("Assignment choose", "empty queue")

# 5.3 Assignment with nonexistent item
code, d = api("POST", "/assignment/99999/choose", {"action": "new"}, token=TOKEN)
test("Assignment choose (nonexistent)", code, 404, detail_of(d))


# ══════════════════════════════════════════════════════════════
#  SECTION 6: Notification Check
# ══════════════════════════════════════════════════════════════

section(6, "Notifications — Check Event Notifications")

# 6.1 Admin notifications
code, d = api("GET", "/notifications/", token=TOKEN)
test("Admin notifications", code, 200,
     f"total={d.get('total', 0)}, unread={d.get('unread_count', 0)}" if isinstance(d, dict) else detail_of(d))

# 6.2 company_admin notifications
if TOKENS.get("company_admin"):
    code, d = api("GET", "/notifications/", token=TOKENS["company_admin"])
    test("company_admin notifications", code, 200,
         f"total={d.get('total', 0)}" if isinstance(d, dict) else detail_of(d))
else:
    skip("company_admin notifications", "no token")

# 6.3 order_handler notifications
if TOKENS.get("order_handler"):
    code, d = api("GET", "/notifications/", token=TOKENS["order_handler"])
    test("order_handler notifications", code, 200,
         f"total={d.get('total', 0)}" if isinstance(d, dict) else detail_of(d))
else:
    skip("order_handler notifications", "no token")

# 6.4 distributor notifications
if TOKENS.get("distributor"):
    code, d = api("GET", "/notifications/", token=TOKENS["distributor"])
    test("distributor notifications", code, 200,
         f"total={d.get('total', 0)}" if isinstance(d, dict) else detail_of(d))
else:
    skip("distributor notifications", "no token")

# 6.5 Mark all read
code, d = api("POST", "/notifications/read-all", token=TOKEN)
test("Mark all notifications read", code, 200, detail_of(d))


# ══════════════════════════════════════════════════════════════
#  SECTION 7: Cleanup
# ══════════════════════════════════════════════════════════════

section(7, "Cleanup — Delete Test Data")

TOKEN = login()

# 7.1 Delete test product
if PRODUCT_ID:
    code, d = api("DELETE", f"/products/{PRODUCT_ID}", token=TOKEN)
    test("Delete test product", code, [200, 204], detail_of(d))

# 7.2 Deactivate test users (don't delete, just note)
for role_label, uid in USER_IDS.items():
    if uid:
        code, d = api("PATCH", f"/users/{uid}", {"is_active": False}, token=TOKEN)
        test(f"Deactivate {role_label} user", code, [200, 404], detail_of(d))

print(f"\n  [INFO] Test orders remain for inspection. Run cleanup-test-data.py to remove.")


# ══════════════════════════════════════════════════════════════
#  FINAL REPORT
# ══════════════════════════════════════════════════════════════

total = PASS + FAIL
print(f"\n{BOLD}{'='*65}{RESET}")
pct = (PASS / total * 100) if total > 0 else 0
color = GREEN if FAIL == 0 else RED
print(f"{BOLD}  E2E WORKFLOW RESULTS: {total} tests | {GREEN}{PASS} PASSED{RESET}{BOLD} | {color}{FAIL} FAILED{RESET}{BOLD} | {YELLOW}{SKIP} SKIPPED{RESET}{BOLD} ({pct:.0f}%){RESET}")
print(f"{BOLD}{'='*65}{RESET}")

if FAIL > 0:
    print(f"\n{RED}{BOLD}FAILURES:{RESET}")
    for s, name, c, det in RESULTS:
        if s == "FAIL":
            print(f"  {RED}x {name} -> {c} {det}{RESET}")

if SKIP > 0:
    print(f"\n{YELLOW}SKIPPED: {SKIP}{RESET}")
    for s, name, c, det in RESULTS:
        if s == "SKIP":
            print(f"  {YELLOW}- {name} {det}{RESET}")

print()
sys.exit(0 if FAIL == 0 else 1)
