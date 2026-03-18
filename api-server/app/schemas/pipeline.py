"""Pipeline schemas: request/response models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class PipelineStateResponse(BaseModel):
    """Pipeline state response."""

    id: int
    order_item_id: int
    current_stage: str
    previous_stage: str | None = None
    extraction_job_id: int | None = None
    campaign_id: int | None = None
    error_message: str | None = None
    metadata_: Any = None
    updated_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class PipelineLogResponse(BaseModel):
    """Pipeline log entry response."""

    id: int
    pipeline_state_id: int
    from_stage: str | None = None
    to_stage: str
    trigger_type: str | None = None
    message: str | None = None
    actor_id: uuid.UUID | None = None
    actor_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PipelineOverviewItem(BaseModel):
    """Summary item for pipeline overview."""

    stage: str
    count: int
