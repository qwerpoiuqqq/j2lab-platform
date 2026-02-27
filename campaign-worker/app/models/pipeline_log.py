"""PipelineLog model - maps to pipeline_logs table.

This model mirrors the table created by api-server's migrations.
campaign-worker uses this for the campaign expiry auto-complete job.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, String, Text, func

from app.core.database import Base


class PipelineLog(Base):
    """Log entry for a pipeline stage transition."""

    __tablename__ = "pipeline_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    pipeline_state_id = Column(BigInteger, nullable=False)
    from_stage = Column(String(30))
    to_stage = Column(String(30), nullable=False)
    trigger_type = Column(String(50))
    message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<PipelineLog(id={self.id}, {self.from_stage} -> {self.to_stage})>"
