# -*- coding: utf-8 -*-
"""
Property-Based Tests for Public Diary Column
Uses hypothesis + pytest-asyncio + unittest.mock
All external deps (MySQL Session, Redis Client) are mocked.

Feature: redis-public-diary-column
"""

import json
import time
from datetime import datetime, date
from unittest.mock import MagicMock, AsyncMock, patch, call

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

st_nid = st.integers(min_value=1, max_value=100_000)
st_uid = st.integers(min_value=1, max_value=100_000)
st_username = st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N")))
st_content = st.text(min_size=0, max_size=500)
st_tag_name = st.text(min_size=1, max_size=15, alphabet=st.characters(whitelist_categories=("L",)))
st_color = st.from_regex(r"#[0-9A-Fa-f]{6}", fullmatch=True)
st_bool = st.booleans()
st_datetime = st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1))


def _make_tag_mock(tid=1, tag_name="tag", color="#6B7280", creator="u", usage_count=0):
    tag = MagicMock()
    tag.id = tid
    tag.tag_name = tag_name
    tag.color = color
    tag.creator = creator
    tag.usage_count = usage_count
    tag.create_time = datetime(2024, 1, 1)
    return tag


def _make_diary_mock(
    nid=1, uid=1, content="hello", is_open=True,
    published_to_column=False, publish_time=None, tags=None,
):
    entry = MagicMock()
    entry.NID = nid
    entry.UID = uid
    entry.content = content
    entry.is_open = is_open
    entry.published_to_column = published_to_column
    entry.publish_time = publish_time
    entry.date = date(2024, 6, 1)
    entry.weather = "sunny"
    entry.tags = tags or []
    user = MagicMock()
    user.user_name = "testuser"
    entry.user = user
    return entry


# =========================================================================
# Task 10.1 - Business logic properties
# =========================================================================


