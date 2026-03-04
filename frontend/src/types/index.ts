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
  parent_id?: string | null;
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
  code?: string;
  category?: string;
  description?: string;
  form_schema?: FormField[];
  base_price: number;
  cost_price?: number;
  reduction_rate?: number;
  min_work_days?: number;
  max_work_days?: number;
  min_daily_limit?: number;
  daily_deadline: string;
  deadline_timezone: string;
  setup_delay_minutes?: number;
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
  | 'payment_hold'
  | 'processing'
  | 'completed'
  | 'cancelled'
  | 'rejected';

export type PaymentStatus = 'unpaid' | 'confirmed' | 'settled';

export type OrderType = 'regular' | 'monthly_guarantee' | 'managed';

export interface Order {
  id: number;
  order_number: string;
  user_id: string;
  user?: User;
  company_id?: number;
  company?: Company;
  status: OrderStatus;
  payment_status: PaymentStatus;
  order_type?: OrderType;
  total_amount: number;
  vat_amount: number;
  notes?: string;
  source: string;
  submitted_by?: string;
  submitted_at?: string;
  payment_confirmed_by?: string;
  payment_confirmed_at?: string;
  hold_reason?: string;
  payment_checked_by?: string;
  payment_checked_at?: string;
  completed_at?: string;
  selection_status?: string;
  selected_by?: string;
  selected_at?: string;
  pipeline_warnings?: string[];
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
  row_number?: number;
  quantity: number;
  unit_price: number;
  subtotal: number;
  item_data?: any;
  status: string;
  result_message?: string;
  cost_unit_price?: number;
  assigned_account_id?: number;
  assignment_status?: string;
  assigned_at?: string;
  assigned_by?: string;
  created_at: string;
  updated_at?: string;
}

export interface CreateOrderRequest {
  items: {
    product_id: number;
    quantity: number;
    item_data?: any;
  }[];
  notes?: string;
  order_type?: OrderType;
  assigned_account_id?: number;
}

// ============================================================
// Campaign
// ============================================================

export type CampaignStatus =
  | 'pending'
  | 'queued'
  | 'registering'
  | 'active'
  | 'daily_exhausted'
  | 'campaign_exhausted'
  | 'paused'
  | 'deactivated'
  | 'pending_extend'
  | 'completed'
  | 'failed'
  | 'expired';

export interface Campaign {
  id: number;
  campaign_code?: string;
  superap_account_id?: number;
  order_item_id?: number;
  place_id?: number;
  extraction_job_id?: number;
  agency_name?: string;
  place_name: string;
  place_url: string;
  campaign_type: string;
  registered_at?: string;
  start_date: string;
  end_date: string;
  daily_limit: number;
  total_limit?: number;
  current_conversions: number;
  status: CampaignStatus;
  registration_step?: string;
  registration_message?: string;
  extend_target_id?: number;
  network_preset_id?: number;
  company_id?: number;
  extension_history?: any;
  original_keywords?: string;
  landmark_name?: string;
  step_count?: number;
  module_context?: any;
  conversion_threshold_handled?: boolean;
  last_keyword_change?: string;
  created_at: string;
  updated_at?: string;
}

export interface CampaignKeyword {
  id: number;
  campaign_id: number;
  keyword: string;
  is_used: boolean;
  used_at?: string;
  round_number: number;
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
  | 'draft'
  | 'order_received'
  | 'submitted'
  | 'payment_confirmed'
  | 'extraction_queued'
  | 'extraction_running'
  | 'extracting'
  | 'extraction_done'
  | 'account_assigned'
  | 'auto_assign'
  | 'assignment_confirmed'
  | 'campaign_registering'
  | 'registration_queued'
  | 'registering'
  | 'campaign_active'
  | 'active'
  | 'management'
  | 'completed'
  | 'failed'
  | 'cancelled';

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
  orders_by_status: Record<string, number>;
  campaigns_by_status: Record<string, number>;
  pipeline_overview: PipelineOverview[];
  recent_orders: Order[];
  user_role: UserRole;
}

export interface PipelineOverview {
  stage: PipelineStage;
  count: number;
}

