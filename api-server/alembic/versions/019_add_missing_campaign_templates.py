"""Add missing campaign templates from quantum-campaign DB.

Revision ID: 019_add_missing_campaign_templates
Revises: 018_add_missing_indexes

Adds 3 templates that existed in quantum but were missing from unified:
- 공유+길찾기+트래픽 (share+navigation+traffic)
- 트래픽1 (traffic variant with different links)
- 저장하기1 (save variant with different links)

Also updates existing templates to match quantum DB (description_template, links).
"""

from alembic import op
import sqlalchemy as sa

revision = "019_add_missing_templates"
down_revision = "018_add_missing_indexes"
branch_labels = None
depends_on = None

# --- Link data from quantum.db ---

TRAFFIC1_LINKS = [
    "https://link.naver.com/bridge?url=https%3A%2F%2Fnid.naver.com%2Fnidlogin.login%3Furl%3Dhttps%253A%252F%252Fm.naver.com%252F&dst=naversearchapp%3A%2F%2Finappbrowser%3Furl%3Dhttps%253A%252F%252Fnid.naver.com%252Fnidlogin.login%253Furl%253Dhttps%25253A%25252F%25252Fm.naver.com%25252F%26version%3D10#cpc_detail_place",
    "https://link.naver.com/bridge?dst=nmap%3A%2F%2Ffavorite%2Fedit%3Ftype%3Detc%26appname%3Dcom.nhn.android.nmap&url=https%3A%2F%2Fapp.map.naver.com%2FlaunchApp%2Ffavorite%2Fedit%3Ftype%3Detc#cpc_detail_place",
]

SAVE1_LINKS = [
    "https://link.naver.com/bridge?url=https%3A%2F%2Fnid.naver.com%2Fnidlogin.login%3Furl%3Dhttps%253A%252F%252Fm.naver.com%252F&dst=naversearchapp%3A%2F%2Finappbrowser%3Furl%3Dhttps%253A%252F%252Fnid.naver.com%252Fnidlogin.login%253Furl%253Dhttps%25253A%25252F%25252Fm.naver.com%25252F%26version%3D10#place_save_tab",
    "https://link.naver.com/bridge?dst=nmap%3A%2F%2Ffavorite%2Fedit%3Ftype%3Detc%26appname%3Dcom.nhn.android.nmap&url=https%3A%2F%2Fapp.map.naver.com%2FlaunchApp%2Ffavorite%2Fedit%3Ftype%3Detc#place_save_tab",
]

LANDMARK_LINKS = [
    "https://nid.naver.com/nidlogin.login?mode=form&url=https%3A%2F%2Fm.naver.com%2F",
]

TRAFFIC_TEMPLATE = """[참여 방법]
{{image|https://i.ibb.co/DgVqGSnW/image.png}}

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
3. 플레이스에서 [지도] 탭 클릭 -> [지도앱으로 보기] 버튼 클릭
4. 저장하기 버튼 클릭하여 완료한 후 [도착] 버튼 클릭
5. 출발지를 [&명소명&]으로 설정 후 [도보] 설정 후 [가장빠른] 걸음 수 맞추기

[주의사항]
이미 참여한 이력이 있다면 리워드가 지급되지 않을 수 있습니다.
WIFI가 아닌 환경에서는 데이터 이용료가 발생할 수 있습니다."""

LANDMARK_TEMPLATE = """[참여방법]
1. 미션 페이지 클릭 후 네이버 홈에서 키워드 검색
2. 플레이스 1~5페이지 이내에 있는 [&상호명&] 클릭 -> 주변 -> 명소 클릭
3. &명소순번&번째 장소를 입력하면 완료!

[주의사항]
미션 플레이스가 조회되지 않을 경우 리워드가 지급되지 않습니다.
이미 참여한 이력이 있다면 리워드가 지급되지 않을 수 있습니다.
WIFI가 아닌 환경에서는 데이터 이용료가 발생할 수 있습니다."""

COMMON_HINT = "참여 방법에 있는 출발지에서 목적지까지 [가장 빠른] 걸음 수 맞추기"