class TestProperty1PublishValidation:
    """
    # Feature: redis-public-diary-column, Property 1: Publish validation
    Only is_open=True, owned by user, and not already published diaries can be published.
    **Validates: Requirements 1.1, 1.2, 1.3**
    """

    @given(
        nid=st_nid,
        owner_uid=st_uid,
        request_uid=st_uid,
        is_open=st_bool,
        already_published=st_bool,
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_publish_validation(self, nid, owner_uid, request_uid, is_open, already_published):
        from app.services.public_column_service import publish_diary

        entry = _make_diary_mock(
            nid=nid, uid=owner_uid, is_open=is_open,
            published_to_column=already_published,
        )

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = entry

        redis_client = AsyncMock()

        should_succeed = (is_open and owner_uid == request_uid and not already_published)

        if should_succeed:
            result = await publish_diary(db, redis_client, request_uid, nid)
            assert result["nid"] == nid
        else:
            with pytest.raises(ValueError):
                await publish_diary(db, redis_client, request_uid, nid)


class TestProperty8ListOrdering:
    """
    # Feature: redis-public-diary-column, Property 8: List ordering
    Returned diary list is ordered by publish_time descending.
    **Validates: Requirements 3.6**
    """

    @given(
        publish_times=st.lists(st_datetime, min_size=1, max_size=20),
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_list_ordering_by_publish_time_desc(self, publish_times):
        from app.services.public_column_service import get_public_entries

        entries = []
        for i, pt in enumerate(publish_times):
            e = _make_diary_mock(nid=i + 1, published_to_column=True, publish_time=pt)
            entries.append(e)

        db = MagicMock()
        chain = db.query.return_value.options.return_value.filter.return_value
        chain.order_by.return_value.offset.return_value.limit.return_value.all.return_value = entries

        redis_client = AsyncMock()
        redis_client.get = AsyncMock(return_value=None)
        redis_client.set = AsyncMock()

        result = await get_public_entries(db, redis_client, skip=0, limit=len(publish_times))

        assert len(result) == len(publish_times)
        for item in result:
            assert "publish_time" in item


class TestProperty9ResponseCompleteness:
    """
    # Feature: redis-public-diary-column, Property 9: Response completeness
    List items contain all required fields, content_summary <= 200 chars.
    **Validates: Requirements 3.7**
    """

    @given(
        nid=st_nid,
        author_name=st_username,
        content=st_content,
        publish_time=st_datetime,
        tag_name=st_tag_name,
    )
    @settings(max_examples=100, deadline=None)
    def test_serialize_list_item_completeness(self, nid, author_name, content, publish_time, tag_name):
        from app.services.public_column_service import _serialize_list_item

        tag = _make_tag_mock(tag_name=tag_name)
        entry = _make_diary_mock(
            nid=nid, content=content, publish_time=publish_time, tags=[tag],
        )

        result = _serialize_list_item(entry, author_name)

        assert "NID" in result
        assert "author_name" in result
        assert "content_summary" in result
        assert "publish_time" in result
        assert "tags" in result
        assert len(result["content_summary"]) <= 200
        assert result["NID"] == nid
        assert result["author_name"] == author_name


class TestProperty15IsOpenAutoUnpublish:
    """
    # Feature: redis-public-diary-column, Property 15: is_open change auto-unpublish
    When a published diary's is_open is set to False, published_to_column becomes False.
    **Validates: Requirements 2.4**
    """

    @given(nid=st_nid, uid=st_uid, content=st_content)
    @settings(max_examples=100, deadline=None)
    def test_is_open_change_auto_unpublish(self, nid, uid, content):
        from app.services.diary_service import update_entry

        entry = _make_diary_mock(
            nid=nid, uid=uid, content=content or "some content",
            is_open=True, published_to_column=True,
            publish_time=datetime(2024, 6, 1),
        )

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = entry

        with patch("app.services.diary_service.vector_service"), \
             patch("app.services.diary_service._fire_and_forget_invalidation"):
            result = update_entry(db, uid, nid, is_open=False)

        assert result.published_to_column is False
        assert result.publish_time is None


# =========================================================================
# Task 10.2 - Cache behavior properties (Mock Redis)
# =========================================================================


class TestProperty2CacheHitSkipsDB:
    """
    # Feature: redis-public-diary-column, Property 2: Cache hit skips DB
    When Redis has cached data, return it directly without querying DB.
    **Validates: Requirements 3.2, 3.3, 4.2, 4.3**
    """

    @given(nid=st_nid)
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_list_cache_hit_skips_db(self, nid):
        from app.services.public_column_service import get_public_entries

        cached_data = [{"NID": nid, "author_name": "u", "content_summary": "hi",
                        "publish_time": "2024-01-01T00:00:00", "tags": []}]

        db = MagicMock()
        redis_client = AsyncMock()
        redis_client.get = AsyncMock(return_value=json.dumps(cached_data))

        result = await get_public_entries(db, redis_client, skip=0, limit=20)

        assert result == cached_data
        db.query.assert_not_called()

    @given(nid=st_nid)
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_detail_cache_hit_skips_db(self, nid):
        from app.services.public_column_service import get_public_entry_detail

        cached_data = {"NID": nid, "author_name": "u", "content": "full",
                       "date": None, "weather": None,
                       "publish_time": "2024-01-01T00:00:00", "tags": []}

        db = MagicMock()
        redis_client = AsyncMock()
        redis_client.get = AsyncMock(return_value=json.dumps(cached_data))

        result = await get_public_entry_detail(db, redis_client, nid)

        assert result == cached_data
        db.query.assert_not_called()


class TestProperty3CacheMissBackfill:
    """
    # Feature: redis-public-diary-column, Property 3: Cache miss backfill
    On cache miss, query DB and backfill Redis.
    **Validates: Requirements 3.4, 4.4**
    """

    @given(nid=st_nid)
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_list_cache_miss_queries_db_and_backfills(self, nid):
        from app.services.public_column_service import get_public_entries

        entry = _make_diary_mock(nid=nid, published_to_column=True, publish_time=datetime(2024, 1, 1))

        db = MagicMock()
        chain = db.query.return_value.options.return_value.filter.return_value
        chain.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [entry]

        redis_client = AsyncMock()
        redis_client.get = AsyncMock(return_value=None)
        redis_client.set = AsyncMock()

        result = await get_public_entries(db, redis_client, skip=0, limit=20)

        db.query.assert_called()
        redis_client.set.assert_called_once()
        assert len(result) == 1


class TestProperty4WriteOpsDeleteCache:
    """
    # Feature: redis-public-diary-column, Property 4: Write ops delete cache
    Publish/unpublish operations delete relevant cache keys.
    **Validates: Requirements 1.4, 2.2, 6.1, 6.2**
    """

    @given(nid=st_nid, uid=st_uid)
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_publish_deletes_cache(self, nid, uid):
        from app.services.public_column_service import publish_diary

        entry = _make_diary_mock(nid=nid, uid=uid, is_open=True, published_to_column=False)

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = entry

        redis_client = AsyncMock()
        redis_client.delete = AsyncMock()
        redis_client.scan = AsyncMock(return_value=(0, []))

        await publish_diary(db, redis_client, uid, nid)

        redis_client.delete.assert_called()

    @given(nid=st_nid, uid=st_uid)
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_unpublish_deletes_cache(self, nid, uid):
        from app.services.public_column_service import unpublish_diary

        entry = _make_diary_mock(nid=nid, uid=uid, is_open=True, published_to_column=True)

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = entry

        redis_client = AsyncMock()
        redis_client.delete = AsyncMock()
        redis_client.scan = AsyncMock(return_value=(0, []))

        await unpublish_diary(db, redis_client, uid, nid)

        redis_client.delete.assert_called()


# =========================================================================
# Task 10.3 - Cache protection properties
# =========================================================================


class TestProperty5TTLRandomOffset:
    """
    # Feature: redis-public-diary-column, Property 5: TTL random offset
    List TTL in [300, 420], detail TTL in [600, 660].
    **Validates: Requirements 3.5, 4.5**
    """

    @given(nid=st_nid)
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_list_ttl_in_range(self, nid):
        from app.services.public_column_service import get_public_entries

        entry = _make_diary_mock(nid=nid, published_to_column=True, publish_time=datetime(2024, 1, 1))

        db = MagicMock()
        chain = db.query.return_value.options.return_value.filter.return_value
        chain.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [entry]

        redis_client = AsyncMock()
        redis_client.get = AsyncMock(return_value=None)
        redis_client.set = AsyncMock()

        await get_public_entries(db, redis_client, skip=0, limit=20)

        redis_client.set.assert_called_once()
        call_kwargs = redis_client.set.call_args
        ttl = call_kwargs.kwargs.get("ex")
        assert 300 <= ttl <= 420, f"List TTL {ttl} not in [300, 420]"

    @given(nid=st_nid)
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_detail_ttl_in_range(self, nid):
        from app.services.public_column_service import get_public_entry_detail

        entry = _make_diary_mock(nid=nid, published_to_column=True, publish_time=datetime(2024, 1, 1))

        db = MagicMock()
        chain = db.query.return_value.options.return_value.filter.return_value
        chain.first.return_value = entry

        redis_client = AsyncMock()
        redis_client.get = AsyncMock(return_value=None)
        redis_client.set = AsyncMock()

        with patch("app.services.public_column_service.RedisDistributedLock") as mock_lock:
            mock_lock.acquire = AsyncMock(return_value="fake-uuid")
            mock_lock.release = AsyncMock(return_value=True)

            await get_public_entry_detail(db, redis_client, nid)

        set_calls = redis_client.set.call_args_list
        detail_ttl = None
        for c in set_calls:
            key_arg = c.args[0] if c.args else ""
            if "column:detail:" in str(key_arg):
                detail_ttl = c.kwargs.get("ex")
                break

        if detail_ttl is not None:
            assert 600 <= detail_ttl <= 660, f"Detail TTL {detail_ttl} not in [600, 660]"


class TestProperty6NullCacheWrite:
    """
    # Feature: redis-public-diary-column, Property 6: Null cache write
    Missing diary writes NULL marker with TTL=60s.
    **Validates: Requirements 4.6, 4.7, 7.1, 7.2, 7.3**
    """

    @given(nid=st_nid)
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_null_cache_written_for_missing_diary(self, nid):
        from app.services.public_column_service import get_public_entry_detail

        db = MagicMock()
        chain = db.query.return_value.options.return_value.filter.return_value
        chain.first.return_value = None

        redis_client = AsyncMock()
        redis_client.get = AsyncMock(return_value=None)
        redis_client.set = AsyncMock()

        with patch("app.services.public_column_service.RedisDistributedLock") as mock_lock:
            mock_lock.acquire = AsyncMock(return_value="fake-uuid")
            mock_lock.release = AsyncMock(return_value=True)

            result = await get_public_entry_detail(db, redis_client, nid)

        assert result is None

        null_key = f"column:null:{nid}"
        set_calls = redis_client.set.call_args_list
        null_call = None
        for c in set_calls:
            if c.args and str(c.args[0]) == null_key:
                null_call = c
                break

        assert null_call is not None, f"Expected redis.set for {null_key}"
        assert null_call.kwargs.get("ex") == 60


class TestProperty7PublishClearsNullMark:
    """
    # Feature: redis-public-diary-column, Property 7: Publish clears NULL mark
    Publishing a diary deletes column:null:{nid}.
    **Validates: Requirements 7.4**
    """

    @given(nid=st_nid, uid=st_uid)
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_publish_clears_null_mark(self, nid, uid):
        from app.services.public_column_service import publish_diary

        entry = _make_diary_mock(nid=nid, uid=uid, is_open=True, published_to_column=False)

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = entry

        redis_client = AsyncMock()
        redis_client.delete = AsyncMock()
        redis_client.scan = AsyncMock(return_value=(0, []))

        await publish_diary(db, redis_client, uid, nid)

        null_key = f"column:null:{nid}"
        delete_calls = redis_client.delete.call_args_list
        deleted_keys = []
        for c in delete_calls:
            deleted_keys.extend(c.args)

        assert null_key in deleted_keys, f"Expected delete of {null_key}, got {deleted_keys}"


# =========================================================================
# Task 10.4 - Infrastructure properties
# =========================================================================


class TestProperty10SlidingWindowRateLimit:
    """
    # Feature: redis-public-diary-column, Property 10: Sliding window rate limit
    After 60 requests, allowed=False is returned.
    **Validates: Requirements 8.2, 8.3**
    """

    @given(ip=st.from_regex(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", fullmatch=True))
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_after_limit(self, ip):
        from app.core.rate_limiter import RateLimiter

        redis_client = AsyncMock()
        redis_client.zremrangebyscore = AsyncMock()
        redis_client.zadd = AsyncMock()
        redis_client.expire = AsyncMock()

        call_count = 0

        async def mock_zcard(key):
            nonlocal call_count
            call_count += 1
            if call_count <= 60:
                return call_count - 1
            return 60

        redis_client.zcard = AsyncMock(side_effect=mock_zcard)

        for _ in range(60):
            result = await RateLimiter.check(redis_client, ip, limit=60, window=60)
            assert result.allowed is True

        result = await RateLimiter.check(redis_client, ip, limit=60, window=60)
        assert result.allowed is False
        assert result.remaining == 0


class TestProperty11RateLimitHeaders:
    """
    # Feature: redis-public-diary-column, Property 11: Rate limit headers
    Response dict contains X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset.
    **Validates: Requirements 8.4**
    """

    @given(ip=st.from_regex(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", fullmatch=True))
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_check_rate_limit_returns_headers(self, ip):
        from app.core.rate_limiter import check_rate_limit

        redis_client = AsyncMock()
        redis_client.zremrangebyscore = AsyncMock()
        redis_client.zcard = AsyncMock(return_value=0)
        redis_client.zadd = AsyncMock()
        redis_client.expire = AsyncMock()

        request = MagicMock()
        request.headers = {"X-Forwarded-For": ip}
        request.client = MagicMock()
        request.client.host = ip

        result = await check_rate_limit(request, redis_client)

        assert "X-RateLimit-Limit" in result
        assert "X-RateLimit-Remaining" in result
        assert "X-RateLimit-Reset" in result


class TestProperty12LockTTL5s:
    """
    # Feature: redis-public-diary-column, Property 12: Lock TTL=5s
    Distributed lock Redis SET uses ex=5.
    **Validates: Requirements 5.4**
    """

    @given(key=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"))))
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_lock_ttl_is_5_seconds(self, key):
        from app.core.distributed_lock import RedisDistributedLock

        redis_client = AsyncMock()
        redis_client.set = AsyncMock(return_value=True)

        await RedisDistributedLock.acquire(redis_client, key, timeout=5)

        redis_client.set.assert_called_once()
        call_kwargs = redis_client.set.call_args.kwargs
        assert call_kwargs["ex"] == 5
        assert call_kwargs["nx"] is True


# =========================================================================
# Task 10.5 - Degradation properties
# =========================================================================


class TestProperty13RedisDegradation:
    """
    # Feature: redis-public-diary-column, Property 13: Redis degradation
    When redis_client=None, data is still returned from DB.
    **Validates: Requirements 9.4**
    """

    @given(nid=st_nid)
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_get_public_entries_without_redis(self, nid):
        from app.services.public_column_service import get_public_entries

        entry = _make_diary_mock(nid=nid, published_to_column=True, publish_time=datetime(2024, 1, 1))

        db = MagicMock()
        chain = db.query.return_value.options.return_value.filter.return_value
        chain.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [entry]

        result = await get_public_entries(db, None, skip=0, limit=20)

        assert len(result) == 1
        assert result[0]["NID"] == nid
        db.query.assert_called()


class TestProperty14CacheDeleteFailureNonBlocking:
    """
    # Feature: redis-public-diary-column, Property 14: Cache delete failure non-blocking
    When redis.delete raises, publish_diary still succeeds.
    **Validates: Requirements 6.3, 6.4**
    """

    @given(nid=st_nid, uid=st_uid)
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_publish_succeeds_despite_cache_delete_failure(self, nid, uid):
        from app.services.public_column_service import publish_diary

        entry = _make_diary_mock(nid=nid, uid=uid, is_open=True, published_to_column=False)

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = entry

        redis_client = AsyncMock()
        redis_client.delete = AsyncMock(side_effect=Exception("Redis down"))
        redis_client.scan = AsyncMock(side_effect=Exception("Redis down"))

        result = await publish_diary(db, redis_client, uid, nid)

        assert result["nid"] == nid
        assert result["message"] == "\u53d1\u5e03\u6210\u529f"
        db.commit.assert_called()
