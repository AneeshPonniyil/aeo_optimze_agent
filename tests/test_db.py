import pytest
import respx
from httpx import Response
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.db.database import Base
from app.db.repository import AuditRepository
from app.config import settings


@pytest.fixture
async def test_db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_audit_repository_lifecycle(test_db_session: AsyncSession):
    # 1. Create pending audit
    audit = await AuditRepository.create_audit(test_db_session, url="https://zenvora.ai")
    assert audit.id is not None
    assert audit.status == "pending"

    # 2. Complete audit with findings
    findings_data = [
        {
            "check_id": "CHECK-TITLE-01",
            "category": "SEO",
            "title": "Missing Title",
            "description": "No title tag",
            "severity": "critical",
            "evidence": "N/A",
            "suggested_fix": "Add title",
            "is_llm_generated": False,
        }
    ]
    completed = await AuditRepository.complete_audit(
        session=test_db_session,
        audit_id=audit.id,
        score=85,
        fetch_time=0.45,
        page_metadata_dict={"title": "Zenvora AI"},
        findings_data=findings_data,
    )
    assert completed.status == "completed"
    assert completed.score == 85
    assert len(completed.findings) == 1
    assert completed.findings[0].check_id == "CHECK-TITLE-01"

    # 3. Retrieve audit by ID
    fetched = await AuditRepository.get_audit_by_id(test_db_session, audit.id)
    assert fetched is not None
    assert fetched.url == "https://zenvora.ai"

    # 4. List audits
    audits_list = await AuditRepository.list_audits(test_db_session)
    assert len(audits_list) == 1
    assert audits_list[0].id == audit.id

    # 5. Delete audit
    deleted = await AuditRepository.delete_audit(test_db_session, audit.id)
    assert deleted is True
    assert await AuditRepository.get_audit_by_id(test_db_session, audit.id) is None


@pytest.mark.asyncio
async def test_audit_api_integration(async_client):
    mock_html = """
    <html>
        <head><title>Zenvora Audit Test Page</title></head>
        <body>
            <h1>Main Topic</h1>
            <h2>Sub section</h2>
            <p>""" + "Content word " * 350 + """</p>
            <script type="application/ld+json">{"@type": "WebPage"}</script>
        </body>
    </html>
    """

    with respx.mock:
        respx.get("https://example.com/test-audit").mock(
            return_value=Response(200, text=mock_html, headers={"content-type": "text/html"})
        )
        respx.get("https://example.com/robots.txt").mock(
            return_value=Response(200, text="User-agent: *\nAllow: /")
        )

        # 1. Trigger Audit via POST API
        response = await async_client.post(
            "/api/v1/audits",
            json={"url": "https://example.com/test-audit"},
            headers={"X-API-Key": settings.AUDIT_API_KEY},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "completed"
        assert data["score"] >= 70
        audit_id = data["id"]

        # 2. Get Audit by ID via GET API
        get_resp = await async_client.get(f"/api/v1/audits/{audit_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == audit_id

        # 3. Get History List via GET API
        hist_resp = await async_client.get("/api/v1/audits")
        assert hist_resp.status_code == 200
        hist_data = hist_resp.json()
        assert hist_data["total"] >= 1

        # 4. Delete Audit via DELETE API
        del_resp = await async_client.delete(
            f"/api/v1/audits/{audit_id}",
            headers={"X-API-Key": settings.AUDIT_API_KEY},
        )
        assert del_resp.status_code == 204
