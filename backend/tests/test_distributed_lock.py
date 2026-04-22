"""
RedisDistributedLock 单元测试
使用 unittest.mock 模拟 Redis 客户端行为
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.distributed_lock import RedisDistributedLock


@pytest.fixture
def mock_redis():
    """创建模拟的 Redis 异步客户端"""
    client = AsyncMock()
    return client


class TestAcquire:
    """测试 acquire 方法"""

    @pytest.mark.asyncio
    async def test_acquire_success_returns_uuid(self, mock_redis):
        """成功获取锁时返回 UUID 字符串"""
        mock_redis.set.return_value = True

        result = await RedisDistributedLock.acquire(mock_redis, "test:lock:1")

        assert result is not None
        # UUID 格式: 8-4-4-4-12 hex chars
        parts = result.split("-")
        assert len(parts) == 5

    @pytest.mark.asyncio
    async def test_acquire_calls_set_with_nx_ex(self, mock_redis):
        """acquire 使用 SET NX EX 参数"""
        mock_redis.set.return_value = True

        await RedisDistributedLock.acquire(mock_redis, "test:lock:1", timeout=5)

        mock_redis.set.assert_called_once()
        call_kwargs = mock_redis.set.call_args
        assert call_kwargs.kwargs["nx"] is True
        assert call_kwargs.kwargs["ex"] == 5

    @pytest.mark.asyncio
    async def test_acquire_failure_returns_none(self, mock_redis):
        """锁已被占用时返回 None"""
        mock_redis.set.return_value = False

        result = await RedisDistributedLock.acquire(mock_redis, "test:lock:1")

        assert result is None

    @pytest.mark.asyncio
    async def test_acquire_custom_timeout(self, mock_redis):
        """支持自定义超时时间"""
        mock_redis.set.return_value = True

        await RedisDistributedLock.acquire(mock_redis, "test:lock:1", timeout=10)

        call_kwargs = mock_redis.set.call_args
        assert call_kwargs.kwargs["ex"] == 10

    @pytest.mark.asyncio
    async def test_acquire_exception_returns_none(self, mock_redis):
        """Redis 异常时返回 None"""
        mock_redis.set.side_effect = Exception("Connection refused")

        result = await RedisDistributedLock.acquire(mock_redis, "test:lock:1")

        assert result is None


class TestRelease:
    """测试 release 方法"""

    @pytest.mark.asyncio
    async def test_release_success(self, mock_redis):
        """值匹配时释放成功返回 True"""
        mock_redis.eval.return_value = 1

        result = await RedisDistributedLock.release(mock_redis, "test:lock:1", "some-uuid")

        assert result is True

    @pytest.mark.asyncio
    async def test_release_value_mismatch(self, mock_redis):
        """值不匹配时返回 False"""
        mock_redis.eval.return_value = 0

        result = await RedisDistributedLock.release(mock_redis, "test:lock:1", "wrong-uuid")

        assert result is False

    @pytest.mark.asyncio
    async def test_release_uses_lua_script(self, mock_redis):
        """release 使用 Lua 脚本进行原子操作"""
        mock_redis.eval.return_value = 1

        await RedisDistributedLock.release(mock_redis, "test:lock:1", "my-uuid")

        mock_redis.eval.assert_called_once()
        args = mock_redis.eval.call_args.args
        # args: (script, numkeys, key, lock_value)
        assert "get" in args[0] and "del" in args[0]
        assert args[1] == 1
        assert args[2] == "test:lock:1"
        assert args[3] == "my-uuid"

    @pytest.mark.asyncio
    async def test_release_exception_returns_false(self, mock_redis):
        """Redis 异常时返回 False"""
        mock_redis.eval.side_effect = Exception("Connection refused")

        result = await RedisDistributedLock.release(mock_redis, "test:lock:1", "some-uuid")

        assert result is False


class TestAcquireReleaseCycle:
    """测试获取-释放完整流程"""

    @pytest.mark.asyncio
    async def test_acquire_then_release(self, mock_redis):
        """获取锁后使用返回的 lock_value 释放"""
        mock_redis.set.return_value = True
        mock_redis.eval.return_value = 1

        lock_value = await RedisDistributedLock.acquire(mock_redis, "test:lock:1")
        assert lock_value is not None

        released = await RedisDistributedLock.release(mock_redis, "test:lock:1", lock_value)
        assert released is True

        # 验证 release 使用了 acquire 返回的 lock_value
        release_args = mock_redis.eval.call_args.args
        assert release_args[3] == lock_value
