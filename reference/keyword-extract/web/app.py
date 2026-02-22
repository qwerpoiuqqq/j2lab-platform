"""
FastAPI 웹 앱 - 키워드 추출 서비스

엔드포인트:
- GET  /             : 메인 페이지 (index.html)
- POST /api/login    : 로그인
- POST /api/logout   : 로그아웃
- POST /api/jobs     : 작업 추가
- GET  /api/jobs     : 작업 목록
- POST /api/jobs/{id}/cancel : 작업 취소
- GET  /api/jobs/{id}/results : 작업 결과
- GET  /api/events   : SSE 스트림
"""

import asyncio
import csv
import io
import json
import os
import time
from typing import List, Optional

from fastapi import FastAPI, Request, Response, HTTPException, Cookie
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .proxy_pool import ProxyPool
from .session_manager import SessionManager, JobStatus, _safe_put

app = FastAPI(title="Keyword Extract Service")

# 전역 객체
_proxy_pool: Optional[ProxyPool] = None
_session_manager: Optional[SessionManager] = None

# 병렬 실행 제한 없음 (등록 즉시 실행)


def get_proxy_pool() -> ProxyPool:
    global _proxy_pool
    if _proxy_pool is None:
        settings_path = os.environ.get("SETTINGS_PATH", "settings.json")
        _proxy_pool = ProxyPool(settings_path)
    return _proxy_pool


def get_session_manager() -> SessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager(get_proxy_pool())
    return _session_manager


# ==================== Startup / Shutdown ====================

@app.on_event("startup")
async def startup():
    """서버 시작 시 초기화"""
    get_proxy_pool()
    get_session_manager()
    # 세션 정리 루프 시작
    asyncio.create_task(_cleanup_loop())
    print("[App] Keyword Extract Service started")


async def _cleanup_loop():
    """주기적 세션 정리 (30분마다)"""
    while True:
        await asyncio.sleep(1800)
        try:
            await get_session_manager().cleanup_expired()
        except Exception as e:
            print(f"[App] Cleanup error: {e}")


# ==================== Static Files ====================

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    """메인 페이지"""
    index_path = os.path.join(static_dir, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# ==================== Auth ====================

class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/login")
async def login(req: LoginRequest, response: Response):
    """로그인 → session_id 쿠키 설정"""
    sm = get_session_manager()
    session = await sm.login(req.username, req.password)

    if not session:
        raise HTTPException(status_code=401, detail="인증 실패")

    response.set_cookie(
        key="session_id",
        value=session.session_id,
        httponly=True,
        samesite="lax",
        max_age=3600,
    )

    return {
        "status": "ok",
        "username": session.username,
        "proxy_slot": session.proxy_slot,
        "is_admin": session.is_admin,
    }


@app.post("/api/logout")
async def logout(response: Response, session_id: str = Cookie(default=None)):
    """로그아웃 - 쿠키만 삭제, 세션은 서버에 유지 (작업 계속 실행)"""
    response.delete_cookie("session_id")
    return {"status": "ok"}


# ==================== Jobs ====================

class JobRequest(BaseModel):
    url: str
    target_count: int = 100
    max_rank: int = 50
    min_rank: int = 1
    name_keyword_ratio: float = 0.30


class BulkJobRequest(BaseModel):
    urls: List[str]
    target_count: int = 100
    max_rank: int = 50
    min_rank: int = 1
    name_keyword_ratio: float = 0.30


@app.post("/api/jobs")
async def add_job(req: JobRequest, session_id: str = Cookie(default=None)):
    """작업 추가"""
    session = await _get_session_or_401(session_id)
    sm = get_session_manager()

    job = await sm.add_job(session_id, req.url, req.target_count, req.max_rank, req.min_rank, req.name_keyword_ratio)
    if not job:
        raise HTTPException(status_code=500, detail="작업 추가 실패")

    # 즉시 실행
    pp = get_proxy_pool()
    _start_next_jobs(session, pp)

    return job.to_dict()


@app.post("/api/jobs/bulk")
async def add_bulk_jobs(req: BulkJobRequest, session_id: str = Cookie(default=None)):
    """대량 작업 추가 (여러 URL 한번에)"""
    session = await _get_session_or_401(session_id)
    sm = get_session_manager()
    pp = get_proxy_pool()

    added = []
    for url in req.urls:
        url = url.strip()
        if not url:
            continue
        job = await sm.add_job(
            session_id, url, req.target_count, req.max_rank,
            req.min_rank, req.name_keyword_ratio
        )
        if job:
            added.append(job.to_dict())

    # 전부 등록 후 한번에 실행
    _start_next_jobs(session, pp)

    return {"jobs": added, "count": len(added)}


@app.get("/api/jobs")
async def list_jobs(session_id: str = Cookie(default=None)):
    """내 작업 목록"""
    await _get_session_or_401(session_id)
    sm = get_session_manager()
    jobs = await sm.get_jobs(session_id)
    return {"jobs": jobs}


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, session_id: str = Cookie(default=None)):
    """작업 취소"""
    await _get_session_or_401(session_id)
    sm = get_session_manager()
    success = await sm.cancel_job(session_id, job_id)
    if not success:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없거나 취소할 수 없습니다")
    return {"status": "ok"}


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str, session_id: str = Cookie(default=None)):
    """작업 삭제"""
    await _get_session_or_401(session_id)
    sm = get_session_manager()
    success = await sm.delete_job(session_id, job_id)
    if not success:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    return {"status": "ok"}


