"""APScheduler 기반 키워드 자동 변경 스케줄러.

매 10분마다 실행되어 각 계정에 로그인 후,
오늘 키워드를 변경하지 않은 캠페인의 키워드를 변경합니다.
"""

import logging
import traceback
from collections import deque
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.database import SessionLocal
from app.models.campaign import Campaign
from app.models.account import Account
from app.utils.encryption import decrypt_password
from app.services.keyword_rotation import rotate_keywords, sync_all_campaign_statuses
from app.services.superap import SuperapController

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")

scheduler = AsyncIOScheduler(timezone=KST)

# ============================================================
# 스케줄러 상태 추적 (진단용)
# ============================================================
MAX_LOG_ENTRIES = 50

scheduler_state: Dict[str, Any] = {
    "last_run": None,
    "last_result": None,
    "last_error": None,
    "run_count": 0,
    "is_running": False,
    "recent_logs": deque(maxlen=MAX_LOG_ENTRIES),
}


def _log(level: str, msg: str) -> None:
    """스케줄러 내부 로그 기록 (logger + state)."""
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{now}] [{level}] {msg}"
    scheduler_state["recent_logs"].append(entry)
    getattr(logger, level.lower(), logger.info)(f"[스케줄러] {msg}")


def get_scheduler_state() -> Dict[str, Any]:
    """현재 스케줄러 상태를 반환."""
    return {
        "is_running": scheduler_state["is_running"],
        "scheduler_active": scheduler.running if scheduler else False,
        "last_run": scheduler_state["last_run"],
        "last_result": scheduler_state["last_result"],
        "last_error": scheduler_state["last_error"],
        "run_count": scheduler_state["run_count"],
        "recent_logs": list(scheduler_state["recent_logs"]),
    }


def _was_rotated_today(campaign: Campaign, today_kst: date) -> bool:
    """오늘(KST) 이미 키워드 변경이 되었는지 확인."""
    if campaign.last_keyword_change is None:
        return False

    last_change = campaign.last_keyword_change
    # DB에 UTC로 저장되므로 naive datetime은 UTC로 간주
    if last_change.tzinfo is None:
        last_change = last_change.replace(tzinfo=timezone.utc)

    last_change_date = last_change.astimezone(KST).date()
    return last_change_date >= today_kst


