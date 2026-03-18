"""Add smart traffic columns (landing_slug, redirect_config).

Revision ID: 022_smart_traffic
Revises: 021_network_ext_threshold
"""

import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "022_smart_traffic"
down_revision = "021_network_ext_threshold"
branch_labels = None
depends_on = None

# --- Template data -----------------------------------------------------------

TRAFFIC_DESCRIPTION = """\
{{image|https://i.ibb.co/DgVqGSnW/image.png}}

1. 하단의 검색키워드 복사 후 미션페이지 클릭
2. 네이버에서 키워드 검색 후 [&상호명&] 클릭
3. 플레이스에서 [지도] 탭 클릭 → [지도앱으로 보기] 버튼 클릭
4. [도착] 버튼 클릭 후 출발지를 [&명소명&]으로 설정
5. [도보] → [가장빠른] 걸음 수 맞추기

[주의사항]
이미 참여한 이력이 있다면 리워드가 지급되지 않을 수 있습니다.
WIFI가 아닌 환경에서는 데이터 이용료가 발생할 수 있습니다."""

SAVE_DESCRIPTION = """\
{{image|https://i.ibb.co/RGW629jv/image.png}}

1. 하단의 검색키워드 복사 후 미션페이지 클릭
2. 네이버에서 키워드 검색 후 [&상호명&] 클릭
3. 플레이스에서 [지도] 탭 클릭 → [지도앱으로 보기] 버튼 클릭
4. 저장하기 버튼 클릭하여 완료한 후 [도착] 버튼 클릭
5. 출발지를 [&명소명&]으로 설정 후 [도보] 설정 후 [가장빠른] 걸음 수 맞추기

[주의사항]
이미 참여한 이력이 있다면 리워드가 지급되지 않을 수 있습니다.
WIFI가 아닌 환경에서는 데이터 이용료가 발생할 수 있습니다."""

MODULES_JSON = '["place_info", "landmark", "steps"]'

DEFAULT_REDIRECT_CONFIG = {
    "channels": {
        "naver_app": {
            "weight": 40,
            "sub": {
                "home": {"weight": 85},
                "blog": {"weight": 15},
            },
        },
        "map_app": {
            "weight": 30,
            "tabs": {
                "map": {"weight": 25},
                "map?tab=discovery": {"weight": 30},
                "map?tab=navi": {"weight": 20},
                "map?tab=pubtrans": {"weight": 15},
                "map?tab=bookmark": {"weight": 10},
            },
        },
        "browser": {
            "weight": 30,
            "sub": {
                "home": {"weight": 85},
                "blog": {"weight": 15},
            },
        },
    }
}

REDIRECT_CONFIG_JSON = json.dumps(DEFAULT_REDIRECT_CONFIG)


def upgrade() -> None:
    # --- campaigns table: new columns ---
    op.add_column(
        "campaigns",
        sa.Column("landing_slug", sa.String(32), nullable=True),
    )
    op.create_index(
        "idx_campaigns_landing_slug",
        "campaigns",
        ["landing_slug"],
        unique=True,
    )
    op.add_column(
        "campaigns",
        sa.Column("redirect_config", JSONB, nullable=True),
    )

    # --- campaign_templates table: new column ---
    op.add_column(
        "campaign_templates",
        sa.Column("default_redirect_config", JSONB, nullable=True),
    )

    # --- Update traffic template (id=1, code='traffic') ---
    op.execute(
        sa.text(
            """
            UPDATE campaign_templates
            SET modules = :modules ::jsonb,
                description_template = :desc,
                default_redirect_config = :rc ::jsonb
            WHERE id = 1 AND code = 'traffic'
            """
        ).bindparams(
            modules=MODULES_JSON,
            desc=TRAFFIC_DESCRIPTION,
            rc=REDIRECT_CONFIG_JSON,
        )
    )

    # --- Update save template (id=2, code='save') ---
    op.execute(
        sa.text(
            """
            UPDATE campaign_templates
            SET modules = :modules ::jsonb,
                description_template = :desc,
                default_redirect_config = :rc ::jsonb
            WHERE id = 2 AND code = 'save'
            """
        ).bindparams(
            modules=MODULES_JSON,
            desc=SAVE_DESCRIPTION,
            rc=REDIRECT_CONFIG_JSON,
        )
    )


def downgrade() -> None:
    op.drop_column("campaign_templates", "default_redirect_config")
    op.drop_index("idx_campaigns_landing_slug", table_name="campaigns")
    op.drop_column("campaigns", "redirect_config")
    op.drop_column("campaigns", "landing_slug")