@app.get("/api/jobs/{job_id}/results")
async def get_results(job_id: str, session_id: str = Cookie(default=None)):
    """작업 결과 (JSON)"""
    await _get_session_or_401(session_id)
    sm = get_session_manager()
    results = await sm.get_job_results(session_id, job_id)
    if results is None:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    return {"results": results}


@app.get("/api/jobs/{job_id}/results/csv")
async def get_results_csv(job_id: str, session_id: str = Cookie(default=None)):
    """작업 결과 CSV 다운로드"""
    await _get_session_or_401(session_id)
    sm = get_session_manager()
    results = await sm.get_job_results(session_id, job_id)
    if results is None:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")

    # CSV 생성
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["키워드", "순위", "키워드 유형", "상태"])
    for r in results:
        writer.writerow([
            r.get("keyword", ""),
            r.get("rank", ""),
            r.get("keyword_type", ""),
            r.get("status", ""),
        ])

    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8-sig",
        headers={
            "Content-Disposition": f"attachment; filename=results_{job_id[:8]}.csv",
        },
    )


# ==================== SSE ====================

@app.get("/api/events")
async def sse_events(request: Request, session_id: str = Cookie(default=None)):
    """SSE 스트림 (실시간 진행)"""
    session = await _get_session_or_401(session_id)

    async def event_generator():
        """이벤트 생성기"""
        # 연결 확인 이벤트
        yield _sse_format("connected", {"username": session.username})

        while True:
            # 클라이언트 연결 해제 체크
            if await request.is_disconnected():
                break

            try:
                # 큐에서 이벤트 대기 (5초 타임아웃 → heartbeat)
                event = await asyncio.wait_for(
                    session.event_queue.get(), timeout=5.0
                )
                event_type = event.get("type", "message")
                yield _sse_format(event_type, event)
            except asyncio.TimeoutError:
                # Heartbeat
                yield _sse_format("heartbeat", {"time": time.time()})
            except Exception as e:
                print(f"[SSE] Error: {e}")
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse_format(event_type: str, data: dict) -> str:
    """SSE 메시지 포맷"""
    json_data = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {json_data}\n\n"


# ==================== Parallel Job Execution ====================

def _start_next_jobs(session, proxy_pool: ProxyPool):
    """대기 중인 작업을 즉시 시작 (제한 없음)"""
    for job in session.jobs.values():
        if job.status == JobStatus.QUEUED:
            task = asyncio.create_task(_run_job(session, job, proxy_pool))
            job._task = task


