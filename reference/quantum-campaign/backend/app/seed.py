"""초기 데이터 시딩 스크립트."""

from app.database import SessionLocal, engine, Base
from app.models import CampaignTemplate


# 트래픽 링크 (해시태그 포함)
TRAFFIC_LINKS = [
    "https://nid.naver.com/nidlogin/login?mode=form&url=https%3A%2F%2Fm.naver.com%2F#cpc_detail_place",
    "https://link.naver.com/bridge?url=https%3A%2F%2Fm.naver.com%2F#cpc_detail_place",
    "https://app.map.naver.com/launchApp/map?tab=discovery#cpc_detail_place",
]

# 저장하기 링크 (해시태그 포함)
SAVE_LINKS = [
    "https://nid.naver.com/nidlogin/login?mode=form&url=https%3A%2F%2Fm.naver.com%2F#place_save_tab",
    "https://link.naver.com/bridge?url=https%3A%2F%2Fm.naver.com%2F#place_save_tab",
    "https://app.map.naver.com/launchApp/map?tab=discovery#place_save_tab",
]

# 공통 힌트 텍스트
COMMON_HINT = "참여 방법에 있는 출발지에서 목적지까지 [가장 빠른] 걸음 수 맞추기"

# 해시태그
TRAFFIC_HASHTAG = "#cpc_detail_place"
SAVE_HASHTAG = "#place_save_tab"

# 트래픽 타입 템플릿
TRAFFIC_TEMPLATE = """{{image|https://i.ibb.co/DgVqGSnW/image.png}}

1. 하단의 검색키워드 복사 후 미션페이지 클릭
2. 네이버 홈에서 키워드 붙여 넣어 검색 후 1~2페이지내에 있는 [&상호명&] 클릭
3. 플레이스에서 [지도] 탭 클릭 → [지도앱으로 보기] 버튼 클릭
4. 플레이스 탭에서 [도착] 버튼 클릭
5. 출발지를 [&명소명&]으로 설정 후 [도보] 설정 후 [가장빠른] 걸음 수 맞추기

[주의사항]
이미 참여한 이력이 있다면 리워드가 지급되지 않을 수 있습니다.
WIFI가 아닌 환경에서는 데이터 이용료가 발생할 수 있습니다."""

# 저장하기 타입 템플릿
SAVE_TEMPLATE = """{{image|https://i.ibb.co/RGW629jv/image.png}}

1. 하단의 검색키워드 복사 후 미션페이지 클릭
2. 네이버 홈에서 키워드 붙여 넣어 검색 후 1~2페이지내에 있는 [&상호명&] 클릭
3. 플레이스에서 [지도] 탭 클릭 → [지도앱으로 보기] 버튼 클릭
4. 저장하기 버튼 클릭하여 완료한 후 [도착] 버튼 클릭
5. 출발지를 [&명소명&]으로 설정 후 [도보] 설정 후 [가장빠른] 걸음 수 맞추기

[주의사항]
이미 참여한 이력이 있다면 리워드가 지급되지 않을 수 있습니다.
WIFI가 아닌 환경에서는 데이터 이용료가 발생할 수 있습니다."""


def create_tables():
    """모든 테이블 생성."""
    Base.metadata.create_all(bind=engine)
    print("모든 테이블이 생성되었습니다.")