async def check_and_rotate_keywords() -> Dict[str, Any]:
    """매 10분마다 실행되는 키워드 변경 함수.

    단순 로직:
    1. 각 계정에 로그인
    2. 해당 계정의 캠페인 번호로 수정 페이지 직접 이동
    3. 오늘 키워드 변경을 안 했으면 변경

    Returns:
        실행 결과 dict (진단용)
    """
    scheduler_state["is_running"] = True
    scheduler_state["run_count"] += 1

    result_summary: Dict[str, Any] = {
        "accounts_processed": 0,
        "logins_ok": 0,
        "logins_failed": 0,
        "rotated": 0,
        "rotation_failed": 0,
        "skipped_today": 0,
        "errors": [],
    }

    db = SessionLocal()
    controller = None

    try:
        now_kst = datetime.now(KST)
        today_kst = now_kst.date()
        _log("INFO", f"키워드 체크 시작: {now_kst.strftime('%Y-%m-%d %H:%M:%S')} KST")

        # 활성 계정 조회
        active_accounts = (
            db.query(Account)
            .filter(Account.is_active == True)
            .all()
        )

        if not active_accounts:
            _log("INFO", "활성 계정 없음")
            scheduler_state["last_result"] = result_summary
            return result_summary

        _log("INFO", f"활성 계정 {len(active_accounts)}개 발견")

        # 브라우저 초기화
        controller = SuperapController(headless=True)
        await controller.initialize()
        _log("INFO", "브라우저 초기화 완료")

        for account in active_accounts:
            account_key = str(account.id)

            # 이 계정의 캠페인 조회 (campaign_code 있는 것만)
            account_campaigns = (
                db.query(Campaign)
                .filter(
                    Campaign.account_id == account.id,
                    Campaign.campaign_code.isnot(None),
                )
                .all()
            )

            if not account_campaigns:
                _log("INFO", f"계정 {account.user_id}: 캠페인 없음, 건너뜀")
                continue

            # 오늘 변경 안 한 캠페인만 필터 (만료일 지난 캠페인 제외)
            campaigns_to_rotate = []
            for c in account_campaigns:
                if c.end_date and c.end_date < today_kst:
                    result_summary["skipped_today"] += 1
                    continue
                if _was_rotated_today(c, today_kst):
                    result_summary["skipped_today"] += 1
                    continue
                campaigns_to_rotate.append(c)

            if not campaigns_to_rotate:
                _log(
                    "INFO",
                    f"계정 {account.user_id}: "
                    f"{len(account_campaigns)}개 캠페인 전부 오늘 이미 변경됨, 건너뜀",
                )
                continue

            _log(
                "INFO",
                f"계정 {account.user_id}: "
                f"변경 대상 {len(campaigns_to_rotate)}개 / "
                f"전체 {len(account_campaigns)}개",
            )
            result_summary["accounts_processed"] += 1

            # 로그인
            try:
                password = decrypt_password(account.password_encrypted)
                login_ok = await controller.login(
                    account_key, account.user_id, password
                )
                if not login_ok:
                    msg = f"계정 {account.user_id} 로그인 실패"
                    _log("ERROR", msg)
                    result_summary["logins_failed"] += 1
                    result_summary["errors"].append(msg)
                    continue
                _log("INFO", f"계정 {account.user_id} 로그인 성공")
                result_summary["logins_ok"] += 1
            except Exception as e:
                msg = f"계정 {account.user_id} 로그인 오류: {e}"
                _log("ERROR", msg)
                result_summary["logins_failed"] += 1
                result_summary["errors"].append(msg)
                continue

            # 상태 + 전환수 동기화 (키워드 변경 전에 실행)
            try:
                sync_result = await sync_all_campaign_statuses(
                    db=db,
                    superap_controller=controller,
                    account_id=account.id,
                )
                if sync_result.get("success"):
                    _log("INFO", f"계정 {account.user_id} 상태 동기화: {sync_result.get('synced_count', 0)}개 업데이트")
                else:
                    _log("WARNING", f"계정 {account.user_id} 상태 동기화 실패: {sync_result.get('message', '')}")
            except Exception as e:
                _log("WARNING", f"계정 {account.user_id} 상태 동기화 오류: {e}")

            # 캠페인별 키워드 변경 (캠페인 번호로 수정 페이지 직접 이동)
            for campaign in campaigns_to_rotate:
                try:
                    rot_result = await rotate_keywords(
                        campaign_id=campaign.id,
                        db=db,
                        superap_controller=controller,
                        trigger_type="daily",
                    )
                    if rot_result["success"]:
                        result_summary["rotated"] += 1
                        _log(
                            "INFO",
                            f"캠페인 {campaign.campaign_code} ({campaign.place_name}) "
                            f"키워드 변경 성공: {rot_result['message']}",
                        )
                    else:
                        result_summary["rotation_failed"] += 1
                        msg = (
                            f"캠페인 {campaign.campaign_code} ({campaign.place_name}) "
                            f"키워드 변경 실패: {rot_result['message']}"
                        )
                        _log("WARNING", msg)
                        result_summary["errors"].append(msg)
                except Exception as e:
                    result_summary["rotation_failed"] += 1
                    msg = (
                        f"캠페인 {campaign.campaign_code} ({campaign.place_name}) "
                        f"오류: {e}"
                    )
                    _log("ERROR", msg)
                    result_summary["errors"].append(msg)

            # 계정 컨텍스트 정리
            try:
                await controller.close_context(account_key)
            except Exception:
                pass

        _log("INFO", f"키워드 체크 완료: {result_summary}")
        scheduler_state["last_result"] = result_summary
        scheduler_state["last_error"] = None

    except Exception as e:
        err_msg = f"전체 오류: {e}\n{traceback.format_exc()}"
        _log("ERROR", err_msg)
        scheduler_state["last_error"] = err_msg
        result_summary["errors"].append(str(e))
    finally:
        scheduler_state["is_running"] = False
        scheduler_state["last_run"] = datetime.now(KST).isoformat()
        db.close()
        if controller:
            try:
                await controller.close()
            except Exception:
                pass

    return result_summary


