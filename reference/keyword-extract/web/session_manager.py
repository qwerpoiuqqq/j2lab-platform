"""
세션 및 대기열 관리 모듈

- 최대 5개 동시 세션
- 세션별 독립 프록시 슬롯
- 작업 대기열 (FIFO)
- SSE 이벤트 큐
"""

import asyncio
import json
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum

from .proxy_pool import ProxyPool


def _safe_put(queue: asyncio.Queue, event: dict):
    """큐에 비블로킹으로 이벤트 추가 (꽉 차면 오래된 이벤트 버림)"""
    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """작업 정보"""
    job_id: str
    url: str
    target_count: int
    max_rank: int = 50
    min_rank: int = 1
    name_keyword_ratio: float = 0.30
    status: JobStatus = JobStatus.QUEUED
    place_name: str = ""
    results: List[dict] = field(default_factory=list)
    error_message: str = ""
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    # 런타임 참조 (직렬화 제외)
    _worker: Optional[object] = field(default=None, repr=False)
    _task: Optional[asyncio.Task] = field(default=None, repr=False)

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "url": self.url,
            "target_count": self.target_count,
            "max_rank": self.max_rank,
            "min_rank": self.min_rank,
            "status": self.status.value,
            "place_name": self.place_name,
            "result_count": len(self.results),
            "error_message": self.error_message,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class Session:
    """사용자 세션"""
    session_id: str
    username: str
    proxy_slot: int
    is_admin: bool = False
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    jobs: Dict[str, Job] = field(default_factory=dict)
    event_queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=1000))

    def touch(self):
        """활동 시간 갱신"""
        self.last_active = time.time()


