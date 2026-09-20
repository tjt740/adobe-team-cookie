import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
# 导入所有模型,保证 create_all 能建全部表
from app.models import external_member as _em  # noqa: F401
from app.models import adobe_account as _aa  # noqa: F401
from app.models import adobe_member as _am  # noqa: F401
from app.models import email as _e  # noqa: F401
from app.models import setting as _s  # noqa: F401
from app.models import user as _u  # noqa: F401


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture
def SessionLocal(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db(SessionLocal):
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def client(SessionLocal, engine, monkeypatch):
    """TestClient(app) 不进入 lifespan(不触发真实 init_db),仅覆盖依赖。"""
    from app.api.deps import get_current_user
    from app.main import app
    from app.models.user import User
    from app.services import job_manager

    monkeypatch.setattr(job_manager, "engine", engine)
    monkeypatch.setattr(job_manager.JOBS, "_jobs", {})
    monkeypatch.setattr(job_manager.JOBS, "_counter", 0)
    monkeypatch.setattr(job_manager.JOBS, "_storage_ready", False)

    def _override_db():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    def _override_user():
        return User(id=1, username="tester", is_active=True, is_superuser=True)

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    # 不用 `with TestClient(app)`:那会触发 lifespan → 对真实 app.db 跑 init_db。
    # 纯实例化不进入 lifespan,请求仍走被覆盖的 get_db(内存库)。
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()
