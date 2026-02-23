"""SQLAlchemy models - import all models here so Alembic can discover them."""

# Phase 1A
from app.models.balance_transaction import BalanceTransaction, TransactionType
from app.models.company import Company
from app.models.order import (
    AssignmentStatus,
    Order,
    OrderItem,
    OrderItemStatus,
    OrderStatus,
    PaymentStatus,
    VALID_ORDER_TRANSITIONS,
)
from app.models.price_policy import PricePolicy
from app.models.product import Product
from app.models.refresh_token import RefreshToken
from app.models.system_setting import SystemSetting
from app.models.user import User, UserRole, has_role_or_higher

# Phase 1C - Pipeline & Integration
from app.models.campaign import Campaign, CampaignStatus
from app.models.campaign_keyword_pool import CampaignKeywordPool
from app.models.campaign_template import CampaignTemplate
from app.models.extraction_job import ExtractionJob, ExtractionJobStatus
from app.models.keyword import Keyword
from app.models.keyword_rank_history import KeywordRankHistory
from app.models.network_preset import NetworkPreset
from app.models.pipeline_log import PipelineLog
from app.models.pipeline_state import (
    PipelineStage,
    PipelineState,
    VALID_PIPELINE_TRANSITIONS,
)
from app.models.place import Place
from app.models.superap_account import SuperapAccount

__all__ = [
    # Phase 1A
    "BalanceTransaction",
    "Company",
    "Order",
    "OrderItem",
    "OrderStatus",
    "OrderItemStatus",
    "AssignmentStatus",
    "PaymentStatus",
    "PricePolicy",
    "Product",
    "RefreshToken",
    "SystemSetting",
    "TransactionType",
    "User",
    "UserRole",
    "VALID_ORDER_TRANSITIONS",
    "has_role_or_higher",
    # Phase 1C
    "Campaign",
    "CampaignKeywordPool",
    "CampaignStatus",
    "CampaignTemplate",
    "ExtractionJob",
    "ExtractionJobStatus",
    "Keyword",
    "KeywordRankHistory",
    "NetworkPreset",
    "PipelineLog",
    "PipelineStage",
    "PipelineState",
    "Place",
    "SuperapAccount",
    "VALID_PIPELINE_TRANSITIONS",
]