async def retry_stuck_registrations():
    """등록 실패/멈춘 캠페인 재시도.

    5분 이상 queued 상태거나 failed 상태(최대 3회)인 캠페인을 재시도합니다.
    """
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)

        # 신규 등록 실패/멈춘 캠페인 (중간 step에서 멈춘 것도 포함)
        stuck = db.query(Campaign).filter(
            Campaign.status == "pending",
            Campaign.registration_step.isnot(None),
            Campaign.campaign_code.is_(None),
            Campaign.updated_at < cutoff,
        ).all()

        retry_ids = []
        for c in stuck:
            retry_count = (c.registration_message or "").count("[재시도")
            if retry_count >= 3:
                logger.info(f"[자동등록 재시도] 캠페인 {c.id}: 최대 재시도 횟수 초과")
                continue
            prev_step = c.registration_step
            c.registration_step = "queued"
            c.registration_message = f"[재시도 {retry_count + 1}] {prev_step}에서 복구"
            retry_ids.append(c.id)

        # pending_extend 실패 캠페인도 재시도 (status가 failed 또는 pending_extend + 실패 메시지)
        stuck_extends = db.query(Campaign).filter(
            Campaign.status.in_(["failed", "pending_extend"]),
            Campaign.extend_target_id.isnot(None),
            Campaign.registration_message.isnot(None),
            Campaign.updated_at < cutoff,
        ).all()

        extend_retry_ids = []
        for c in stuck_extends:
            # 실패 메시지가 없으면 아직 처리 전이므로 건너뜀
            msg = c.registration_message or ""
            if "실패" not in msg and "오류" not in msg:
                continue
            retry_count = msg.count("[재시도")
            if retry_count >= 3:
                logger.info(f"[연장 재시도] 캠페인 {c.id}: 최대 재시도 횟수 초과")
                continue
            c.status = "pending_extend"
            c.registration_message = f"[재시도 {retry_count + 1}] " + msg
            extend_retry_ids.append(c.id)

        db.commit()

        if retry_ids:
            logger.info(f"[자동등록 재시도] {len(retry_ids)}개 캠페인 재시도")
            from app.services.auto_registration import process_pending_campaigns
            await process_pending_campaigns(retry_ids)

        if extend_retry_ids:
            logger.info(f"[연장 재시도] {len(extend_retry_ids)}개 캠페인 재시도")
            from app.services.auto_registration import process_pending_extensions
            await process_pending_extensions(extend_retry_ids)

    except Exception as e:
        logger.error(f"[자동등록 재시도] 오류: {e}")
    finally:
        db.close()


def start_scheduler():
    """스케줄러 시작."""
    scheduler.add_job(
        check_and_rotate_keywords,
        trigger=IntervalTrigger(minutes=10),
        id="keyword_rotation",
        name="키워드 자동 변경",
        replace_existing=True,
    )
    scheduler.add_job(
        retry_stuck_registrations,
        trigger=IntervalTrigger(minutes=5),
        id="registration_retry",
        name="등록 실패 캠페인 재시도",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("[스케줄러] APScheduler 시작 (키워드 10분, 등록재시도 5분 간격)")


def stop_scheduler():
    """스케줄러 정지."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[스케줄러] APScheduler 정지")
