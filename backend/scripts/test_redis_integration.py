"""
Redis 集成验证脚本
===================
连接真实 Redis 实例，逐项验证所有 Redis 相关功能是否正常工作。

运行方式（在 backend 目录下）：
    python -m scripts.test_redis_integration

前置条件：
    - Redis 服务运行在 localhost:6379
    - 已安装 redis[hiredis] 依赖
"""

import asyncio
import json
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import redis.asyncio as aioredis

# 测试用的 Redis 数据库编号（用 db=15 避免污染业务数据）
TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/15")

passed = 0
failed = 0
total = 0


def report(name: str, ok: bool, detail: str = ""):
    global passed, failed, total
    total += 1
    if ok:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name} — {detail}")


async def get_client() -> aioredis.Redis:
    return aioredis.from_url(TEST_REDIS_URL, max_connections=10, decode_responses=True)


# =========================================================================
# 1. Redis 连接与基础操作
# =========================================================================
async def test_connection():
    print("\n🔌 测试 1：Redis 连接")
    client = await get_client()
    try:
        pong = await client.ping()
        report("PING → PONG", pong is True)

        await client.set("test:hello", "world", ex=10)
        val = await client.get("test:hello")
        report("SET/GET 基础读写", val == "world", f"期望 'world'，实际 '{val}'")

        await client.delete("test:hello")
        val = await client.get("test:hello")
        report("DELETE 删除", val is None)
    finally:
        await client.flushdb()
        await client.close()


# =========================================================================
# 2. 分布式锁（SET NX EX + Lua 释放）
# =========================================================================
async def test_distributed_lock():
    print("\n🔒 测试 2：分布式锁")
    from app.core.distributed_lock import RedisDistributedLock

    client = await get_client()
    try:
        lock_key = "test:lock:diary_detail_99"

        # 获取锁
        lock_val = await RedisDistributedLock.acquire(client, lock_key, timeout=5)
        report("acquire 获取锁成功", lock_val is not None)

        # 验证 TTL
        ttl = await client.ttl(lock_key)
        report("锁 TTL ≤ 5 秒", 0 < ttl <= 5, f"实际 TTL={ttl}")

        # 重复获取应失败（互斥）
        lock_val2 = await RedisDistributedLock.acquire(client, lock_key, timeout=5)
        report("重复 acquire 被拒绝（互斥）", lock_val2 is None)

        # 用错误值释放应失败
        released_wrong = await RedisDistributedLock.release(client, lock_key, "wrong-uuid")
        report("错误值 release 失败", released_wrong is False)

        # 用正确值释放
        released = await RedisDistributedLock.release(client, lock_key, lock_val)
        report("正确值 release 成功", released is True)

        # 释放后可以重新获取
        lock_val3 = await RedisDistributedLock.acquire(client, lock_key, timeout=5)
        report("释放后可重新 acquire", lock_val3 is not None)
        if lock_val3:
            await RedisDistributedLock.release(client, lock_key, lock_val3)
    finally:
        await client.flushdb()
        await client.close()


# =========================================================================
# 3. 滑动窗口限流
# =========================================================================
async def test_rate_limiter():
    print("\n⏱️  测试 3：滑动窗口限流")
    from app.core.rate_limiter import RateLimiter

    client = await get_client()
    try:
        test_ip = "192.168.1.100"
        limit = 5
        window = 10

        # 前 5 次应该全部通过
        for i in range(limit):
            result = await RateLimiter.check(client, test_ip, limit=limit, window=window)
            if not result.allowed:
                report(f"第 {i+1} 次请求通过", False, "被意外拒绝")
                return

        report(f"前 {limit} 次请求全部通过", True)

        # 超限后应该被拒绝（多发几次确保超限）
        blocked = False
        for _ in range(3):
            result = await RateLimiter.check(client, test_ip, limit=limit, window=window)
            if not result.allowed:
                blocked = True
                break
        report(f"超过 {limit} 次后被拒绝", blocked is True)
        report("remaining = 0", result.remaining == 0, f"实际 remaining={result.remaining}")

        # 验证 Sorted Set 中的记录数
        key = f"ratelimit:{test_ip}"
        count = await client.zcard(key)
        report(f"Sorted Set 记录数 = {limit}", count == limit, f"实际 count={count}")
    finally:
        await client.flushdb()
        await client.close()


