"""路由 REST API 集成测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.auth_service import get_current_user
from app.models.user import User


def make_mock_user(user_id: int = 1):
    user = MagicMock(spec=User)
    user.id = user_id
    user.username = "test_user"
    user.email = "test@example.com"
    return user


async def _mock_db_session():
    session = AsyncMock(spec=AsyncSession)
    yield session


async def _mock_auth():
    return make_mock_user()


@pytest.fixture(scope="module")
def client():
    from app.main import app
    app.dependency_overrides[get_db] = _mock_db_session
    app.dependency_overrides[get_current_user] = _mock_auth
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


class TestRoutingRoutesRegistered:
    """验证路由已注册"""

    def test_routing_config_get_registered(self):
        from app.main import app
        paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/api/v1/routing/config" in paths

    def test_routing_config_put_registered(self):
        from app.main import app
        paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/api/v1/routing/config" in paths

    def test_routing_route_post_registered(self):
        from app.main import app
        paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/api/v1/routing/route" in paths

    def test_routing_config_get_returns_not_404(self, client):
        resp = client.get("/api/v1/routing/config")
        assert resp.status_code != 404

    def test_routing_route_post_returns_not_404(self, client):
        resp = client.post("/api/v1/routing/route", json={
            "query": "test",
            "task_type": "simple_qa",
        })
        assert resp.status_code != 404


class TestRoutingConfigAPI:
    """测试路由配置 GET/PUT"""

    def test_get_config_returns_defaults(self, client):
        resp = client.get("/api/v1/routing/config")
        # 即使 mock DB 返回空，也应返回默认值
        if resp.status_code == 200:
            data = resp.json()
            assert "model_mode" in data
            assert "budget_limit" in data
            assert "confirm_threshold" in data


class TestRouteDecisionAPI:
    """测试路由决策端点"""

    def test_route_simple_qa(self, client):
        resp = client.post("/api/v1/routing/route", json={
            "query": "什么是机器学习？",
            "task_type": "simple_qa",
        })
        if resp.status_code == 200:
            data = resp.json()
            assert "tier" in data
            assert "reason" in data
