import pytest
from app.core.analyzer import HTMLParserService, DeterministicTechnicalAnalyzer
from app.schemas.technical import SeverityEnum


SAMPLE_GOOD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Zenvora AI - Advanced Answer Engine Optimization</title>
    <meta name="description" content="Zenvora AI provides state-of-the-art AEO audit services for modern generative search platforms and answer engines.">
    <link rel="canonical" href="https://zenvora.ai/">
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "FAQPage",
      "mainEntity": [{
        "@type": "Question",
        "name": "What is AEO?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "Answer Engine Optimization (AEO) is the strategy of optimizing content for generative AI response synthesis."
        }
      }]
    }
    </script>
</head>
<body>
    <h1>Zenvora AI Website Audit</h1>
    <h2>What is Answer Engine Optimization?</h2>
    <p>""" + "AEO optimizes content so AI search tools cite your brand. " * 30 + """</p>
    <img src="/logo.png" alt="Zenvora Logo">
</body>
</html>
"""

SAMPLE_BAD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <!-- Missing title -->
    <!-- Missing meta description -->
    <!-- Missing canonical -->
</head>
<body>
    <!-- Missing H1 tag -->
    <p>Short content.</p>
    <img src="/banner.jpg"> <!-- Missing alt attribute -->
</body>
</html>
"""


def test_html_parser_good_html():
    parsed = HTMLParserService.parse_html(
        target_url="https://zenvora.ai/",
        status_code=200,
        html_text=SAMPLE_GOOD_HTML,
        headers={"content-type": "text/html"},
        fetch_time=0.25
    )

    assert parsed.metadata.title == "Zenvora AI - Advanced Answer Engine Optimization"
    assert parsed.metadata.meta_description.startswith("Zenvora AI provides")
    assert parsed.metadata.canonical_url == "https://zenvora.ai/"
    assert parsed.headings.h1_list == ["Zenvora AI Website Audit"]
    assert parsed.headings.h2_list == ["What is Answer Engine Optimization?"]
    assert len(parsed.images) == 1
    assert parsed.images[0].has_alt is True
    assert parsed.structured_data.has_schema is True
    assert "FAQPage" in parsed.structured_data.schema_types
    assert parsed.word_count > 300


def test_deterministic_analyzer_good_html():
    parsed = HTMLParserService.parse_html(
        target_url="https://zenvora.ai/",
        status_code=200,
        html_text=SAMPLE_GOOD_HTML,
        headers={"content-type": "text/html"},
        fetch_time=0.25
    )
    summary = DeterministicTechnicalAnalyzer.analyze(parsed)

    assert summary.score >= 90
    assert summary.critical_count == 0


def test_deterministic_analyzer_bad_html():
    parsed = HTMLParserService.parse_html(
        target_url="https://example.com/bad",
        status_code=200,
        html_text=SAMPLE_BAD_HTML,
        headers={"content-type": "text/html"},
        fetch_time=0.1
    )
    summary = DeterministicTechnicalAnalyzer.analyze(parsed)

    assert summary.score < 50
    assert summary.critical_count >= 3

    check_ids = [finding.check_id for finding in summary.findings]
    assert "CHECK-TITLE-01" in check_ids
    assert "CHECK-META-01" in check_ids
    assert "CHECK-H1-01" in check_ids
    assert "CHECK-SCHEMA-01" in check_ids
    assert "CHECK-ALT-01" in check_ids
    assert "CHECK-THIN-CONTENT" in check_ids