class SessionManager:
    """세션 + 대기열 + 로그인 관리"""

    MAX_SESSIONS = 5
    SESSION_TIMEOUT = 3600  # 1시간
    JOBS_DIR = os.path.join("data", "jobs")

    def __init__(self, proxy_pool: ProxyPool):
        self._proxy_pool = proxy_pool
        self._sessions: Dict[str, Session] = {}  # session_id -> Session
        self._username_to_session: Dict[str, str] = {}  # username -> session_id
        self._used_slots: set = set()
        self._lock = asyncio.Lock()

    async def login(self, username: str, password: str) -> Optional[Session]:
        """로그인 → 세션 생성

        Returns:
            Session if success, None if auth failed
        """
        # 인증 체크: settings.json users + data/users.json users
        all_users = self._proxy_pool.users + self._load_extra_users()
        authenticated = False
        is_admin = False
        for user in all_users:
            if user.get("username") == username and user.get("password") == password:
                authenticated = True
                is_admin = user.get("is_admin", False)
                break

        if not authenticated:
            return None

        async with self._lock:
            # 이미 로그인된 경우 기존 세션 반환
            if username in self._username_to_session:
                session_id = self._username_to_session[username]
                if session_id in self._sessions:
                    session = self._sessions[session_id]
                    session.touch()
                    return session

            # 세션 수 제한
            if len(self._sessions) >= self.MAX_SESSIONS:
                # 가장 오래된 세션 제거 시도
                oldest = self._find_oldest_idle_session()
                if oldest:
                    await self._destroy_session_internal(oldest)
                else:
                    return None  # 모든 세션이 활성 상태

            # 프록시 슬롯 할당
            slot = self._proxy_pool.get_available_slot(self._used_slots)
            if slot is None:
                # 슬롯 없으면 첫 번째 사용 가능 슬롯 재사용
                slot = 1

            # 세션 생성
            session_id = secrets.token_urlsafe(32)
            session = Session(
                session_id=session_id,
                username=username,
                proxy_slot=slot,
                is_admin=is_admin,
            )

            # 디스크에서 기존 작업 로드
            saved_jobs = self._load_jobs(username)
            for job in saved_jobs:
                session.jobs[job.job_id] = job

            self._sessions[session_id] = session
            self._username_to_session[username] = session_id
            self._used_slots.add(slot)

            print(f"[SessionManager] Login: {username} → session={session_id[:8]}..., slot={slot}, admin={is_admin}, loaded_jobs={len(saved_jobs)}")
            return session

    async def get_session(self, session_id: str) -> Optional[Session]:
        """세션 조회"""
        session = self._sessions.get(session_id)
        if session:
            session.touch()
        return session

    async def add_job(self, session_id: str, url: str, target_count: int,
                      max_rank: int = 50, min_rank: int = 1,
                      name_keyword_ratio: float = 0.30) -> Optional[Job]:
        """작업 추가"""
        session = self._sessions.get(session_id)
        if not session:
            return None

        job_id = secrets.token_urlsafe(16)
        job = Job(
            job_id=job_id,
            url=url,
            target_count=target_count,
            max_rank=max_rank,
            min_rank=min_rank,
            name_keyword_ratio=name_keyword_ratio,
        )
        session.jobs[job_id] = job
        session.touch()

        # 디스크에 저장
        self._save_job(session.username, job)

        # 세션 이벤트 큐에 작업 추가 알림
        _safe_put(session.event_queue, {
            "type": "job_added",
            "job_id": job_id,
            "data": job.to_dict(),
            "timestamp": time.time(),
        })

        print(f"[SessionManager] Job added: {job_id[:8]}... → session={session_id[:8]}...")
        return job

    async def cancel_job(self, session_id: str, job_id: str) -> bool:
        """작업 취소 (실행 중이면 worker.stop() + 부분 결과 수집)"""
        session = self._sessions.get(session_id)
        if not session:
            return False

        job = session.jobs.get(job_id)
        if not job:
            return False

        if job.status not in (JobStatus.QUEUED, JobStatus.RUNNING):
            return False

        # 실행 중이면 worker 중단 → 부분 결과 수집
        if job.status == JobStatus.RUNNING and job._worker:
            job._worker.stop()
            # 부분 결과 수집
            try:
                results = []
                for r in job._worker.all_results:
                    results.append({
                        "keyword": r.keyword,
                        "rank": r.rank,
                        "keyword_type": "PLT" if (getattr(r, 'source', None) == "name" and r.rank == 1 and (getattr(r, 'total_count', None) is None or getattr(r, 'total_count', None) == 1)) else "PLL",
                        "status": r.status,
                    })
                job.results = results
            except Exception:
                pass

        job.status = JobStatus.CANCELLED
        job.completed_at = time.time()

        # 디스크에 저장
        self._save_job(session.username, job)

        _safe_put(session.event_queue, {
            "type": "job_cancelled",
            "job_id": job_id,
            "data": job.to_dict(),
            "timestamp": time.time(),
        })
        return True

    async def delete_job(self, session_id: str, job_id: str) -> bool:
        """작업 삭제 (실행 중이면 먼저 취소)"""
        session = self._sessions.get(session_id)
        if not session:
            return False

        job = session.jobs.get(job_id)
        if not job:
            return False

        # 실행 중이면 먼저 중단
        if job.status == JobStatus.RUNNING:
            if job._worker:
                job._worker.stop()
            if job._task and not job._task.done():
                job._task.cancel()

        # 작업 제거
        del session.jobs[job_id]

        # 디스크에서 삭제
        self._delete_job_file(session.username, job_id)

        _safe_put(session.event_queue, {
            "type": "job_deleted",
            "job_id": job_id,
            "timestamp": time.time(),
        })
        return True

    async def get_jobs(self, session_id: str) -> List[dict]:
        """세션의 모든 작업 목록"""
        session = self._sessions.get(session_id)
        if not session:
            return []
        return [job.to_dict() for job in session.jobs.values()]

    async def get_job_results(self, session_id: str, job_id: str) -> Optional[List[dict]]:
        """작업 결과 반환"""
        session = self._sessions.get(session_id)
        if not session:
            return None

        job = session.jobs.get(job_id)
        if not job:
            return None

        return job.results

    async def destroy_session(self, session_id: str):
        """세션 파괴"""
        async with self._lock:
            await self._destroy_session_internal(session_id)

    async def _destroy_session_internal(self, session_id: str):
        """세션 파괴 (내부, 락 없음)"""
        session = self._sessions.get(session_id)
        if not session:
            return

        # 실행 중인 각 작업의 워커/태스크 취소
        for job in session.jobs.values():
            if job._worker:
                job._worker.stop()
            if job._task and not job._task.done():
                job._task.cancel()

        # 슬롯 해제
        self._used_slots.discard(session.proxy_slot)
        self._username_to_session.pop(session.username, None)
        del self._sessions[session_id]

        print(f"[SessionManager] Session destroyed: {session_id[:8]}... (user={session.username})")

    def _find_oldest_idle_session(self) -> Optional[str]:
        """가장 오래된 비활성 세션 ID (실행 중인 작업이 없는)"""
        candidates = []
        for sid, session in self._sessions.items():
            # 실행 중인 작업이 있으면 건드리지 않음
            has_running = any(
                j.status == JobStatus.RUNNING for j in session.jobs.values()
            )
            if not has_running:
                candidates.append((sid, session.last_active))

        if not candidates:
            return None

        # 가장 오래된 세션
        candidates.sort(key=lambda x: x[1])
        return candidates[0][0]

    async def cleanup_expired(self):
        """만료된 세션 정리"""
        now = time.time()
        expired = []

        for sid, session in self._sessions.items():
            if now - session.last_active > self.SESSION_TIMEOUT:
                # 실행 중인 작업이 없으면 만료
                has_running = any(
                    j.status == JobStatus.RUNNING for j in session.jobs.values()
                )
                if not has_running:
                    expired.append(sid)

        for sid in expired:
            async with self._lock:
                await self._destroy_session_internal(sid)

    def get_active_session_count(self) -> int:
        """활성 세션 수"""
        return len(self._sessions)

    def get_session_info(self) -> List[dict]:
        """모든 세션 정보 (디버그용)"""
        result = []
        for sid, session in self._sessions.items():
            result.append({
                "session_id": sid[:8] + "...",
                "username": session.username,
                "proxy_slot": session.proxy_slot,
                "job_count": len(session.jobs),
                "last_active": session.last_active,
            })
        return result

    # ==================== Job Persistence ====================

    def _get_user_jobs_dir(self, username: str) -> str:
        """유저별 작업 디렉토리 경로"""
        return os.path.join(self.JOBS_DIR, username)

    def _save_job(self, username: str, job: Job):
        """작업을 디스크에 저장"""
        user_dir = self._get_user_jobs_dir(username)
        os.makedirs(user_dir, exist_ok=True)
        filepath = os.path.join(user_dir, f"{job.job_id}.json")
        data = {
            "job_id": job.job_id,
            "url": job.url,
            "target_count": job.target_count,
            "max_rank": job.max_rank,
            "min_rank": job.min_rank,
            "name_keyword_ratio": job.name_keyword_ratio,
            "status": job.status.value,
            "place_name": job.place_name,
            "results": job.results,
            "error_message": job.error_message,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
        }
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            print(f"[SessionManager] Failed to save job {job.job_id[:8]}: {e}")

    def save_job_by_session(self, session_id: str, job_id: str):
        """세션/작업 ID로 디스크에 저장 (외부 호출용)"""
        session = self._sessions.get(session_id)
        if not session:
            return
        job = session.jobs.get(job_id)
        if not job:
            return
        self._save_job(session.username, job)

    def _load_jobs(self, username: str) -> List[Job]:
        """디스크에서 유저의 모든 작업 로드"""
        user_dir = self._get_user_jobs_dir(username)
        if not os.path.exists(user_dir):
            return []

        jobs = []
        for filename in os.listdir(user_dir):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(user_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                job = Job(
                    job_id=data["job_id"],
                    url=data["url"],
                    target_count=data.get("target_count", 100),
                    max_rank=data.get("max_rank", 50),
                    min_rank=data.get("min_rank", 1),
                    name_keyword_ratio=data.get("name_keyword_ratio", 0.30),
                    status=JobStatus(data.get("status", "completed")),
                    place_name=data.get("place_name", ""),
                    results=data.get("results", []),
                    error_message=data.get("error_message", ""),
                    created_at=data.get("created_at", 0),
                    started_at=data.get("started_at"),
                    completed_at=data.get("completed_at"),
                )
                # 서버 재시작으로 중단된 실행 중 작업 → 실패 처리
                if job.status in (JobStatus.RUNNING, JobStatus.QUEUED):
                    job.status = JobStatus.FAILED
                    job.error_message = "서버 재시작으로 중단됨"
                    job.completed_at = time.time()
                    # 상태 변경 반영
                    with open(filepath, "w", encoding="utf-8") as f2:
                        data["status"] = job.status.value
                        data["error_message"] = job.error_message
                        data["completed_at"] = job.completed_at
                        json.dump(data, f2, ensure_ascii=False)

                jobs.append(job)
            except Exception as e:
                print(f"[SessionManager] Failed to load job {filename}: {e}")

        # 생성 시간 역순 정렬
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs

    def _delete_job_file(self, username: str, job_id: str):
        """디스크에서 작업 파일 삭제"""
        filepath = os.path.join(self._get_user_jobs_dir(username), f"{job_id}.json")
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                print(f"[SessionManager] Job file deleted: {job_id[:8]}")
        except Exception as e:
            print(f"[SessionManager] Failed to delete job file {job_id[:8]}: {e}")

    # ==================== Extra User Management ====================

    EXTRA_USERS_PATH = os.path.join("data", "users.json")

    def _load_extra_users(self) -> List[dict]:
        """data/users.json에서 추가 유저 리스트 로드"""
        if not os.path.exists(self.EXTRA_USERS_PATH):
            return []
        try:
            with open(self.EXTRA_USERS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def _save_extra_users(self, users: List[dict]):
        """data/users.json에 유저 리스트 저장"""
        os.makedirs(os.path.dirname(self.EXTRA_USERS_PATH), exist_ok=True)
        with open(self.EXTRA_USERS_PATH, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)

    def create_user(self, username: str, password: str) -> bool:
        """새 유저 추가 (non-admin). 이미 존재하면 False"""
        # settings.json users 체크
        for user in self._proxy_pool.users:
            if user.get("username") == username:
                return False

        # data/users.json users 체크
        extra_users = self._load_extra_users()
        for user in extra_users:
            if user.get("username") == username:
                return False

        extra_users.append({"username": username, "password": password})
        self._save_extra_users(extra_users)
        print(f"[SessionManager] User created: {username}")
        return True

    def delete_user(self, username: str) -> bool:
        """유저 삭제. admin 유저 또는 settings.json 유저는 삭제 불가"""
        # settings.json users는 삭제 불가
        for user in self._proxy_pool.users:
            if user.get("username") == username:
                return False

        # data/users.json에서 삭제
        extra_users = self._load_extra_users()
        new_users = [u for u in extra_users if u.get("username") != username]
        if len(new_users) == len(extra_users):
            return False  # 해당 유저 없음

        self._save_extra_users(new_users)
        print(f"[SessionManager] User deleted: {username}")
        return True

    def list_users(self) -> List[dict]:
        """전체 유저 목록 반환 (비밀번호 제외)"""
        result = []
        for user in self._proxy_pool.users:
            result.append({
                "username": user.get("username", ""),
                "is_admin": user.get("is_admin", False),
                "source": "settings",
            })
        for user in self._load_extra_users():
            result.append({
                "username": user.get("username", ""),
                "is_admin": False,
                "source": "extra",
            })
        return result
