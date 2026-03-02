"""Assignment schemas: auto-assignment request/response models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AssignmentResult(BaseModel):
    """Result of auto-assignment for a single order item."""

    order_item_id: int
    is_extension: bool = False
    extend_target_campaign_id: int | None = None
    assigned_account_id: int | None = None
    assigned_account_name: str | None = None
    network_preset_id: int | None = None
    network_preset_name: str | None = None
    campaign_type: str | None = None
    suggestion: str | None = None  # e.g. "All networks used, consider type change"
    error: str | None = None


class CampaignBrief(BaseModel):
    """Brief campaign summary for recommendation display."""

    campaign_id: int
    campaign_type: str
    status: str
    total_limit: int | None = None
    start_date: str = ""
    end_date: str = ""


class PlaceRecommendation(BaseModel):
    """AI recommendation result for a place at order time."""

    place_id: int
    is_existing: bool
    existing_campaigns: list[CampaignBrief] = []
    recommended_network: str | None = None
    recommended_action: str  # "new" | "extend"


class AssignmentQueueItem(BaseModel):
    """Item in the assignment queue."""

    order_item_id: int
    order_id: int
    place_id: int | None = None
    place_name: str | None = None
    campaign_type: str | None = None
    assignment_status: str
    assigned_account_id: int | None = None
    network_preset_id: int | None = None


class AssignmentConfirmRequest(BaseModel):
    """Request to confirm an assignment."""

    pass  # No body needed


class AssignmentChoiceRequest(BaseModel):
    """Request to choose new or extend for an assignment."""

    action: str = Field(..., pattern="^(new|extend)$")


class AssignmentOverrideRequest(BaseModel):
    """Request to manually change account/network assignment."""

    account_id: int
    network_preset_id: int | None = None


class BulkConfirmRequest(BaseModel):
    """Request to bulk confirm assignments."""

    item_ids: list[int] = Field(..., min_length=1)


class PlaceNetworkHistoryResponse(BaseModel):
    """Network usage history for a place."""

    place_id: int
    campaign_type: str
    network_preset_id: int
    network_preset_name: str
    campaign_id: int
    campaign_status: str
    total_limit: int | None = None
    start_date: str
    end_date: str