def upgrade() -> None:
    import json

    conn = op.get_bind()

    # Update existing traffic template description to match quantum DB
    conn.execute(sa.text(
        "UPDATE campaign_templates SET description_template = :desc "
        "WHERE code = 'traffic'"
    ), {"desc": TRAFFIC_TEMPLATE})

    # Update existing save template description to match quantum DB
    conn.execute(sa.text(
        "UPDATE campaign_templates SET description_template = :desc "
        "WHERE code = 'save'"
    ), {"desc": SAVE_TEMPLATE})

    # Update existing landmark template (명소) description and conversion text
    conn.execute(sa.text(
        "UPDATE campaign_templates SET "
        "description_template = :desc, "
        "hint_text = :hint, "
        "conversion_text_template = :conv, "
        "links = :links "
        "WHERE code = '명소' OR type_name = '명소'"
    ), {
        "desc": LANDMARK_TEMPLATE,
        "hint": "&명소순번&번째 명소 이름 맞추기",
        "conv": "&명소명&",
        "links": json.dumps(LANDMARK_LINKS),
    })

    # Insert missing templates using direct SQL to avoid JSONB double-encoding
    # (op.bulk_insert with sa.JSON columns causes json.dumps to be applied twice)

    INSERT_SQL = sa.text("""
        INSERT INTO campaign_templates
            (code, type_name, description_template, hint_text,
             campaign_type_selection, links, hashtag,
             image_url_200x600, image_url_720x780,
             conversion_text_template, steps_start, modules, is_active)
        SELECT :code, :type_name, :desc, :hint,
               :campaign_type_selection, :links::jsonb, :hashtag,
               :image_url_200x600, :image_url_720x780,
               :conversion_text_template, :steps_start, :modules::jsonb, :is_active
        WHERE NOT EXISTS (
            SELECT 1 FROM campaign_templates WHERE code = :code
        )
    """)

    # 공유+길찾기+트래픽
    conn.execute(INSERT_SQL, {
        "code": "share_directions_traffic",
        "type_name": "공유+길찾기+트래픽",
        "desc": "미션 페이지 참고하여 리워드 퀴즈 풀기",
        "hint": "미션 페이지에 나와있는 가이드에 따라서 진행 후 정답 입력",
        "campaign_type_selection": "플레이스 퀴즈",
        "links": json.dumps([]),
        "hashtag": "#cpc_detail_place",
        "image_url_200x600": "https://i.ibb.co/DgVqGSnW/image.png",
        "image_url_720x780": None,
        "conversion_text_template": None,
        "steps_start": None,
        "modules": json.dumps(["place_info", "landmark", "steps"]),
        "is_active": True,
    })

    # 트래픽1
    conn.execute(INSERT_SQL, {
        "code": "traffic1",
        "type_name": "트래픽1",
        "desc": TRAFFIC_TEMPLATE,
        "hint": COMMON_HINT,
        "campaign_type_selection": "플레이스 퀴즈",
        "links": json.dumps(TRAFFIC1_LINKS),
        "hashtag": "#cpc_detail_place",
        "image_url_200x600": None,
        "image_url_720x780": None,
        "conversion_text_template": None,
        "steps_start": None,
        "modules": json.dumps(["place_info", "landmark", "steps"]),
        "is_active": True,
    })

    # 저장하기1
    conn.execute(INSERT_SQL, {
        "code": "save1",
        "type_name": "저장하기1",
        "desc": SAVE_TEMPLATE,
        "hint": COMMON_HINT,
        "campaign_type_selection": "검색 후 정답 입력",
        "links": json.dumps(SAVE1_LINKS),
        "hashtag": "#place_save_tab",
        "image_url_200x600": None,
        "image_url_720x780": None,
        "conversion_text_template": None,
        "steps_start": None,
        "modules": json.dumps(["place_info", "landmark", "steps"]),
        "is_active": True,
    })


def downgrade() -> None:
    op.execute(
        "DELETE FROM campaign_templates WHERE code IN "
        "('share_directions_traffic', 'traffic1', 'save1')"
    )