def seed_templates():
    """초기 템플릿 데이터 삽입."""
    db = SessionLocal()
    try:
        # 기존 템플릿 확인
        existing = db.query(CampaignTemplate).count()
        if existing > 0:
            print(f"이미 {existing}개의 템플릿이 존재합니다. 시딩을 건너뜁니다.")
            return

        # 트래픽 템플릿 (landmark + steps 모듈 사용)
        traffic = CampaignTemplate(
            type_name="트래픽",
            description_template=TRAFFIC_TEMPLATE,
            hint_text=COMMON_HINT,
            campaign_type_selection="플레이스 퀴즈",
            links=TRAFFIC_LINKS,
            hashtag=TRAFFIC_HASHTAG,
            image_url_200x600="https://i.ibb.co/DgVqGSnW/image.png",
            image_url_720x780=None,
            modules=["landmark", "steps"],
            is_active=True,
        )

        # 저장하기 템플릿 (landmark + steps 모듈 사용)
        save = CampaignTemplate(
            type_name="저장하기",
            description_template=SAVE_TEMPLATE,
            hint_text=COMMON_HINT,
            campaign_type_selection="검색 후 정답 입력",
            links=SAVE_LINKS,
            hashtag=SAVE_HASHTAG,
            image_url_200x600="https://i.ibb.co/RGW629jv/image.png",
            image_url_720x780=None,
            modules=["landmark", "steps"],
            is_active=True,
        )

        db.add(traffic)
        db.add(save)
        db.commit()

        print("템플릿 2개가 성공적으로 삽입되었습니다:")
        print("  - 트래픽 (플레이스 퀴즈)")
        print("  - 저장하기 (검색 후 정답 입력)")

    except Exception as e:
        db.rollback()
        print(f"시딩 실패: {e}")
        raise
    finally:
        db.close()


def migrate_templates_add_modules():
    """기존 템플릿에 modules 필드 추가 마이그레이션.

    Phase 3.2에서 추가된 modules 필드를 기존 템플릿에 설정합니다.
    - 트래픽, 저장하기: ["landmark", "steps"]
    - 그 외: []
    """
    db = SessionLocal()
    try:
        templates = db.query(CampaignTemplate).all()
        updated_count = 0

        for template in templates:
            # modules 필드가 None이거나 빈 리스트인 경우만 업데이트
            if template.modules is None or template.modules == []:
                if template.type_name in ["트래픽", "저장하기"]:
                    template.modules = ["landmark", "steps"]
                else:
                    template.modules = []

                # is_active 필드도 설정
                if template.is_active is None:
                    template.is_active = True

                updated_count += 1

        if updated_count > 0:
            db.commit()
            print(f"{updated_count}개 템플릿이 마이그레이션되었습니다.")
        else:
            print("마이그레이션할 템플릿이 없습니다.")

    except Exception as e:
        db.rollback()
        print(f"마이그레이션 실패: {e}")
        raise
    finally:
        db.close()


def migrate_templates_add_conversion_text():
    """기존 DB에 conversion_text_template 컬럼 추가."""
    from sqlalchemy import inspect, text

    db = SessionLocal()
    try:
        inspector = inspect(engine)
        columns = [col["name"] for col in inspector.get_columns("campaign_templates")]
        if "conversion_text_template" not in columns:
            with engine.connect() as conn:
                conn.execute(text(
                    "ALTER TABLE campaign_templates ADD COLUMN conversion_text_template TEXT DEFAULT NULL"
                ))
                conn.commit()
            print("conversion_text_template 컬럼이 추가되었습니다.")
        else:
            print("conversion_text_template 컬럼이 이미 존재합니다.")

    except Exception as e:
        db.rollback()
        print(f"conversion_text_template 마이그레이션 실패: {e}")
    finally:
        db.close()