export interface DeadlineAlert {
  order_id: number;
  order_number: string;
  deadline: string;
  days_remaining: number;
  urgency: 'red' | 'orange' | 'yellow';
  status: string;
}

export interface KeywordWarning {
  campaign_id: number;
  place_name: string;
  campaign_code?: string;
  remaining: number;
  total: number;
}

export interface EnhancedDashboard {
  upcoming_deadlines: DeadlineAlert[];
  keyword_warnings: KeywordWarning[];
  registration_queue: { status: string; registration_step: string; count: number }[];
  weekly_trend: { date: string; count: number }[];
}

export interface CalendarDeadlines {
  orders: {
    id: number;
    order_number: string;
    deadline: string | null;
    status: string;
    total_amount: number;
  }[];
  campaigns: {
    id: number;
    campaign_code?: string;
    place_name: string;
    end_date: string | null;
    status: string;
  }[];
}

// ============================================================
// System Settings
// ============================================================

export interface SystemSetting {
  key: string;
  value: any;
  description?: string;
  updated_by?: string;
  updated_at?: string;
}

// ============================================================
// API Common
// ============================================================

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface ApiError {
  detail: string;
  status_code?: number;
}

// ============================================================
// Category
// ============================================================

export interface Category {
  id: number;
  name: string;
  description?: string;
  icon?: string;
  sort_order: number;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
}

export interface CreateCategoryRequest {
  name: string;
  description?: string;
  icon?: string;
  sort_order?: number;
}

export interface UpdateCategoryRequest {
  name?: string;
  description?: string;
  icon?: string;
  sort_order?: number;
  is_active?: boolean;
}

export interface CategoryReorderRequest {
  items: { id: number; sort_order: number }[];
}

// ============================================================
// Notification
// ============================================================

export type NotificationType = 'order' | 'campaign' | 'system' | 'settlement';

export interface Notification {
  id: number;
  user_id: string;
  type: NotificationType;
  title: string;
  message: string;
  related_id?: number;
  is_read: boolean;
  created_at: string;
}

export interface NotificationListResponse {
  items: Notification[];
  total: number;
  page: number;
  size: number;
  pages: number;
  unread_count: number;
}

// ============================================================
// Notice
// ============================================================

export interface Notice {
  id: number;
  title: string;
  content: string;
  author_id: string;
  author_name?: string;
  is_pinned: boolean;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
}

export interface CreateNoticeRequest {
  title: string;
  content: string;
  is_pinned?: boolean;
}

export interface UpdateNoticeRequest {
  title?: string;
  content?: string;
  is_pinned?: boolean;
  is_active?: boolean;
}

// ============================================================
// Settlement
// ============================================================

export type SettlementStatus = 'pending' | 'confirmed' | 'settled';

export interface Settlement {
  order_id: number;
  order_number: string;
  product_name: string;
  user_name: string;
  user_role: string;
  quantity: number;
  unit_price: number;
  base_price: number;
  subtotal: number;
  cost: number;
  profit: number;
  margin_pct: number;
  created_at: string;
}

export interface SettlementSummary {
  total_revenue: number;
  total_cost: number;
  total_profit: number;
  avg_margin_pct: number;
  order_count: number;
  item_count: number;
}

export interface SettlementSecretRequest {
  password: string;
  date_from?: string;
  date_to?: string;
}

export interface SettlementSecretItem {
  order_id: number;
  order_number: string;
  product_name: string;
  user_name: string;
  user_role: string;
  quantity: number;
  unit_price: number;
  base_price: number;
  subtotal: number;
  cost: number;
  profit: number;
  margin_pct: number;
  created_at: string;
}

// ============================================================
// Product Schema (extended)
// ============================================================

export type FieldType = 'text' | 'url' | 'number' | 'date' | 'select' | 'calc' | 'date_calc' | 'date_diff' | 'readonly' | 'checkbox';

export interface CalcFormula {
  fieldA: string;
  operator: '+' | '-' | '*' | '/';
  fieldB: string;
}

export interface DateCalcFormula {
  dateField: string;
  daysField: string;
}

export interface DateDiffFormula {
  startField: string;
  endField: string;
}

