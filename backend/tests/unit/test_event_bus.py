"""EventBus 单元测试

测试 app.services.core.event_bus 的核心功能：
- 事件发布和订阅
- 多个订阅者
- 异步订阅者
- 取消订阅
- 事件类型隔离
"""
import pytest
import pytest_asyncio

from app.services.core.event_bus import EventBus, Event, EventTypes


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def bus():
    """每个测试用独立的 EventBus 实例，避免状态污染"""
    return EventBus()


# ── 测试：事件发布和订阅 ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_subscribe_and_publish(bus):
    """发布事件后订阅者被调用"""
    received = []

    def handler(event: Event):
        received.append(event)

    bus.subscribe("test.event", handler)
    await bus.publish(Event(type="test.event", data={"key": "value"}))

    assert len(received) == 1
    assert received[0].type == "test.event"
    assert received[0].data == {"key": "value"}


@pytest.mark.asyncio
async def test_publish_no_subscribers_does_not_raise(bus):
    """发布没有订阅者的事件不应抛出异常"""
    # 不应抛出
    await bus.publish(Event(type="no.subscribers"))


# ── 测试：多个订阅者 ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_multiple_subscribers_all_called(bus):
    """同一事件多个订阅者都被调用"""
    calls = []

    def handler_a(event: Event):
        calls.append("A")

    def handler_b(event: Event):
        calls.append("B")

    bus.subscribe("multi.event", handler_a)
    bus.subscribe("multi.event", handler_b)
    await bus.publish(Event(type="multi.event"))

    assert "A" in calls
    assert "B" in calls
    assert len(calls) == 2


# ── 测试：异步订阅者 ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_async_handler_executed(bus):
    """async handler 正确执行"""
    received = []

    async def async_handler(event: Event):
        received.append(event.type)

    bus.subscribe("async.event", async_handler)
    await bus.publish(Event(type="async.event", data={"n": 42}))

    assert received == ["async.event"]


@pytest.mark.asyncio
async def test_mixed_sync_async_handlers(bus):
    """同步和异步处理器可以混合使用"""
    order = []

    def sync_handler(event: Event):
        order.append("sync")

    async def async_handler(event: Event):
        order.append("async")

    bus.subscribe("mixed.event", sync_handler)
    bus.subscribe("mixed.event", async_handler)
    await bus.publish(Event(type="mixed.event"))

    assert set(order) == {"sync", "async"}
    assert len(order) == 2


# ── 测试：取消订阅 ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unsubscribe_stops_receiving(bus):
    """取消订阅后不再收到事件"""
    received = []

    def handler(event: Event):
        received.append(event)

    bus.subscribe("unsub.event", handler)
    bus.unsubscribe("unsub.event", handler)
    await bus.publish(Event(type="unsub.event"))

    assert len(received) == 0


@pytest.mark.asyncio
async def test_unsubscribe_nonexistent_handler_does_not_raise(bus):
    """取消不存在的订阅不应抛出异常"""
    def handler(event: Event):
        pass

    # 既没有订阅，取消也不应抛出
    bus.unsubscribe("no.event", handler)


@pytest.mark.asyncio
async def test_unsubscribe_one_of_multiple(bus):
    """取消一个订阅者，另一个仍然被调用"""
    calls = []

    def handler_a(event: Event):
        calls.append("A")

    def handler_b(event: Event):
        calls.append("B")

    bus.subscribe("partial.unsub", handler_a)
    bus.subscribe("partial.unsub", handler_b)
    bus.unsubscribe("partial.unsub", handler_a)

    await bus.publish(Event(type="partial.unsub"))

    assert calls == ["B"]


# ── 测试：事件类型隔离 ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_event_type_isolation(bus):
    """订阅者只收到自己订阅的事件类型"""
    received_a = []
    received_b = []

    def handler_a(event: Event):
        received_a.append(event)

    def handler_b(event: Event):
        received_b.append(event)

    bus.subscribe("type.A", handler_a)
    bus.subscribe("type.B", handler_b)

    await bus.publish(Event(type="type.A"))

    assert len(received_a) == 1
    assert len(received_b) == 0


# ── 测试：处理器异常不影响其他处理器 ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_handler_exception_does_not_stop_others(bus):
    """单个处理器抛出异常不影响其他处理器执行"""
    received = []

    def bad_handler(event: Event):
        raise RuntimeError("故意抛出的异常")

    def good_handler(event: Event):
        received.append(event)

    bus.subscribe("error.event", bad_handler)
    bus.subscribe("error.event", good_handler)

    # 不应抛出异常
    await bus.publish(Event(type="error.event"))

    assert len(received) == 1


# ── 测试：辅助方法 ────────────────────────────────────────────────────────────

def test_has_handlers(bus):
    """has_handlers 正确反映订阅状态"""
    assert bus.has_handlers("x.event") is False

    def handler(event: Event):
        pass

    bus.subscribe("x.event", handler)
    assert bus.has_handlers("x.event") is True


def test_get_handler_count(bus):
    """get_handler_count 返回正确数量"""
    def h1(e): pass
    def h2(e): pass

    assert bus.get_handler_count("cnt.event") == 0
    bus.subscribe("cnt.event", h1)
    assert bus.get_handler_count("cnt.event") == 1
    bus.subscribe("cnt.event", h2)
    assert bus.get_handler_count("cnt.event") == 2


def test_clear_removes_all_handlers(bus):
    """clear() 清空所有订阅"""
    def h(e): pass
    bus.subscribe("e1", h)
    bus.subscribe("e2", h)

    bus.clear()

    assert bus.has_handlers("e1") is False
    assert bus.has_handlers("e2") is False


# ── 测试：EventTypes 常量 ────────────────────────────────────────────────────

def test_event_types_constants_exist():
    """EventTypes 中所有常量都存在且为字符串"""
    constants = [
        EventTypes.PAPER_UPLOADED,
        EventTypes.PAPER_DELETED,
        EventTypes.ANALYSIS_COMPLETED,
        EventTypes.SESSION_CREATED,
        EventTypes.INDEX_REBUILD_STARTED,
        EventTypes.INDEX_REBUILD_COMPLETED,
        EventTypes.SETTINGS_CHANGED,
        EventTypes.INDEX_REBUILT,
    ]
    for c in constants:
        assert isinstance(c, str)
        assert len(c) > 0
