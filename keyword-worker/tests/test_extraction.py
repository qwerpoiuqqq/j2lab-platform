"""Tests for extraction service (mocked external dependencies)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction_job import ExtractionJob, ExtractionJobStatus
from app.models.keyword import Keyword
from app.models.place import Place
from app.services.extraction_service import ExtractionService
from app.services.place_scraper import PlaceData, RegionInfo, ReviewKeyword
from app.services.rank_checker import RankCheckResult


class TestExtractionServiceSavePlace:
    """Test place saving to database."""

    @pytest.mark.asyncio
    async def test_save_new_place(self, db_session: AsyncSession, sample_place_data):
        """Test saving a new place record."""
        service = ExtractionService()
        place_id = int(sample_place_data.id)

        # Patch the session factory to use our test session
        async def mock_session_factory():
            class MockCtx:
                async def __aenter__(self):
                    return db_session

                async def __aexit__(self, *args):
                    pass

            return MockCtx()

        with patch(
            "app.services.extraction_service.async_session_factory",
            side_effect=lambda: mock_session_factory().__aenter__(),
        ):
            # Manually test the place saving logic
            new_place = Place(
                id=place_id,
                name=sample_place_data.name,
                place_type="restaurant",
                category=sample_place_data.category,
                road_address=sample_place_data.road_address,
                jibun_address=sample_place_data.jibun_address,
                city=sample_place_data.region.city,
                gu=sample_place_data.region.gu,
                dong=sample_place_data.region.dong,
                stations=sample_place_data.region.stations,
                phone=sample_place_data.phone,
                keywords=sample_place_data.keywords,
                menus=sample_place_data.menus,
                has_booking=sample_place_data.has_booking,
                last_scraped_at=datetime.now(timezone.utc),
            )
            db_session.add(new_place)
            await db_session.commit()

            # Verify it was saved
            result = await db_session.get(Place, place_id)
            assert result is not None
            assert result.name == "미도인 강남"
            assert result.category == "이탈리아음식"
            assert result.place_type == "restaurant"
            assert result.gu == "강남구"
            assert "강남역" in result.stations

    @pytest.mark.asyncio
    async def test_save_keywords(self, db_session: AsyncSession):
        """Test saving keywords to database."""
        # First create a place
        place = Place(
            id=99999,
            name="테스트 맛집",
            place_type="restaurant",
            category="한식",
        )
        db_session.add(place)
        await db_session.commit()

        # Add keywords
        keywords_data = [
            Keyword(
                place_id=99999,
                keyword="강남 맛집",
                keyword_type="pll",
                current_rank=3,
                current_map_type="신지도",
                last_checked_at=datetime.now(timezone.utc),
            ),
            Keyword(
                place_id=99999,
                keyword="강남역 한식",
                keyword_type="pll",
                current_rank=7,
                current_map_type="신지도",
                last_checked_at=datetime.now(timezone.utc),
            ),
            Keyword(
                place_id=99999,
                keyword="테스트 맛집",
                keyword_type="plt",
                current_rank=1,
                current_map_type="신지도",
                last_checked_at=datetime.now(timezone.utc),
            ),
        ]
        for kw in keywords_data:
            db_session.add(kw)
        await db_session.commit()

        # Verify keywords
        stmt = select(Keyword).where(Keyword.place_id == 99999)
        result = await db_session.execute(stmt)
        saved_keywords = result.scalars().all()

        assert len(saved_keywords) == 3
        assert saved_keywords[0].keyword == "강남 맛집"
        assert saved_keywords[0].current_rank == 3
        assert saved_keywords[2].keyword_type == "plt"


class TestExtractionServiceJobStatus:
    """Test job status management."""

    @pytest.mark.asyncio
    async def test_create_and_query_job(self, db_session: AsyncSession):
        """Test creating and querying extraction jobs."""
        job = ExtractionJob(
            naver_url="https://m.place.naver.com/restaurant/1234567/home",
            target_count=100,
            max_rank=50,
            min_rank=1,
            name_keyword_ratio=0.30,
            status=ExtractionJobStatus.QUEUED.value,
        )
        db_session.add(job)
        await db_session.commit()

        # Query the job
        result = await db_session.get(ExtractionJob, job.id)
        assert result is not None
        assert result.status == "queued"
        assert result.target_count == 100
        assert result.naver_url == "https://m.place.naver.com/restaurant/1234567/home"

    @pytest.mark.asyncio
    async def test_job_status_transitions(self, db_session: AsyncSession):
        """Test job status transitions."""
        job = ExtractionJob(
            naver_url="https://m.place.naver.com/restaurant/1234567/home",
            status=ExtractionJobStatus.QUEUED.value,
        )
        db_session.add(job)
        await db_session.commit()

        # Transition to running
        job.status = ExtractionJobStatus.RUNNING.value
        job.started_at = datetime.now(timezone.utc)
        await db_session.commit()
        assert job.status == "running"

        # Transition to completed
        job.status = ExtractionJobStatus.COMPLETED.value
        job.completed_at = datetime.now(timezone.utc)
        job.result_count = 150
        job.results = [{"keyword": "test", "rank": 1}]
        await db_session.commit()
        assert job.status == "completed"
        assert job.result_count == 150

    @pytest.mark.asyncio
    async def test_job_failure(self, db_session: AsyncSession):
        """Test job failure status."""
        job = ExtractionJob(
            naver_url="https://m.place.naver.com/restaurant/invalid",
            status=ExtractionJobStatus.QUEUED.value,
        )
        db_session.add(job)
        await db_session.commit()

        job.status = ExtractionJobStatus.FAILED.value
        job.error_message = "Invalid URL format"
        job.completed_at = datetime.now(timezone.utc)
        await db_session.commit()

        result = await db_session.get(ExtractionJob, job.id)
        assert result.status == "failed"
        assert result.error_message == "Invalid URL format"


class TestExtractionServiceCancel:
    """Test job cancellation."""

    def test_cancel_running_job(self):
        """Test cancelling a running job."""
        service = ExtractionService()
        service._running_jobs[42] = True

        service.cancel_job(42)

        assert service._running_jobs[42] is False
        assert service._is_running(42) is False

    def test_cancel_nonexistent_job(self):
        """Cancelling a non-existent job should not raise."""
        service = ExtractionService()
        service.cancel_job(999)  # Should not raise
        assert service._is_running(999) is False


class TestExtractionServicePartialSelection:
    """Test partial keyword selection for timeout cancellation."""

    def test_select_partial_ranked_keywords(self):
        service = ExtractionService()
        rank_results = [
            RankCheckResult(
                keyword="키워드A",
                keyword_type="pll",
                rank=3,
                map_type="신지도",
                result_count=10,
            ),
            RankCheckResult(
                keyword="키워드B",
                keyword_type="plt",
                rank=1,
                map_type="신지도",
                result_count=9,
            ),
            RankCheckResult(
                keyword="키워드C",
                keyword_type="pll",
                rank=35,
                map_type="신지도",
                result_count=20,
            ),
        ]

        selected = service._select_partial_ranked_keywords(
            rank_results=rank_results,
            target_count=2,
            max_rank=20,
        )

        assert len(selected) == 2
        assert selected[0].keyword == "키워드B"
        assert selected[1].keyword == "키워드A"