export interface FormFieldExtended extends FormField {
  type: FieldType;
  options?: string[];
  formula?: CalcFormula | DateCalcFormula | DateDiffFormula | string;  // object (new) or string (legacy)
  color?: string;
  sample?: string;
  is_quantity?: boolean;
  description?: string;
  group?: string;  // checkbox field name that controls this field's enabled state
  min?: number;
  max?: number;
}

export interface ProductSchema {
  product_id: number;
  product_name: string;
  form_schema: FormFieldExtended[];
  base_price: number | null;
  effective_price: number;
}

export interface CombinedProductConfig {
  trafficProduct: Product;
  saveProduct: Product;
  trafficPrice: number;
  savePrice: number;
}

export interface PricePolicy {
  id: number;
  product_id: number;
  user_id?: string;
  role?: UserRole;
  price: number;
  min_quantity?: number;
  is_active: boolean;
  created_at: string;
}

export interface PriceMatrixRow {
  product_id: number;
  product_name: string;
  base_price: number;
  prices: Record<string, number>;
}

// ============================================================
// Campaign (extended for Dashboard)
// ============================================================

export interface CampaignDashboardStats {
  total: number;
  active: number;
  exhausted_today: number;
  keyword_warnings: number;
}

export interface CampaignListItem extends Campaign {
  days_running: number;
  keyword_status: 'normal' | 'warning' | 'critical';
  keyword_remaining: number;
  keyword_total: number;
  extension_history?: ExtensionHistoryItem[];
  last_keyword_change?: string;
}

export interface ExtensionHistoryItem {
  extended_at: string;
  previous_total_limit: number;
  new_total_limit: number;
  previous_end_date: string;
  new_end_date: string;
  added_quantity: number;
}

export interface CampaignSettings {
  campaign_code?: string;
  place_name?: string;
  agency_name?: string;
  daily_limit?: number;
  total_limit?: number;
  start_date?: string;
  end_date?: string;
  keywords?: string;
}

export interface CampaignManualCreate {
  campaign_code: string;
  account_id: number;
  place_url: string;
  place_name?: string;
  agency_name?: string;
  template_id: number;
  start_date: string;
  end_date: string;
  daily_limit: number;
  keywords: string;
}

// ============================================================
// Campaign Upload
// ============================================================

export interface CampaignUploadPreviewItem {
  row_number: number;
  agency_name?: string;
  user_id: string;
  start_date: string;
  end_date: string;
  daily_limit: number;
  keywords: string[];
  keyword_count: number;
  place_name?: string;
  place_url: string;
  campaign_type: string;
  is_valid: boolean;
  errors: string[];
  extension_eligible: boolean;
  existing_campaign_code?: string;
  existing_campaign_id?: number;
}

export interface CampaignUploadPreviewResponse {
  items: CampaignUploadPreviewItem[];
  total: number;
  valid_count: number;
  error_count: number;
}

export interface CampaignUploadConfirmRequest {
  items: CampaignUploadConfirmItem[];
}

export interface CampaignUploadConfirmItem {
  place_url: string;
  place_name?: string;
  campaign_type: string;
  start_date: string;
  end_date: string;
  daily_limit: number;
  keywords: string[];
  agency_name?: string;
  account_user_id?: string;
}

export interface RegistrationProgressItem {
  campaign_id: number;
  place_name?: string;
  status: string;
  registration_step: 'queued' | 'logging_in' | 'running_modules' | 'filling_form' | 'submitting' | 'extracting_code' | 'completed' | 'failed';
  registration_message?: string;
  campaign_code?: string;
}

// ============================================================
// Superap Account
// ============================================================

export interface SuperapAccount {
  id: number;
  user_id_superap: string;
  agency_name?: string;
  company_id?: number;
  company_name?: string;
  network_preset_id?: number;
  unit_cost_traffic: number;
  unit_cost_save: number;
  assignment_order: number;
  is_active: boolean;
  campaign_count: number;
  created_at?: string;
}

export interface CreateSuperapAccountRequest {
  user_id_superap: string;
  password: string;
  agency_name?: string;
  company_id?: number;
  network_preset_id?: number;
  unit_cost_traffic?: number;
  unit_cost_save?: number;
  assignment_order?: number;
}