def migrate_keywords_to_pool():
    """기존 캠페인의 original_keywords → KeywordPool 마이그레이션.

    original_keywords가 있지만 KeywordPool이 비어있는 캠페인 대상.
    서버 시작 시 자동 실행됩니다.
    """
    from app.models.campaign import Campaign
    from app.models.keyword import KeywordPool

    db = SessionLocal()
    try:
        campaigns = db.query(Campaign).filter(
            Campaign.original_keywords.isnot(None),
            Campaign.original_keywords != '',
        ).all()

        migrated_count = 0
        for campaign in campaigns:
            existing_count = db.query(KeywordPool).filter(
                KeywordPool.campaign_id == campaign.id
            ).count()
            if existing_count > 0:
                continue

            keywords = [kw.strip() for kw in campaign.original_keywords.split(',') if kw.strip()]
            seen = set()
            for keyword in keywords:
                if keyword not in seen:
                    kw_record = KeywordPool(
                        campaign_id=campaign.id,
                        keyword=keyword,
                        is_used=False,
                    )
                    db.add(kw_record)
                    seen.add(keyword)

            if seen:
                migrated_count += 1
                print(f"  - {campaign.place_name}: {len(seen)}개 키워드 마이그레이션")

        if migrated_count > 0:
            db.commit()
            print(f"총 {migrated_count}개 캠페인의 키워드가 마이그레이션되었습니다.")
        else:
            print("마이그레이션할 키워드가 없습니다.")

    except Exception as e:
        db.rollback()
        print(f"키워드 마이그레이션 실패: {e}")
    finally:
        db.close()


def reset_keyword_usage():
    """모든 키워드 사용 상태 초기화 (1회성).

    - KeywordPool: is_used=False, used_at=NULL
    - Campaign: last_keyword_change=NULL
    - 파일 플래그로 중복 실행 방지 (/app/data/.keyword_reset_done)
    """
    import os
    from sqlalchemy import update

    from app.models.campaign import Campaign
    from app.models.keyword import KeywordPool

    flag_path = os.path.join(os.environ.get("DATA_DIR", "/app/data"), ".keyword_reset_done")
    if os.path.exists(flag_path):
        print("키워드 초기화: 이미 실행됨 (플래그 존재)")
        return

    db = SessionLocal()
    try:
        kw_count = db.query(KeywordPool).filter(KeywordPool.is_used == True).count()
        if kw_count == 0:
            print("키워드 초기화: 사용된 키워드 없음, 건너뜀")
        else:
            db.execute(
                update(KeywordPool).values(is_used=False, used_at=None)
            )
            db.execute(
                update(Campaign).values(last_keyword_change=None)
            )
            db.commit()
            print(f"키워드 초기화 완료: {kw_count}개 키워드 is_used=False, last_keyword_change=NULL")

        # 플래그 파일 생성 (재실행 방지)
        os.makedirs(os.path.dirname(flag_path), exist_ok=True)
        with open(flag_path, "w") as f:
            from datetime import datetime
            f.write(f"reset at {datetime.now().isoformat()}\n")
        print(f"플래그 파일 생성: {flag_path}")

    except Exception as e:
        db.rollback()
        print(f"키워드 초기화 실패: {e}")
    finally:
        db.close()


def migrate_status_to_english():
    """기존 한글 status를 영문 코드로 마이그레이션.

    DB에 '진행중', '일일소진' 등 한글 상태값이 있으면 영문으로 변환합니다.
    서버 시작 시 자동 실행됩니다.
    """
    from app.models.campaign import Campaign
    from app.utils.status_map import SUPERAP_TO_INTERNAL

    db = SessionLocal()
    try:
        updated_count = 0
        for korean, english in SUPERAP_TO_INTERNAL.items():
            campaigns = db.query(Campaign).filter(Campaign.status == korean).all()
            for c in campaigns:
                c.status = english
                updated_count += 1

        if updated_count > 0:
            db.commit()
            print(f"상태 마이그레이션 완료: {updated_count}개 캠페인 (한글→영문)")
        else:
            print("상태 마이그레이션: 변환할 한글 상태 없음")

    except Exception as e:
        db.rollback()
        print(f"상태 마이그레이션 실패: {e}")
    finally:
        db.close()


def init_db():
    """DB 초기화: 테이블 생성 + 시딩."""
    create_tables()
    seed_templates()


def init_db_with_migration():
    """DB 초기화: 테이블 생성 + 시딩 + 마이그레이션."""
    create_tables()
    seed_templates()
    migrate_templates_add_modules()
    migrate_templates_add_conversion_text()
    migrate_status_to_english()


if __name__ == "__main__":
    init_db_with_migration()
