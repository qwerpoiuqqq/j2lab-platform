import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

# SQLite connection
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite only
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """데이터베이스 초기화 및 마이그레이션.

    테이블이 없으면 생성하고, 누락된 컬럼이 있으면 추가합니다.
    """
    # 모든 모델 임포트 (테이블 생성을 위해)
    from app.models import account, campaign, keyword, template  # noqa: F401

    # 테이블 생성 (없는 테이블만)
    Base.metadata.create_all(bind=engine)

    # 누락된 컬럼 자동 추가
    _migrate_missing_columns()


def _migrate_missing_columns():
    """모델에 정의된 컬럼 중 DB에 없는 컬럼을 자동으로 추가."""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            continue

        existing_columns = {col["name"] for col in inspector.get_columns(table_name)}

        for column in table.columns:
            if column.name not in existing_columns:
                col_type = column.type.compile(engine.dialect)
                nullable = "NULL" if column.nullable else "NOT NULL"
                default = ""
                if column.default is not None and hasattr(column.default, "arg") and isinstance(column.default.arg, (str, int, float)):
                    default = f" DEFAULT {column.default.arg!r}"

                alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type} {nullable}{default}"
                try:
                    with engine.connect() as conn:
                        conn.execute(text(alter_sql))
                        conn.commit()
                    logger.info(f"[마이그레이션] {table_name}.{column.name} 컬럼 추가됨")
                except Exception as e:
                    logger.warning(f"[마이그레이션] {table_name}.{column.name} 추가 실패: {e}")