export interface UpdateSuperapAccountRequest {
  password?: string;
  agency_name?: string;
  network_preset_id?: number | null;
  unit_cost_traffic?: number;
  unit_cost_save?: number;
  assignment_order?: number;
  is_active?: boolean;
}

// ============================================================
// Network Preset
// ============================================================

export type CampaignType = 'traffic' | 'save' | 'landmark' | 'directions';

export interface NetworkPreset {
  id: number;
  company_id: number;
  campaign_type: CampaignType;
  tier_order: number;
  name: string;
  media_config?: Record<string, any>;
  handler_user_id?: string | null;
  cost_price?: number;
  description?: string;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
}

export interface CreateNetworkPresetRequest {
  company_id: number;
  campaign_type: CampaignType;
  tier_order: number;
  name: string;
  media_config?: Record<string, any>;
  handler_user_id?: string | null;
  cost_price?: number;
  description?: string;
}

export interface UpdateNetworkPresetRequest {
  name?: string;
  tier_order?: number;
  media_config?: Record<string, any>;
  handler_user_id?: string | null;
  cost_price?: number;
  description?: string;
  is_active?: boolean;
}

// ============================================================
// Campaign Template
// ============================================================

export interface CampaignTemplate {
  id: number;
  type_name: string;
  description_template: string;
  hint_text: string;
  campaign_type_selection?: string;
  links: string[];
  hashtag?: string;
  image_url_200x600?: string;
  image_url_720x780?: string;
  conversion_text_template?: string;
  steps_start?: string;
  modules: string[];
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface CreateCampaignTemplateRequest {
  type_name: string;
  description_template: string;
  hint_text: string;
  campaign_type_selection?: string;
  links?: string[];
  hashtag?: string;
  image_url_200x600?: string;
  image_url_720x780?: string;
  conversion_text_template?: string;
  steps_start?: string;
  modules?: string[];
}

export interface UpdateCampaignTemplateRequest {
  type_name?: string;
  description_template?: string;
  hint_text?: string;
  campaign_type_selection?: string;
  links?: string[];
  hashtag?: string;
  image_url_200x600?: string;
  image_url_720x780?: string;
  conversion_text_template?: string;
  steps_start?: string;
  modules?: string[];
  is_active?: boolean;
}

export interface ModuleInfo {
  name: string;
  description: string;
  variables: string[];
}

// ============================================================
// Scheduler
// ============================================================

export interface SchedulerStatus {
  status: 'running' | 'waiting' | 'stopped';
  last_run?: string;
  execution_count: number;
  keyword_changes: number;
  keyword_failures: number;
  skipped_today: number;
  error_message?: string;
  recent_logs?: SchedulerLog[];
}

export interface SchedulerLog {
  timestamp: string;
  level: 'info' | 'warning' | 'error';
  message: string;
}

// ============================================================
// Order (extended)
// ============================================================

export interface BulkDeleteResult {
  message: string;
  deleted?: number;
  errors?: string[];
}

export interface BulkStatusRequest {
  order_ids: number[];
  status: OrderStatus;
}

export interface DeadlineUpdateRequest {
  deadline: string;
}

export interface ExcelUploadResponse {
  rows: Record<string, any>[];
  errors: string[];
}

export interface ExcelUploadPreviewItem {
  row_number: number;
  data: Record<string, any>;
  is_valid: boolean;
  errors: string[];
}

export interface ExcelUploadPreviewResponse {
  items: ExcelUploadPreviewItem[];
  total: number;
  valid_count: number;
  error_count: number;
  product_id: number;
  product_name: string;
}

export interface ExcelUploadConfirmRequest {
  product_id: number;
  row_indices: number[];
  rows: Record<string, any>[];
  notes?: string;
}

// ============================================================
// Daily Settlement Check
// ============================================================

export interface OrderBrief {
  id: number;
  place_name: string;
  total_amount: number;
  status: string;
  created_at: string;
}

export interface DailyCheckDistributor {
  distributor_id: string;
  distributor_name: string;
  order_count: number;
  total_amount: number;
  orders: OrderBrief[];
}

export interface DailyCheckResponse {
  date: string;
  distributors: DailyCheckDistributor[];
  summary: {
    total_orders: number;
    total_amount: number;
    distributor_count: number;
  };
}
