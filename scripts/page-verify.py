#!/usr/bin/env python3
"""Verify all frontend pages + API endpoints for each page."""
import urllib.request, json, re, sys

BASE = "http://localhost:8000/api/v1"
NGINX = "http://localhost:80"
PASS = 0
FAIL = 0

def get_raw(url, token=None):
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        ct = resp.headers.get("Content-Type", "")
        body = resp.read()
        return resp.status, ct, body
    except urllib.error.HTTPError as e:
        return e.code, "", b""
    except Exception as e:
        return 0, str(e)[:60], b""

def api(method, path, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return resp.status, json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace") if e.fp else ""
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw
    except Exception:
        return 0, None

def check(name, ok, detail=""):
    global PASS, FAIL
    sym = "OK" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    d = f"  ({detail})" if detail else ""
    print(f"  [{sym:4s}] {name}{d}")

# ── Login ──
code, d = api("POST", "/auth/login", {"email": "admin@jtwolab.kr", "password": "jjlab1234!j"})
TOKEN = d.get("access_token", "") if isinstance(d, dict) else ""
print(f"Login: {code}\n")

# ══════════════════════════════════════════════════════════════
print("=" * 60)
print("PART 1: SPA Page Delivery (Nginx → index.html)")
print("=" * 60)

pages = [
    ("/", "Root"),
    ("/login", "LoginPage"),
    ("/dashboard", "DashboardPage"),
    ("/orders", "OrdersPage"),
    ("/orders/new", "OrderGridPage"),
    ("/orders/1", "OrderDetailPage"),
    ("/campaigns", "CampaignsPage"),
    ("/campaigns/new", "CampaignAddPage"),
    ("/campaigns/upload", "CampaignUploadPage"),
    ("/campaigns/1", "CampaignDetailPage"),
    ("/campaign-templates", "CampaignTemplatesPage"),
    ("/users", "UsersPage"),
    ("/companies", "CompaniesPage"),
    ("/settings", "SettingsPage"),
    ("/settlements", "SettlementPage"),
    ("/settlements/secret", "SettlementSecretPage"),
    ("/superap-accounts", "SuperapAccountsPage"),
    ("/notices", "NoticesPage"),
    ("/calendar", "CalendarPage"),
    ("/assignment-queue", "AssignmentQueuePage"),
    ("/categories", "CategoriesPage"),
    ("/products", "ProductsPage"),
    ("/price-matrix", "PriceMatrixPage"),
]

for path, name in pages:
    code, ct, body = get_raw(NGINX + path)
    html = body.decode("utf-8", "replace")
    has_root = 'id="root"' in html
    has_js = "/assets/" in html and ".js" in html
    ok = code == 200 and "text/html" in ct and has_root and has_js
    check(f"{name:30s} {path}", ok, f"{code}, {len(body)} bytes, root={has_root}, js={has_js}")

# ══════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}")
print("PART 2: Static Assets (JS/CSS bundles)")
print("=" * 60)

_, _, index_body = get_raw(NGINX + "/")
index_html = index_body.decode("utf-8", "replace")
assets = re.findall(r'(?:src|href)="(/assets/[^"]+)"', index_html)
for asset in assets:
    code, ct, body = get_raw(NGINX + asset)
    ext = asset.rsplit(".", 1)[-1][:4]
    check(f"{asset[-55:]}", code == 200, f"{len(body)} bytes, {ext}")

# ══════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}")
print("PART 3: API Endpoints per Page")
print("=" * 60)

def api_check(page, endpoint, method="GET", data=None):
    if method == "GET":
        c, d = api("GET", endpoint, token=TOKEN)
    else:
        c, d = api(method, endpoint, data=data, token=TOKEN)
    detail = ""
    if isinstance(d, dict):
        if "total" in d:
            detail = f"total={d['total']}"
        elif "items" in d:
            detail = f"items={len(d['items'])}"
        elif "status" in d:
            detail = f"status={d['status']}"
    check(f"{page:25s} {method:4s} {endpoint}", c == 200 or c == 201, f"{c} {detail}")

print("\n-- LoginPage --")
api_check("LoginPage", "/auth/login", "POST", {"email": "admin@jtwolab.kr", "password": "jjlab1234!j"})

print("\n-- DashboardPage --")
api_check("DashboardPage", "/dashboard/summary")
api_check("DashboardPage", "/dashboard/enhanced")
api_check("DashboardPage", "/dashboard/campaign-stats")

print("\n-- OrdersPage --")
api_check("OrdersPage", "/orders/?page=1&size=20")
api_check("OrdersPage", "/orders/?status=draft")
api_check("OrdersPage", "/orders/?status=processing")

print("\n-- OrderGridPage --")
api_check("OrderGridPage", "/products/?size=100&is_active=true")
api_check("OrderGridPage", "/categories/")

print("\n-- OrderDetailPage --")
c, d = api("GET", "/orders/?page=1&size=1", token=TOKEN)
if isinstance(d, dict) and d.get("items"):
    oid = d["items"][0]["id"]
    api_check("OrderDetailPage", f"/orders/{oid}")

print("\n-- CampaignsPage --")
api_check("CampaignsPage", "/campaigns/?page=1&size=20")
api_check("CampaignsPage", "/campaigns/?status=active")

print("\n-- CampaignAddPage --")
api_check("CampaignAddPage", "/superap-accounts/")
api_check("CampaignAddPage", "/templates/")

print("\n-- CampaignUploadPage --")
api_check("CampaignUploadPage", "/campaigns/upload/template")
api_check("CampaignUploadPage", "/campaigns/registration/progress")

print("\n-- CampaignDetailPage --")
c, d = api("GET", "/campaigns/?page=1&size=1", token=TOKEN)
if isinstance(d, dict) and d.get("items"):
    cid = d["items"][0]["id"]
    api_check("CampaignDetailPage", f"/campaigns/{cid}")
    api_check("CampaignDetailPage", f"/campaigns/{cid}/keywords")

print("\n-- CampaignTemplatesPage --")
api_check("CampaignTemplates", "/templates/")
api_check("CampaignTemplates", "/templates/modules")

print("\n-- UsersPage --")
api_check("UsersPage", "/users/?page=1&size=20")
api_check("UsersPage", "/users/?role=distributor")

print("\n-- CompaniesPage --")
api_check("CompaniesPage", "/companies/")

print("\n-- SettingsPage --")
api_check("SettingsPage", "/settings/")

print("\n-- SettlementPage --")
api_check("SettlementPage", "/settlements/")
api_check("SettlementPage", "/settlements/?date_from=2026-01-01")

print("\n-- SettlementSecretPage --")
api_check("SettlementSecret", "/settlements/secret", "POST",
          {"password": "j2lab-settlement-2026"})

print("\n-- SuperapAccountsPage --")
api_check("SuperapAccounts", "/superap-accounts/")
api_check("SuperapAccounts", "/superap-accounts/agencies")

print("\n-- NoticesPage --")
api_check("NoticesPage", "/notices/")

print("\n-- CalendarPage --")
api_check("CalendarPage", "/orders/deadlines?year=2026&month=2")

print("\n-- AssignmentQueuePage --")
api_check("AssignmentQueue", "/assignment/queue")

print("\n-- CategoriesPage --")
api_check("CategoriesPage", "/categories/")

print("\n-- ProductsPage --")
api_check("ProductsPage", "/products/?page=1&size=100")

print("\n-- PriceMatrixPage --")
api_check("PriceMatrixPage", "/products/prices/matrix")
api_check("PriceMatrixPage", "/products/prices/user-matrix")

print("\n-- NotificationsBar --")
api_check("NotificationsBar", "/notifications/")

print("\n-- BalanceWidget --")
c, d = api("GET", "/users/me", token=TOKEN)
uid = d.get("id", "") if isinstance(d, dict) else ""
if uid:
    api_check("BalanceWidget", f"/balance/{uid}")

# ══════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}")
print(f"TOTAL: {PASS + FAIL} checks | {PASS} OK | {FAIL} FAIL")
print("=" * 60)
sys.exit(0 if FAIL == 0 else 1)
