"""Fix missing TypeScript types on EC2."""
import sys

path = "/home/ubuntu/j2lab-platform/frontend/src/types/index.ts"
with open(path, "r") as f:
    c = f.read()

# Add missing interfaces at end
extra_types = '''

// === Auto-added missing types ===

export interface DashboardWidgetResponse {
  items: any[];
  total: number;
}

export interface VolumeReportResponse {
  by_date: any[];
  by_product: VolumeByDateProduct[];
  summary: Record<string, any>;
}

export interface VolumeByDateProduct {
  product_id: number;
  product_name: string;
  total_quantity: number;
  total_amount: number;
}

export type ReviewAction = "approve" | "reject" | "request_revision";

export interface OrderEditLog {
  id: number;
  order_id: number;
  field_name: string;
  old_value?: string;
  new_value?: string;
  changed_by: string;
  changed_at: string;
}
'''

# Add review_status to Order
if "review_status" not in c:
    c = c.replace(
        "payment_status?: string;",
        "payment_status?: string;\n  review_status?: string;\n  review_note?: string;"
    )

# Fix LoginRequest to accept login_id
if "LoginRequest" in c and "login_id" not in c.split("LoginRequest")[1].split("}")[0]:
    c = c.replace(
        "export interface LoginRequest {\n  email: string;",
        "export interface LoginRequest {\n  email?: string;\n  login_id?: string;"
    )

# Add category_name to Product
if "category_name" not in c:
    c = c.replace("category_id?: number;", "category_id?: number;\n  category_name?: string;")

# Add image_url to Category interface
if "interface Category" in c:
    cat_section = c.split("interface Category")[1].split("}")[0]
    if "image_url" not in cat_section:
        c = c.replace(
            "interface Category {\n",
            "interface Category {\n  image_url?: string;\n",
            1
        )
        # Try alternate format
        if "image_url" not in c.split("interface Category")[1].split("}")[0]:
            c = c.replace("export interface Category {", "export interface Category {\n  image_url?: string;")

# Only add extra types if not already present
if "DashboardWidgetResponse" not in c:
    c += extra_types

with open(path, "w") as f:
    f.write(c)

print("TYPES UPDATED OK")