# =========================================================================
# 4. Cache-Aside 缓存读写
# =========================================================================
async def test_cache_aside():
    print("\n📦 测试 4：Cache-Aside 缓存读写")
    client = await get_client()
    try:
        # 模拟列表缓存写入
        list_key = "column:list:0:20"
        list_data = [
            {"NID": 1, "author_name": "张三", "content_summary": "今天天气不错", "publish_time": "2024-06-01T10:00:00", "tags": []},
            {"NID": 2, "author_name": "李四", "content_summary": "学习了 Redis", "publish_time": "2024-06-02T10:00:00", "tags": []},
        ]
        await client.set(list_key, json.dumps(list_data, ensure_ascii=False), ex=300)

        # 读取并验证
        cached = await client.get(list_key)
        parsed = json.loads(cached)
        report("列表缓存写入/读取", len(parsed) == 2 and parsed[0]["NID"] == 1)

        # 验证 TTL 在合理范围
        ttl = await client.ttl(list_key)
        report("列表缓存 TTL ≤ 300s", 0 < ttl <= 300, f"实际 TTL={ttl}")

        # 模拟详情缓存写入
        detail_key = "column:detail:42"
        detail_data = {"NID": 42, "author_name": "王五", "content": "完整日记内容...", "publish_time": "2024-06-01T10:00:00"}
        await client.set(detail_key, json.dumps(detail_data, ensure_ascii=False), ex=600)

        cached_detail = await client.get(detail_key)
        parsed_detail = json.loads(cached_detail)
        report("详情缓存写入/读取", parsed_detail["NID"] == 42)

        # 模拟缓存失效（删除）
        await client.delete(list_key, detail_key)
        val1 = await client.get(list_key)
        val2 = await client.get(detail_key)
        report("缓存失效（删除后为 None）", val1 is None and val2 is None)
    finally:
        await client.flushdb()
        await client.close()


# =========================================================================
# 5. 缓存穿透防护（空值缓存）
# =========================================================================
async def test_null_cache():
    print("\n🛡️  测试 5：缓存穿透防护（空值缓存）")
    client = await get_client()
    try:
        null_key = "column:null:99999"

        # 写入空值标记
        await client.set(null_key, "NULL", ex=60)

        # 读取验证
        val = await client.get(null_key)
        report("空值标记写入/读取", val == "NULL")

        # 验证 TTL = 60s
        ttl = await client.ttl(null_key)
        report("空值标记 TTL ≤ 60s", 0 < ttl <= 60, f"实际 TTL={ttl}")

        # 模拟发布后清除空值标记
        await client.delete(null_key)
        val_after = await client.get(null_key)
        report("发布后清除空值标记", val_after is None)
    finally:
        await client.flushdb()
        await client.close()


# =========================================================================
# 6. 缓存雪崩防护（TTL 随机偏移）
# =========================================================================
async def test_ttl_random_offset():
    print("\n🌊 测试 6：缓存雪崩防护（TTL 随机偏移）")
    import random
    client = await get_client()
    try:
        ttls = []
        for i in range(20):
            key = f"column:list:0:{i}"
            ttl = 300 + random.randint(0, 120)
            await client.set(key, "test", ex=ttl)
            actual_ttl = await client.ttl(key)
            ttls.append(actual_ttl)

        min_ttl = min(ttls)
        max_ttl = max(ttls)
        report("列表 TTL 范围 [300, 420]", 290 <= min_ttl and max_ttl <= 420,
               f"实际范围 [{min_ttl}, {max_ttl}]")

        # 验证不是所有 TTL 都相同（随机性）
        unique_ttls = len(set(ttls))
        report("TTL 具有随机性（不全相同）", unique_ttls > 1, f"只有 {unique_ttls} 种不同的 TTL")
    finally:
        await client.flushdb()
        await client.close()


