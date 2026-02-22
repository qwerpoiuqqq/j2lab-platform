import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import init_db
from app.routers import upload
from app.routers.accounts import router as accounts_router
from app.routers.campaigns import router as campaigns_router
from app.routers.dashboard import router as dashboard_router
from app.routers.templates import router as templates_router, modules_router
from app.routers.scheduler_api import router as scheduler_router
from app.modules.registry import register_default_modules
from app.seed import migrate_keywords_to_pool, migrate_status_to_english, reset_keyword_usage
from app.services.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작/종료 시 실행되는 이벤트."""
    # DB 초기화 및 마이그레이션
    init_db()
    # 기존 캠페인 키워드 → KeywordPool 마이그레이션
    migrate_keywords_to_pool()
    # 한글 상태 → 영문 상태 마이그레이션
    migrate_status_to_english()
    # 키워드 사용 상태 1회성 초기화 (플래그 파일로 중복 실행 방지)
    reset_keyword_usage()
    # 시작 시 모듈 등록
    register_default_modules()
    # 스케줄러 시작
    start_scheduler()
    logger.info("애플리케이션 시작 완료")
    yield
    # 종료 시 스케줄러 정지
    stop_scheduler()
    logger.info("애플리케이션 종료")


app = FastAPI(
    title="Quantum Campaign Automation",
    description="superap.io campaign automation system",
    version="0.1.0",
    lifespan=lifespan,
)

# Routers
app.include_router(accounts_router)
app.include_router(upload.router)
app.include_router(campaigns_router)
app.include_router(dashboard_router)
app.include_router(templates_router)
app.include_router(modules_router)
app.include_router(scheduler_router)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 글로벌 에러 핸들러
# ============================================================

@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """데이터베이스 오류 글로벌 핸들러."""
    logger.error(f"DB 오류 [{request.method} {request.url.path}]: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "데이터베이스 오류가 발생했습니다. 잠시 후 다시 시도해주세요."},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """예기치 않은 오류 글로벌 핸들러."""
    logger.error(f"예기치 않은 오류 [{request.method} {request.url.path}]: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "서버 내부 오류가 발생했습니다."},
    )


# ============================================================
# 요청 로깅 미들웨어
# ============================================================

@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """모든 요청에 대한 로깅 미들웨어."""
    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000

    if duration_ms > 5000:
        logger.warning(
            f"느린 요청: {request.method} {request.url.path} "
            f"→ {response.status_code} ({duration_ms:.0f}ms)"
        )
    elif response.status_code >= 400:
        logger.warning(
            f"에러 응답: {request.method} {request.url.path} "
            f"→ {response.status_code} ({duration_ms:.0f}ms)"
        )

    return response


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Quantum Campaign Automation API",
        "version": "0.1.0",
        "docs": "/docs"
    }
