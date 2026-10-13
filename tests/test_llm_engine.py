import pytest
import respx
from httpx import Response
from app.core.llm.mock_provider import MockLLMProvider
from app.core.llm.engine import AEOCopilotEngine
from app.core.analyzer import HTMLParserService, DeterministicTechnicalAnalyzer
from app.schemas.aeo import AEOCopilotResult
from app.config import settings


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
            json={"url": "https://example.com/aeo-test"},
            headers={"X-API-Key": settings.AUDIT_API_KEY},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["aeo_summary"] is not None
        assert "entity_clarity_score" in data["aeo_summary"]
        assert "key_recommendations" in data["aeo_summary"]
        assert len(data["aeo_summary"]["key_recommendations"]) > 0


def test_aeo_suggestion_bounds_enforcement():
    from pydantic import ValidationError
    from app.schemas.aeo import AEOSuggestion

    # Confidence score > 1.0 must be rejected
    with pytest.raises(ValidationError):
        AEOSuggestion(
            check_id="TEST-01",
            title="Invalid Confidence",
            current_state_evidence="Evidence",
            suggested_aeo_content="Content",
            confidence_score=1.2,
            limitations="None"
        )

    # Confidence score < 0.0 must be rejected
    with pytest.raises(ValidationError):
        AEOSuggestion(
            check_id="TEST-02",
            title="Negative Confidence",
            current_state_evidence="Evidence",
            suggested_aeo_content="Content",
            confidence_score=-0.1,
            limitations="None"
        )


def test_aeo_copilot_result_score_bounds():
    from pydantic import ValidationError

    # Entity clarity score > 100 must be rejected
    with pytest.raises(ValidationError):
        AEOCopilotResult(
            summary="Test",
            entity_clarity_score=105,
            answer_readiness_score=80
        )

    # Answer readiness score < 0 must be rejected
    with pytest.raises(ValidationError):
        AEOCopilotResult(
            summary="Test",
            entity_clarity_score=50,
            answer_readiness_score=-5
        )


@pytest.mark.asyncio
async def test_mock_provider_json_ld_syntactic_validity():
    import json
    import re

    parsed = HTMLParserService.parse_html(
        target_url="https://example.com",
        status_code=200,
        html_text=SAMPLE_HTML,
        headers={},
        fetch_time=0.1
    )
    provider = MockLLMProvider()
    result = await provider.generate_aeo_recommendations(parsed, [])

    # Validate suggested_json_ld_schema serializes
    assert result.suggested_json_ld_schema is not None
    serialized = json.dumps(result.suggested_json_ld_schema)
    assert json.loads(serialized) == result.suggested_json_ld_schema

    # Validate embedded script tags parse as valid JSON
    for rec in result.key_recommendations:
        if rec.suggested_schema_code:
            match = re.search(r"<script[^>]*>(.*?)</script>", rec.suggested_schema_code, re.DOTALL | re.IGNORECASE)
            raw = match.group(1).strip() if match else rec.suggested_schema_code.strip()
            parsed_json = json.loads(raw)
            assert isinstance(parsed_json, dict)
            assert "@context" in parsed_json


@pytest.mark.asyncio
async def test_engine_gracefully_handles_custom_exception(monkeypatch):
    class ExplodingProvider:
        async def generate_aeo_recommendations(self, *args, **kwargs):
            raise RuntimeError("Simulated remote provider connection crash")

    monkeypatch.setattr(AEOCopilotEngine, "get_provider", lambda: ExplodingProvider())

    page = HTMLParserService.parse_html("https://example.com", 200, SAMPLE_HTML, {}, 0.1)
    # Must not raise RuntimeError, must fall back to MockLLMProvider
    result = await AEOCopilotEngine.analyze_page(page, [])
    assert isinstance(result, AEOCopilotResult)
    assert len(result.key_recommendations) > 0

