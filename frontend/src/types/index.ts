// ============================================================
// User & Auth
// ============================================================

export type UserRole =
  | 'system_admin'
  | 'company_admin'
  | 'order_handler'
  | 'distributor'
  | 'sub_account';

export interface User {
  id: string;
  email: string;
  name: string;
  phone?: string;
  company_id?: number;
  company?: Company;
  role: UserRole;
  parent_id?: string;
  balance: number;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export interface RefreshResponse {
  access_token: string;
  token_type: string;
}

export interface CreateUserRequest {
  email: string;
  password: string;
  name: string;
  phone?: string;
  company_id?: number;
  role: UserRole;
  parent_id?: string;
}

export interface UpdateUserRequest {
  name?: string;
  phone?: string;
  role?: UserRole;
  is_active?: boolean;
}

// ============================================================
// Company
// ============================================================

export interface Company {
  id: number;
  name: string;
  code: string;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
}

export interface CreateCompanyRequest {
  name: string;
  code: string;
}

// ============================================================
// Product
// ============================================================

export interface FormField {
  name: string;
  type: string;
  label: string;
  required?: boolean;
  default?: string | number;
}

export interface Product {
  id: number;
  name: string;
  code: string;
  category?: string;
  description?: string;
  form_schema?: FormField[];
  base_price: number;
  min_work_days?: number;
  max_work_days?: number;
  daily_deadline: string;
  deadline_timezone: string;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
}

// ============================================================
// Order
// ============================================================

export type OrderStatus =
  | 'draft'
  | 'submitted'
  | 'payment_confirmed'
  | 'processing'
  | 'completed'
  | 'cancelled'
  | 'rejected';

export type PaymentStatus = 'unpaid' | 'confirmed' | 'settled';

export interface Order {
  id: number;
  order_number: string;
  user_id: string;
  user?: User;
  company_id?: number;
  company?: Company;
  status: OrderStatus;
  payment_status: PaymentStatus;
  total_amount: number;
  vat_amount: number;
  notes?: string;
  source: string;
  submitted_by?: string;
  submitted_at?: string;
  payment_confirmed_by?: string;
  payment_confirmed_at?: string;
  created_at: string;
  updated_at?: string;
  items?: OrderItem[];
  item_count?: number;
}

export interface OrderItem {
  id: number;
  order_id: number;
  product_id: number;
  product?: Product;
  place_url: string;
  place_name?: string;
  quantity: number;
  unit_price: number;
  subtotal: number;
  form_data?: Record<string, unknown>;
  status: string;
  created_at: string;
}

export interface CreateOrderRequest {
  items: {
    product_id: number;
    place_url: string;
    quantity: number;
    form_data?: Record<string, unknown>;
  }[];
  notes?: string;
}

// ============================================================
// Campaign
// ============================================================

export type CampaignStatus =
  | 'pending_registration'
  | 'registering'
  | 'active'
  | 'paused'
  | 'completed'
  | 'failed'
  | 'cancelled';

export interface Campaign {
  id: number;
  campaign_code?: string;
  order_item_id?: number;
  order_item?: OrderItem;
  place_id?: number;
  place?: Place;
  superap_account_id?: number;
  template_id?: number;
  status: CampaignStatus;
  start_date?: string;
  end_date?: string;
  daily_limit: number;
  total_budget: number;
  keywords_count?: number;
  current_keyword?: string;
  last_rotation_at?: string;
  created_at: string;
  updated_at?: string;
}

export interface CampaignKeyword {
  id: number;
  campaign_id: number;
  keyword: string;
  is_used: boolean;
  used_at?: string;
  rank?: number;
  last_rank_check?: string;
}

// ============================================================
// Place & Keyword
// ============================================================

export interface Place {
  id: number;
  naver_place_id?: string;
  name: string;
  category?: string;
  address?: string;
  phone?: string;
  url: string;
  extra_data?: Record<string, unknown>;
  created_at: string;
}

export interface Keyword {
  id: number;
  place_id: number;
  keyword: string;
  search_volume?: number;
  current_rank?: number;
  best_rank?: number;
  last_checked_at?: string;
  created_at: string;
}

// ============================================================
// Pipeline
// ============================================================

export type PipelineStage =
  | 'order_received'
  | 'payment_confirmed'
  | 'extraction_queued'
  | 'extracting'
  | 'extraction_done'
  | 'auto_assign'
  | 'assignment_confirmed'
  | 'registration_queued'
  | 'registering'
  | 'active'
  | 'completed'
  | 'failed';

export interface PipelineState {
  id: number;
  order_item_id: number;
  current_stage: PipelineStage;
  previous_stage?: PipelineStage;
  extraction_job_id?: number;
  campaign_id?: number;
  error_message?: string;
  updated_at: string;
}

// ============================================================
// Balance & Settlement
// ============================================================

export type TransactionType = 'deposit' | 'withdraw' | 'payment' | 'refund';

export interface BalanceTransaction {
  id: number;
  user_id: string;
  type: TransactionType;
  amount: number;
  balance_after: number;
  order_id?: number;
  description?: string;
  created_by?: string;
  created_at: string;
}

// ============================================================
// Dashboard
// ============================================================

export interface DashboardSummary {
  total_orders: number;
  active_campaigns: number;
  pending_orders: number;
  today_revenue: number;
  orders_by_status: Record<OrderStatus, number>;
  campaigns_by_status: Record<CampaignStatus, number>;
  pipeline_overview: PipelineOverview[];
  recent_orders: Order[];
}

export interface PipelineOverview {
  stage: PipelineStage;
  count: number;
}

// ============================================================
// System Settings
// ============================================================

export interface SystemSetting {
  key: string;
  value: string;
  description?: string;
  updated_at?: string;
}

// ============================================================
// API Common
// ============================================================

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ApiError {
  detail: string;
  status_code?: number;
}
