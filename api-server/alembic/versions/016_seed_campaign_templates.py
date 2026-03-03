"""Seed campaign templates from quantum-campaign reference.

Revision ID: 016_seed_campaign_templates
Revises: 015_conv_threshold_flag

Inserts the two essential campaign templates (traffic + save) that were
present in quantum-campaign but missing from unified-platform.
"""

from alembic import op
import sqlalchemy as sa

revision = "016_seed_campaign_templates"
down_revision = "015_conv_threshold_flag"
branch_labels = None
depends_on = None

# --- Template data from reference/quantum-campaign/backend/app/seed.py ---

TRAFFIC_LINKS = [
    "https://nid.naver.com/nidlogin/login?mode=form&url=https%3A%2F%2Fm.naver.com%2F#cpc_detail_place",
    "https://link.naver.com/bridge?url=https%3A%2F%2Fm.naver.com%2F#cpc_detail_place",
    "https://app.map.naver.com/launchApp/map?tab=discovery#cpc_detail_place",
]

SAVE_LINKS = [
    "https://nid.naver.com/nidlogin/login?mode=form&url=https%3A%2F%2Fm.naver.com%2F#place_save_tab",
    "https://link.naver.com/bridge?url=https%3A%2F%2Fm.naver.com%2F#place_save_tab",
    "https://app.map.naver.com/launchApp/map?tab=discovery#place_save_tab",
]

COMMON_HINT = "참여 방법에 있는 출발지에서 목적지까지 [가장 빠른] 걸음 수 맞추기"

TRAFFIC_TEMPLATE = """{{image|https://i.ibb.co/DgVqGSnW/image.png}}

1. 하단의 검색키워드 복사 후 미션페이지 클릭
2. 네이버 홈에서 키워드 붙여 넣어 검색 후 1~2페이지내에 있는 [&상호명&] 클릭
3. 플레이스에서 [지도] 탭 클릭 → [지도앱으로 보기] 버튼 클릭
4. 플레이스 탭에서 [도착] 버튼 클릭
5. 출발지를 [&명소명&]으로 설정 후 [도보] 설정 후 [가장빠른] 걸음 수 맞추기

[주의사항]
이미 참여한 이력이 있다면 리워드가 지급되지 않을 수 있습니다.
WIFI가 아닌 환경에서는 데이터 이용료가 발생할 수 있습니다."""

SAVE_TEMPLATE = """{{image|https://i.ibb.co/RGW629jv/image.png}}

1. 하단의 검색키워드 복사 후 미션페이지 클릭
2. 네이버 홈에서 키워드 붙여 넣어 검색 후 1~2페이지내에 있는 [&상호명&] 클릭
3. 플레이스에서 [지도] 탭 클릭 → [지도앱으로 보기] 버튼 클릭
4. 저장하기 버튼 클릭하여 완료한 후 [도착] 버튼 클릭
5. 출발지를 [&명소명&]으로 설정 후 [도보] 설정 후 [가장빠른] 걸음 수 맞추기

[주의사항]
이미 참여한 이력이 있다면 리워드가 지급되지 않을 수 있습니다.
WIFI가 아닌 환경에서는 데이터 이용료가 발생할 수 있습니다."""


def upgrade() -> None:
    import json

    campaign_templates = sa.table(
        "campaign_templates",
        sa.column("code", sa.String),
        sa.column("type_name", sa.String),
        sa.column("description_template", sa.Text),
        sa.column("hint_text", sa.Text),
        sa.column("campaign_type_selection", sa.String),
        sa.column("links", sa.JSON),
        sa.column("hashtag", sa.String),
        sa.column("image_url_200x600", sa.Text),
        sa.column("image_url_720x780", sa.Text),
        sa.column("conversion_text_template", sa.Text),
        sa.column("steps_start", sa.Text),
        sa.column("modules", sa.JSON),
        sa.column("is_active", sa.Boolean),
    )

    # Only insert if table is empty (idempotent)
    conn = op.get_bind()
    count = conn.execute(
        sa.text("SELECT COUNT(*) FROM campaign_templates")
    ).scalar()

    if count == 0:
        op.bulk_insert(campaign_templates, [
            {
                "code": "traffic",
                "type_name": "트래픽",
                "description_template": TRAFFIC_TEMPLATE,
                "hint_text": COMMON_HINT,
                "campaign_type_selection": "플레이스 퀴즈",
                "links": json.dumps(TRAFFIC_LINKS),
                "hashtag": "#cpc_detail_place",
                "image_url_200x600": "https://i.ibb.co/DgVqGSnW/image.png",
                "image_url_720x780": None,
                "conversion_text_template": None,
                "steps_start": None,
                "modules": json.dumps(["landmark", "steps"]),
                "is_active": True,
            },
            {
                "code": "save",
                "type_name": "저장하기",
                "description_template": SAVE_TEMPLATE,
                "hint_text": COMMON_HINT,
                "campaign_type_selection": "검색 후 정답 입력",
                "links": json.dumps(SAVE_LINKS),
                "hashtag": "#place_save_tab",
                "image_url_200x600": "https://i.ibb.co/RGW629jv/image.png",
                "image_url_720x780": None,
                "conversion_text_template": None,
                "steps_start": None,
                "modules": json.dumps(["landmark", "steps"]),
                "is_active": True,
            },
        ])


def downgrade() -> None:
    op.execute(
        "DELETE FROM campaign_templates WHERE code IN ('traffic', 'save')"
    )
