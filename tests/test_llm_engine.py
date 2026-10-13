import pytest
import respx
from httpx import Response
from app.core.llm.mock_provider import MockLLMProvider
from app.core.llm.engine import AEOCopilotEngine
from app.core.analyzer import HTMLParserService, DeterministicTechnicalAnalyzer
from app.schemas.aeo import AEOCopilotResult


SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Zenvora AI Test Page</title>
    <meta name="description" content="A comprehensive guide to Answer Engine Optimization and modern generative search strategies.">
</head>
<body>
    <h1>Understanding AEO Engine Optimization</h1>
    <h2>What is Answer Engine Optimization?</h2>
    <p>""" + "AEO optimizes content so AI tools cite your brand directly. " * 25 + """</p>
</body>
</html>
"""


@pytest.mark.asyncio
async def test_mock_llm_provider_grounding():
    parsed = HTMLParserService.parse_html(
        target_url="https://zenvora.ai/test",
        status_code=200,
        html_text=SAMPLE_HTML,
        headers={"content-type": "text/html"},
        fetch_time=0.2
    )
    summary = DeterministicTechnicalAnalyzer.analyze(parsed)

    provider = MockLLMProvider()
    result = await provider.generate_aeo_recommendations(parsed, summary.findings)

    assert isinstance(result, AEOCopilotResult)
    assert 0 <= result.entity_clarity_score <= 100
    assert 0 <= result.answer_readiness_score <= 100
    assert len(result.key_recommendations) > 0
    assert len(result.faq_opportunities) > 0
    assert result.suggested_json_ld_schema is not None
    assert "FAQPage" in result.key_recommendations[0].suggested_schema_code or "FAQPage" in result.key_recommendations[0].title


@pytest.mark.asyncio
async def test_aeo_engine_fallback():
    # Force provider to mock fallback
    result = await AEOCopilotEngine.analyze_page(
        HTMLParserService.parse_html("https://example.com", 200, SAMPLE_HTML, {}, 0.1),
        []
    )
    assert isinstance(result, AEOCopilotResult)
    assert "AEO Analysis for" in result.summary


@pytest.mark.asyncio
async def test_audit_api_includes_aeo_summary(async_client):
    with respx.mock:
        respx.get("https://example.com/aeo-test").mock(
            return_value=Response(200, text=SAMPLE_HTML, headers={"content-type": "text/html"})
        )
        respx.get("https://example.com/robots.txt").mock(
            return_value=Response(200, text="User-agent: *\nAllow: /")
        )

        response = await async_client.post(
            "/api/v1/audits",
            json={"url": "https://example.com/aeo-test"}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["aeo_summary"] is not None
        assert "entity_clarity_score" in data["aeo_summary"]
        assert "key_recommendations" in data["aeo_summary"]
        assert len(data["aeo_summary"]["key_recommendations"]) > 0