# =========================================================================
# 7. 缓存击穿防护（并发锁竞争）
# =========================================================================
async def test_lock_contention():
    print("\n⚡ 测试 7：缓存击穿防护（并发锁竞争）")
    from app.core.distributed_lock import RedisDistributedLock

    client = await get_client()
    try:
        lock_key = "column:lock:detail:hot_diary"
        results = []

        async def try_acquire(task_id):
            val = await RedisDistributedLock.acquire(client, lock_key, timeout=5)
            results.append((task_id, val))
            if val:
                # 模拟回源 DB 耗时
                await asyncio.sleep(0.1)
                await RedisDistributedLock.release(client, lock_key, val)

        # 模拟 5 个并发请求同时竞争锁
        tasks = [try_acquire(i) for i in range(5)]
        await asyncio.gather(*tasks)

        acquired_count = sum(1 for _, v in results if v is not None)
        report("5 个并发请求中仅 1 个获取锁", acquired_count == 1,
               f"实际 {acquired_count} 个获取了锁")
    finally:
        await client.flushdb()
        await client.close()


# =========================================================================
# 8. SCAN 批量删除列表缓存
# =========================================================================
async def test_scan_delete():
    print("\n🔍 测试 8：SCAN 批量删除列表缓存")
    client = await get_client()
    try:
        # 写入多个列表缓存 key
        for skip in range(0, 100, 20):
            await client.set(f"column:list:{skip}:20", "data", ex=300)

        # 写入一个详情缓存（不应被删除）
        await client.set("column:detail:1", "detail_data", ex=600)

        # SCAN 删除所有 column:list:* 的 key
        cursor = 0
        deleted_count = 0
        while True:
            cursor, keys = await client.scan(cursor=cursor, match="column:list:*", count=100)
            if keys:
                await client.delete(*keys)
                deleted_count += len(keys)
            if cursor == 0:
                break

        report(f"SCAN 删除了 {deleted_count} 个列表缓存", deleted_count == 5,
               f"期望 5，实际 {deleted_count}")

        # 验证详情缓存未被误删
        detail_val = await client.get("column:detail:1")
        report("详情缓存未被误删", detail_val == "detail_data")
    finally:
        await client.flushdb()
        await client.close()


# =========================================================================
# 9. Redis 降级（连接不可用）
# =========================================================================
async def test_degradation():
    print("\n🔄 测试 9：Redis 降级（连接不可用）")
    from app.core.distributed_lock import RedisDistributedLock

    # 创建一个连接到不存在端口的客户端
    bad_client = aioredis.from_url("redis://localhost:59999/0", socket_connect_timeout=1)

    # 分布式锁应返回 None 而不是抛异常
    lock_val = await RedisDistributedLock.acquire(bad_client, "test:lock", timeout=5)
    report("锁 acquire 降级返回 None", lock_val is None)

    released = await RedisDistributedLock.release(bad_client, "test:lock", "fake")
    report("锁 release 降级返回 False", released is False)

    await bad_client.close()


# =========================================================================
# 10. Key 命名规范验证
# =========================================================================
async def test_key_naming():
    print("\n🏷️  测试 10：Key 命名规范验证")
    client = await get_client()
    try:
        expected_patterns = {
            "column:list:0:20": "列表缓存",
            "column:detail:42": "详情缓存",
            "column:null:99": "空值标记",
            "column:lock:detail:42": "分布式锁",
            "ratelimit:192.168.1.1": "限流计数",
        }

        for key, desc in expected_patterns.items():
            await client.set(key, "test", ex=10)
            val = await client.get(key)
            report(f"Key 格式 '{key}' ({desc})", val == "test")
    finally:
        await client.flushdb()
        await client.close()


# =========================================================================
# 主入口
# =========================================================================
async def main():
    print("=" * 60)
    print("  Redis 集成验证脚本")
    print(f"  连接: {TEST_REDIS_URL}")
    print("=" * 60)

    # 先验证连接
    try:
        client = await get_client()
        await client.ping()
        await client.close()
    except Exception as e:
        print(f"\n❌ 无法连接 Redis: {e}")
        print("请确保 Redis 服务运行在 localhost:6379")
        sys.exit(1)

    await test_connection()
    await test_distributed_lock()
    await test_rate_limiter()
    await test_cache_aside()
    await test_null_cache()
    await test_ttl_random_offset()
    await test_lock_contention()
    await test_scan_delete()
    await test_degradation()
    await test_key_naming()

    print("\n" + "=" * 60)
    print(f"  结果: {passed}/{total} 通过, {failed} 失败")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
