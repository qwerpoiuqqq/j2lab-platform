"""Extraction service - orchestrates the keyword extraction pipeline.

Pipeline:
1. Receive job from api-server
2. Scrape place data (Playwright)
3. Generate keyword pool (rule-based combinations)
4. Rank check (GraphQL API)
5. Save results to DB (places, keywords, keyword_rank_history)
6. Send callback to api-server

Ported from: reference/keyword-extract/src/smart_worker.py
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.extraction_job import ExtractionJob, ExtractionJobStatus
from app.models.keyword import Keyword
from app.models.keyword_rank_history import KeywordRankHistory
from app.models.place import Place
from app.services.keyword_parser import (
    detect_business_type,
    generate_keyword_pool,
    generate_region_keywords,
)
from app.services.place_scraper import PlaceData, PlaceScraper
from app.services.rank_checker import RankCheckResult, RankChecker
from app.utils.url_parser import parse_place_url

logger = logging.getLogger(__name__)


class ExtractionService:
    """Orchestrates keyword extraction pipeline."""

    def __init__(self):
        self._running_jobs: Dict[int, bool] = {}  # job_id -> is_running
        self._partial_rank_results: Dict[int, List[RankCheckResult]] = {}  # job_id -> partial results

    async def execute_job(self, job_id: int, timeout_seconds: int = 600) -> None:
        """Execute a single extraction job end-to-end.

        Args:
            job_id: ExtractionJob.id to execute.
            timeout_seconds: Max execution time in seconds (default 600 = 10 min).
        """
        self._running_jobs[job_id] = True
        self._partial_rank_results[job_id] = []
        db_place_id = 0  # Track place_id for failure callback

        try:
            # Load job data and capture all needed attributes before closing session
            async with async_session_factory() as db:
                job = await db.get(ExtractionJob, job_id)
                if not job:
                    logger.error("Job %d not found", job_id)
                    return

                if job.status != ExtractionJobStatus.QUEUED.value:
                    logger.warning(
                        "Job %d is not queued (status: %s), skipping",
                        job_id,
                        job.status,
                    )
                    return

                # Capture needed attributes before session closes
                job_naver_url = job.naver_url
                job_target_count = job.target_count
                job_max_rank = job.max_rank
                job_name_keyword_ratio = job.name_keyword_ratio

                # Mark as running
                job.status = ExtractionJobStatus.RUNNING.value
                job.started_at = datetime.now(timezone.utc)
                job.worker_id = f"kw-worker-{settings.WORKER_PORT}"
                await db.commit()

            start_time = time.time()

            # Notify api-server that extraction has started so pipeline stage
            # can move from extraction_queued -> extraction_running immediately.
            await self._send_callback(
                job_id,
                "running",
                0,
                db_place_id,
            )

            # Phase 0: Parse URL
            parsed = parse_place_url(job_naver_url)
            if not parsed.is_valid:
                await self._fail_job(
                    job_id, f"Invalid URL: {parsed.error_message}"
                )
                return

            place_id_str = parsed.mid
            logger.info(
                "Job %d: Starting extraction for place %s", job_id, place_id_str
            )

            # Phase 1: Scrape place data
            if not self._is_running(job_id):
                await self._cancel_job(job_id)
                return

            place_data = await self._scrape_place(job_naver_url)
            if not place_data:
                await self._fail_job(
                    job_id, "Failed to scrape place data"
                )
                return

            place_data.id = place_id_str
            logger.info(
                "Job %d: Scraped place '%s' (%s)",
                job_id,
                place_data.name,
                place_data.category,
            )

            # Save place to DB
            db_place_id = int(place_id_str)
            await self._save_place(db_place_id, place_data)

            # Update job with place info
            async with async_session_factory() as db:
                job = await db.get(ExtractionJob, job_id)
                if job:
                    job.place_id = db_place_id
                    job.place_name = place_data.name
                    await db.commit()

            # Phase 2: Generate keyword pool
            if not self._is_running(job_id):
                await self._cancel_job(job_id)
                return

            keyword_pool = generate_keyword_pool(
                place_data,
                target_count=job_target_count,
                name_keyword_ratio=job_name_keyword_ratio,
            )
            logger.info(
                "Job %d: Generated %d keyword candidates",
                job_id,
                len(keyword_pool),
            )

            # Phase 3: Rank check with timeout (retry until conditions match)
            if not self._is_running(job_id):
                await self._cancel_job(job_id)
                return

            all_keywords = [item["keyword"] for item in keyword_pool]
            deadline = start_time + timeout_seconds
            timed_out = False
            attempt = 0
            rank_results: List[RankCheckResult] = []
            best_rank_results: List[RankCheckResult] = []  # Keep best across attempts
            final_keywords = all_keywords
            selected_results: List[RankCheckResult] = []
            condition_met = False
            last_selection_error = ""

            while self._is_running(job_id):
                remaining = deadline - time.time()
                if remaining <= 0:
                    timed_out = True
                    break

                attempt += 1
                self._partial_rank_results[job_id] = []
                logger.info(
                    "Job %d: Attempt %d rank check (remaining %.1fs)",
                    job_id,
                    attempt,
                    remaining,
                )

                try:
                    attempt_results, attempt_final_keywords = await asyncio.wait_for(
                        self._check_ranks(
                            keywords=all_keywords,
                            place_id=place_id_str,
                            max_rank=job_max_rank,
                            target_count=job_target_count,
                            job_id=job_id,
                        ),
                        timeout=remaining,
                    )
                except asyncio.TimeoutError:
                    timed_out = True
                    # Merge partial results from this attempt with best previous results
                    partial = list(self._partial_rank_results.get(job_id, []))
                    partial_ranked = len([r for r in partial if r.rank is not None])
                    best_ranked = len([r for r in best_rank_results if r.rank is not None])
                    rank_results = partial if partial_ranked > best_ranked else best_rank_results
                    final_keywords = all_keywords
                    logger.warning(
                        "Job %d: Timeout after %ds, using best of %d (partial) vs %d (previous best) rank results",
                        job_id,
                        timeout_seconds,
                        partial_ranked,
                        best_ranked,
                    )
                    break

                rank_results = attempt_results
                final_keywords = attempt_final_keywords
                # Track best complete results across attempts
                cur_ranked = len([r for r in rank_results if r.rank is not None])
                best_ranked = len([r for r in best_rank_results if r.rank is not None])
                if cur_ranked > best_ranked:
                    best_rank_results = list(rank_results)

                ranked_count = len([r for r in rank_results if r.rank is not None])
                logger.info(
                    "Job %d: Attempt %d checked. %d ranked keywords found",
                    job_id,
                    attempt,
                    ranked_count,
                )

                try:
                    selected_results = self._select_ranked_keywords_by_ratio(
                        rank_results=rank_results,
                        target_count=job_target_count,
                        name_keyword_ratio=job_name_keyword_ratio,
                        max_rank=job_max_rank,
                    )
                    condition_met = True
                    break
                except ValueError as e:
                    last_selection_error = str(e)
                    logger.info(
                        "Job %d: Attempt %d did not meet conditions: %s",
                        job_id,
                        attempt,
                        last_selection_error,
                    )

            if not self._is_running(job_id):
                await self._cancel_job(job_id)
                return

            if not condition_met:
                if timed_out:
                    selected_results = self._select_partial_ranked_keywords(
                        rank_results=rank_results,
                        target_count=job_target_count,
                        max_rank=job_max_rank,
                    )
                else:
                    error_message = (
                        last_selection_error
                        or "키워드 조건 충족 전에 작업이 중단되었습니다."
                    )
                    await self._fail_job(job_id, error_message)
                    await self._send_callback(
                        job_id,
                        "failed",
                        0,
                        db_place_id,
                        place_name=place_data.name,
                        error_message=error_message,
                    )
                    logger.warning("Job %d failed validation: %s", job_id, error_message)
                    return

            # Phase 4: Save results
            if not self._is_running(job_id):
                await self._cancel_job(job_id)
                return

            saved_count = await self._save_keywords(
                db_place_id, selected_results, final_keywords, job_target_count
            )

            results_json = [r.to_dict() for r in selected_results]
            if timed_out:
                timeout_message = (
                    f"시간 초과({timeout_seconds}초): "
                    f"부분 키워드 {saved_count}개 반영"
                )
                if saved_count > 0:
                    # Partial results available: treat as completed so pipeline continues
                    await self._complete_job(job_id, results_json, saved_count)
                    await self._send_callback(
                        job_id,
                        "completed",
                        saved_count,
                        db_place_id,
                        place_name=place_data.name,
                    )
                    logger.info(
                        "Job %d: Timed out but completed with partial results (%d)",
                        job_id,
                        saved_count,
                    )
                else:
                    # No results at all: cancel
                    await self._cancel_job_with_results(
                        job_id,
                        results_json,
                        saved_count,
                        timeout_message,
                    )
                    await self._send_callback(
                        job_id,
                        "cancelled",
                        saved_count,
                        db_place_id,
                        place_name=place_data.name,
                        error_message=timeout_message,
                    )
                    logger.warning(
                        "Job %d: Timed out with no results",
                        job_id,
                    )
            else:
                await self._complete_job(job_id, results_json, saved_count)

                # Send callback to api-server
                await self._send_callback(
                    job_id,
                    "completed",
                    saved_count,
                    db_place_id,
                    place_name=place_data.name,
                )

                logger.info(
                    "Job %d: Completed. %d keywords saved", job_id, saved_count
                )

        except asyncio.CancelledError:
            await self._cancel_job(job_id)
        except Exception as e:
            logger.exception("Job %d failed: %s", job_id, e)
            await self._fail_job(job_id, str(e))
            await self._send_callback(
                job_id, "failed", 0, db_place_id, error_message=str(e)
            )
        finally:
            self._running_jobs.pop(job_id, None)
            self._partial_rank_results.pop(job_id, None)

    def cancel_job(self, job_id: int) -> None:
        """Request cancellation of a running job."""
        self._running_jobs[job_id] = False

    def _is_running(self, job_id: int) -> bool:
        """Check if a job should continue running."""
        return self._running_jobs.get(job_id, False)

    @staticmethod
    def _select_ranked_keywords_by_ratio(
        rank_results: List[RankCheckResult],
        target_count: int,
        name_keyword_ratio: float,
        max_rank: int,
    ) -> List[RankCheckResult]:
        """Select exactly target_count keywords by rank and PLT ratio."""
        qualified = [
            r
            for r in rank_results
            if r.rank is not None and isinstance(r.rank, int) and r.rank <= max_rank
        ]

        if len(qualified) < target_count:
            raise ValueError(
                f"조건 충족 키워드가 부족합니다. (필요: {target_count}, 확보: {len(qualified)}, 조건: rank<={max_rank})"
            )

        plt_target = int(round(target_count * name_keyword_ratio))
        plt_target = max(0, min(plt_target, target_count))
        pll_target = target_count - plt_target

        plt_candidates = [r for r in qualified if r.keyword_type == "plt"]
        pll_candidates = [r for r in qualified if r.keyword_type != "plt"]

        if len(plt_candidates) < plt_target:
            raise ValueError(
                f"PLT 키워드 비중을 맞출 수 없습니다. (필요: {plt_target}, 확보: {len(plt_candidates)})"
            )
        if len(pll_candidates) < pll_target:
            raise ValueError(
                f"PLL 키워드 수가 부족합니다. (필요: {pll_target}, 확보: {len(pll_candidates)})"
            )

        plt_candidates.sort(key=lambda r: (r.rank, r.result_count, r.keyword))
        pll_candidates.sort(key=lambda r: (r.rank, r.result_count, r.keyword))

        selected = plt_candidates[:plt_target] + pll_candidates[:pll_target]
        selected.sort(key=lambda r: (r.rank, r.keyword_type, r.keyword))
        return selected

    @staticmethod
    def _select_partial_ranked_keywords(
        rank_results: List[RankCheckResult],
        target_count: int,
        max_rank: int,
    ) -> List[RankCheckResult]:
        """Select up to target_count keywords for partial save.

        Includes all keywords that have rank data (regardless of max_rank),
        prioritizing those within max_rank first, then the rest by rank.
        """
        with_rank = [
            r for r in rank_results
            if r.rank is not None and isinstance(r.rank, int)
        ]
        # Sort: within max_rank first, then by rank ascending
        with_rank.sort(key=lambda r: (0 if r.rank <= max_rank else 1, r.rank, r.keyword))
        return with_rank[:target_count]

    # ==================== Phase 1: Scraping ====================

    async def _scrape_place(self, url: str) -> Optional[PlaceData]:
        """Scrape place data using Playwright."""
        try:
            async with PlaceScraper(
                headless=settings.PLAYWRIGHT_HEADLESS
            ) as scraper:
                return await scraper.get_place_data_by_url(url)
        except Exception as e:
            logger.error("Scraping failed: %s", e)
            return None

    # ==================== Phase 3: Rank Checking ====================

    async def _check_ranks(
        self,
        keywords: List[str],
        place_id: str,
        max_rank: int,
        target_count: int,
        job_id: Optional[int] = None,
    ) -> tuple:
        """Check ranks for keywords and generate final list.

        Args:
            job_id: If provided, intermediate results are accumulated in
                    _partial_rank_results[job_id] so they survive a timeout.

        Returns:
            Tuple of (rank_results, final_keywords_list)
        """
        rank_results: List[RankCheckResult] = []

        def _on_result(result: RankCheckResult) -> None:
            """Callback to accumulate partial results for timeout recovery."""
            if job_id is not None and job_id in self._partial_rank_results:
                self._partial_rank_results[job_id].append(result)

        try:
            async with RankChecker(
                default_max_rank=max_rank,
            ) as checker:
                # Check map type first
                map_type = ""
                if keywords:
                    map_type = await checker.check_map_type(keywords[0])

                # Batch rank check with progress callback
                results, place_info = await checker.batch_check_ranks(
                    keywords=keywords,
                    place_id=place_id,
                    max_rank=max_rank,
                    max_concurrent=10,
                    map_type=map_type,
                    on_result=_on_result,
                )
                rank_results = results

                # Generate booking keywords if applicable
                final_kws, _, _ = checker.generate_booking_keywords(
                    keywords,
                    place_info=place_info,
                    rank_results=rank_results,
                    map_type=map_type,
                )

        except ImportError:
            logger.warning(
                "httpx not available, skipping rank check. "
                "All keywords will be saved without rank data."
            )
            final_kws = keywords
        except Exception as e:
            logger.error("Rank check failed: %s", e)
            final_kws = keywords

        return rank_results, final_kws

    # ==================== Phase 4: DB Operations ====================

    async def _save_place(self, place_id: int, place_data: PlaceData) -> None:
        """Save or update place data in the database."""
        async with async_session_factory() as db:
            existing = await db.get(Place, place_id)

            if existing:
                # Update existing place
                existing.name = place_data.name
                existing.place_type = (
                    detect_business_type(place_data.category) or "place"
                )
                existing.category = place_data.category
                existing.road_address = place_data.road_address
                existing.jibun_address = place_data.jibun_address
                existing.city = place_data.region.city
                existing.si = place_data.region.si
                existing.gu = place_data.region.gu
                existing.dong = place_data.region.dong
                existing.major_area = place_data.region.major_area
                existing.stations = place_data.region.stations
                existing.phone = place_data.phone
                existing.naver_url = place_data.url
                existing.keywords = place_data.keywords
                existing.conveniences = place_data.conveniences
                existing.micro_reviews = place_data.micro_reviews
                existing.review_menu_keywords = [
                    {"label": k.label, "count": k.count}
                    for k in place_data.review_menu_keywords
                ]
                existing.review_theme_keywords = [
                    {"label": k.label, "count": k.count}
                    for k in place_data.review_theme_keywords
                ]
                existing.voted_keywords = [
                    {"label": k.label, "count": k.count}
                    for k in place_data.voted_keywords
                ]
                existing.menus = place_data.menus
                existing.medical_subjects = place_data.medical_subjects
                existing.introduction = place_data.introduction
                existing.has_booking = place_data.has_booking
                existing.booking_type = place_data.booking_type
                existing.discovered_regions = list(place_data.discovered_regions)
                existing.last_scraped_at = datetime.now(timezone.utc)
            else:
                # Create new place
                new_place = Place(
                    id=place_id,
                    name=place_data.name,
                    place_type=detect_business_type(place_data.category) or "place",
                    category=place_data.category,
                    road_address=place_data.road_address,
                    jibun_address=place_data.jibun_address,
                    city=place_data.region.city,
                    si=place_data.region.si,
                    gu=place_data.region.gu,
                    dong=place_data.region.dong,
                    major_area=place_data.region.major_area,
                    stations=place_data.region.stations,
                    phone=place_data.phone,
                    naver_url=place_data.url,
                    keywords=place_data.keywords,
                    conveniences=place_data.conveniences,
                    micro_reviews=place_data.micro_reviews,
                    review_menu_keywords=[
                        {"label": k.label, "count": k.count}
                        for k in place_data.review_menu_keywords
                    ],
                    review_theme_keywords=[
                        {"label": k.label, "count": k.count}
                        for k in place_data.review_theme_keywords
                    ],
                    voted_keywords=[
                        {"label": k.label, "count": k.count}
                        for k in place_data.voted_keywords
                    ],
                    menus=place_data.menus,
                    medical_subjects=place_data.medical_subjects,
                    introduction=place_data.introduction,
                    has_booking=place_data.has_booking,
                    booking_type=place_data.booking_type,
                    discovered_regions=list(place_data.discovered_regions),
                    last_scraped_at=datetime.now(timezone.utc),
                )
                db.add(new_place)

            await db.commit()

    async def _save_keywords(
        self,
        place_id: int,
        rank_results: List[RankCheckResult],
        final_keywords: List[str],
        target_count: int,
    ) -> int:
        """Save extracted keywords to the database.

        Uses INSERT ON CONFLICT (upsert) to handle duplicate keywords.
        Returns the number of keywords saved.
        """
        now = datetime.now(timezone.utc)
        today = date.today()

        # Build keyword data from selected ranked keywords only
        keyword_data: Dict[str, Dict] = {}

        # Add ranked results first
        for r in rank_results:
            if r.rank is not None:
                keyword_data[r.keyword] = {
                    "keyword": r.keyword,
                    "keyword_type": r.keyword_type,
                    "current_rank": r.rank,
                    "current_map_type": r.map_type,
                    "last_checked_at": now,
                }

        if not keyword_data:
            return 0

        saved_count = 0
        async with async_session_factory() as db:
            for kw, data in keyword_data.items():
                # Check if keyword already exists for this place
                stmt = select(Keyword).where(
                    Keyword.place_id == place_id,
                    Keyword.keyword == kw,
                )
                result = await db.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    # Update existing keyword
                    if data["current_rank"] is not None:
                        existing.current_rank = data["current_rank"]
                        existing.current_map_type = data["current_map_type"]
                        existing.keyword_type = data["keyword_type"]
                        existing.last_checked_at = data["last_checked_at"]
                    keyword_id = existing.id
                else:
                    # Insert new keyword with savepoint to handle race condition
                    try:
                        async with db.begin_nested():
                            new_kw = Keyword(
                                place_id=place_id,
                                keyword=data["keyword"],
                                keyword_type=data["keyword_type"],
                                current_rank=data["current_rank"],
                                current_map_type=data["current_map_type"],
                                last_checked_at=data["last_checked_at"],
                            )
                            db.add(new_kw)
                            await db.flush()
                            keyword_id = new_kw.id
                    except IntegrityError:
                        # Another process inserted this keyword; fetch and update
                        result = await db.execute(stmt)
                        existing = result.scalar_one_or_none()
                        if existing:
                            existing.current_rank = data["current_rank"]
                            existing.current_map_type = data["current_map_type"]
                            existing.keyword_type = data["keyword_type"]
                            existing.last_checked_at = data["last_checked_at"]
                            keyword_id = existing.id
                        else:
                            continue

                # Add rank history if we have rank data
                if data["current_rank"] is not None:
                    # Check if history entry exists for today
                    hist_stmt = select(KeywordRankHistory).where(
                        KeywordRankHistory.keyword_id == keyword_id,
                        KeywordRankHistory.recorded_date == today,
                    )
                    hist_result = await db.execute(hist_stmt)
                    existing_hist = hist_result.scalar_one_or_none()

                    if existing_hist:
                        existing_hist.rank_position = data["current_rank"]
                        existing_hist.map_type = data["current_map_type"]
                    else:
                        history = KeywordRankHistory(
                            keyword_id=keyword_id,
                            rank_position=data["current_rank"],
                            map_type=data["current_map_type"],
                            recorded_date=today,
                        )
                        db.add(history)

                saved_count += 1

            await db.commit()

        return saved_count

    # ==================== Job Status Updates ====================

    async def _complete_job(
        self, job_id: int, results_json: List[Dict], result_count: int
    ) -> None:
        """Mark job as completed."""
        async with async_session_factory() as db:
            job = await db.get(ExtractionJob, job_id)
            if job:
                job.status = ExtractionJobStatus.COMPLETED.value
                job.results = results_json
                job.result_count = result_count
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()

    async def _fail_job(self, job_id: int, error_message: str) -> None:
        """Mark job as failed."""
        async with async_session_factory() as db:
            job = await db.get(ExtractionJob, job_id)
            if job:
                job.status = ExtractionJobStatus.FAILED.value
                job.error_message = error_message
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()

    async def _cancel_job(self, job_id: int) -> None:
        """Mark job as cancelled."""
        async with async_session_factory() as db:
            job = await db.get(ExtractionJob, job_id)
            if job:
                job.status = ExtractionJobStatus.CANCELLED.value
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()

    async def _cancel_job_with_results(
        self,
        job_id: int,
        results_json: List[Dict],
        result_count: int,
        error_message: str,
    ) -> None:
        """Mark job as cancelled while persisting partial results."""
        async with async_session_factory() as db:
            job = await db.get(ExtractionJob, job_id)
            if job:
                job.status = ExtractionJobStatus.CANCELLED.value
                job.results = results_json
                job.result_count = result_count
                job.error_message = error_message
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()

    # ==================== Callback ====================

    async def _send_callback(
        self,
        job_id: int,
        status: str,
        result_count: int,
        place_id: int,
        place_name: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Send completion callback to api-server.

        Payload matches api-server's ExtractionCallbackRequest schema.
        """
        try:
            import httpx

            callback_url = (
                f"{settings.API_SERVER_URL}/internal/callback/extraction/{job_id}"
            )
            payload: Dict[str, Any] = {
                "status": status,
                "result_count": result_count,
                "place_id": place_id,
            }
            if place_name is not None:
                payload["place_name"] = place_name
            if error_message is not None:
                payload["error_message"] = error_message
            headers = {"X-Internal-Secret": settings.INTERNAL_API_SECRET}
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    callback_url,
                    json=payload,
                    headers=headers,
                )
                if resp.status_code != 200:
                    logger.warning(
                        "Callback to api-server returned %d: %s",
                        resp.status_code,
                        resp.text,
                    )
        except Exception as e:
            logger.warning("Failed to send callback to api-server: %s", e)


# Singleton instance
extraction_service = ExtractionService()