async def _run_job(session, job, proxy_pool: ProxyPool):
    """개별 작업 실행"""
    from .async_smart_worker import AsyncSmartWorker

    job.status = JobStatus.RUNNING
    job.started_at = time.time()

    # 실행 중 상태 디스크 저장
    get_session_manager()._save_job(session.username, job)

    # 세션에 상태 변경 알림
    _safe_put(session.event_queue, {
        "type": "job_started",
        "job_id": job.job_id,
        "data": job.to_dict(),
        "timestamp": time.time(),
    })

    worker = None
    try:
        # 프록시 설정
        proxies = proxy_pool.get_slot_proxy_dicts(session.proxy_slot)

        worker = AsyncSmartWorker(
            url=job.url,
            target_count=job.target_count,
            event_queue=session.event_queue,
            job_id=job.job_id,
            max_rank=job.max_rank,
            min_rank=job.min_rank,
            name_keyword_ratio=job.name_keyword_ratio,
            proxies=proxies,
            use_api_mode=True,
            use_own_ip=proxy_pool.use_own_ip,
            user_slot=session.proxy_slot,
            total_instances=proxy_pool.MAX_SLOTS,
            modifiers=proxy_pool.modifiers,
            gemini_api_key=proxy_pool.gemini_api_key,
        )

        # 워커를 job에 저장 (취소용)
        job._worker = worker

        # 워커 실행
        await worker.run()

        # 결과 수집 (취소되지 않은 경우)
        if job.status != JobStatus.CANCELLED:
            results = []
            for r in worker.all_results:
                results.append({
                    "keyword": r.keyword,
                    "rank": r.rank,
                    "keyword_type": "PLT" if (getattr(r, 'source', None) == "name" and r.rank == 1 and (getattr(r, 'total_count', None) is None or getattr(r, 'total_count', None) == 1)) else "PLL",
                    "status": r.status,
                })
            job.results = results
            job.status = JobStatus.COMPLETED
            job.completed_at = time.time()

            # place_name 설정
            if hasattr(worker, '_place_name'):
                job.place_name = worker._place_name

    except asyncio.CancelledError:
        if worker:
            worker.stop()
            # 부분 결과 수집
            try:
                results = []
                for r in worker.all_results:
                    results.append({
                        "keyword": r.keyword,
                        "rank": r.rank,
                        "keyword_type": "PLT" if (getattr(r, 'source', None) == "name" and r.rank == 1 and (getattr(r, 'total_count', None) is None or getattr(r, 'total_count', None) == 1)) else "PLL",
                        "status": r.status,
                    })
                job.results = results
            except Exception:
                pass
        if job.status != JobStatus.CANCELLED:
            job.status = JobStatus.CANCELLED
            job.completed_at = time.time()
    except Exception as e:
        import traceback
        traceback.print_exc()
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        job.completed_at = time.time()
    finally:
        job._worker = None
        job._task = None

        # 디스크에 결과 저장
        sm = get_session_manager()
        sm._save_job(session.username, job)

        # 완료/실패/취소 알림
        _safe_put(session.event_queue, {
            "type": "job_finished",
            "job_id": job.job_id,
            "data": job.to_dict(),
            "timestamp": time.time(),
        })

        # 대기 중인 다음 작업 자동 시작
        _start_next_jobs(session, proxy_pool)


# ==================== Helpers ====================

async def _get_session_or_401(session_id: Optional[str]):
    """세션 검증"""
    if not session_id:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")

    sm = get_session_manager()
    session = await sm.get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="세션이 만료되었습니다")

    return session


async def _get_admin_session_or_403(session_id: Optional[str]):
    """어드민 세션 검증"""
    session = await _get_session_or_401(session_id)
    if not session.is_admin:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    return session


# ==================== Admin ====================

class CreateUserRequest(BaseModel):
    username: str
    password: str


@app.get("/api/admin/users")
async def list_users(session_id: str = Cookie(default=None)):
    """유저 목록 (어드민 전용)"""
    await _get_admin_session_or_403(session_id)
    sm = get_session_manager()
    users = sm.list_users()
    return {"users": users}


@app.post("/api/admin/users")
async def create_user(req: CreateUserRequest, session_id: str = Cookie(default=None)):
    """유저 생성 (어드민 전용)"""
    await _get_admin_session_or_403(session_id)
    sm = get_session_manager()
    success = sm.create_user(req.username, req.password)
    if not success:
        raise HTTPException(status_code=400, detail="이미 존재하는 사용자입니다")
    return {"status": "ok"}


@app.delete("/api/admin/users/{username}")
async def delete_user(username: str, session_id: str = Cookie(default=None)):
    """유저 삭제 (어드민 전용)"""
    await _get_admin_session_or_403(session_id)
    sm = get_session_manager()
    success = sm.delete_user(username)
    if not success:
        raise HTTPException(status_code=400, detail="삭제할 수 없는 사용자입니다")
    return {"status": "ok"}
