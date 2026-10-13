import json
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from app.schemas.crawler import (
    FetchedPageContent,
    PageMetadata,
    HeadingStructure,
    ImageInfo,
    LinkInfo,
    StructuredDataInfo,
)
from app.schemas.technical import (
    TechnicalFinding,
    TechnicalAuditSummary,
    SeverityEnum,
)

logger = logging.getLogger("zenvora.analyzer")


class HTMLParserService:
    """
    Service for parsing raw HTML string into structured page representations.
    """

    @classmethod
    def parse_html(cls, target_url: str, status_code: int, html_text: str, headers: dict, fetch_time: float) -> FetchedPageContent:
        soup = BeautifulSoup(html_text, "html.parser")
        parsed_target = urlparse(target_url)
        target_domain = parsed_target.netloc.lower()

        # 1. Extract Metadata
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else None

        meta_desc = None
        desc_tag = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "description"})
        if desc_tag and desc_tag.get("content"):
            meta_desc = desc_tag.get("content").strip()

        robots_meta = None
        robots_tag = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "robots"})
        if robots_tag and robots_tag.get("content"):
            robots_meta = robots_tag.get("content").strip()

        canonical_url = None
        canonical_tag = soup.find("link", attrs={"rel": lambda x: x and x.lower() == "canonical"})
        if canonical_tag and canonical_tag.get("href"):
            canonical_url = canonical_tag.get("href").strip()

        # OpenGraph & Twitter
        opengraph = {}
        for meta in soup.find_all("meta", attrs={"property": lambda x: x and x.startswith("og:")}):
            prop = meta.get("property")
            content = meta.get("content")
            if prop and content:
                opengraph[prop] = content.strip()

        twitter_card = {}
        for meta in soup.find_all("meta", attrs={"name": lambda x: x and x.startswith("twitter:")}):
            name = meta.get("name")
            content = meta.get("content")
            if name and content:
                twitter_card[name] = content.strip()

        metadata = PageMetadata(
            title=title,
            meta_description=meta_desc,
            canonical_url=canonical_url,
            robots_meta=robots_meta,
            opengraph=opengraph,
            twitter_card=twitter_card,
        )

        # 2. Extract Headings
        h1_list = [tag.get_text(strip=True) for tag in soup.find_all("h1") if tag.get_text(strip=True)]
        h2_list = [tag.get_text(strip=True) for tag in soup.find_all("h2") if tag.get_text(strip=True)]
        h3_list = [tag.get_text(strip=True) for tag in soup.find_all("h3") if tag.get_text(strip=True)]
        h4_h6_count = len(soup.find_all(["h4", "h5", "h6"]))

        headings = HeadingStructure(
            h1_list=h1_list,
            h2_list=h2_list,
            h3_list=h3_list,
            h4_to_h6_count=h4_h6_count,
        )

        # 3. Extract Images
        images: List[ImageInfo] = []
        for img in soup.find_all("img"):
            src = img.get("src", "").strip()
            alt = img.get("alt")
            has_alt = alt is not None and len(alt.strip()) > 0
            if src:
                images.append(ImageInfo(src=src, alt=alt or "", has_alt=has_alt))

        # 4. Extract Links
        links: List[LinkInfo] = []
        for link in soup.find_all("a", href=True):
            href = link.get("href", "").strip()
            text = link.get_text(strip=True)
            rel = link.get("rel")
            rel_str = " ".join(rel) if isinstance(rel, list) else rel

            parsed_href = urlparse(href)
            is_internal = False
            is_external = False

            if not parsed_href.netloc or parsed_href.netloc.lower() == target_domain:
                is_internal = True
            elif parsed_href.scheme in ("http", "https"):
                is_external = True

            links.append(LinkInfo(
                href=href,
                text=text,
                is_internal=is_internal,
                is_external=is_external,
                rel=rel_str,
            ))

        # 5. Extract Text Content & Word Count
        # Remove script, style, nav, footer tags for accurate body word count
        soup_copy = BeautifulSoup(html_text, "html.parser")
        for element in soup_copy(["script", "style", "nav", "footer", "header", "noscript"]):
            element.decompose()

        text_content = soup_copy.get_text(separator=" ", strip=True)
        words = text_content.split()
        word_count = len(words)

        # 6. Extract JSON-LD Structured Data
        schema_types = []
        raw_schemas = []
        has_schema = False

        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                if script.string:
                    data = json.loads(script.string)
                    if isinstance(data, dict):
                        raw_schemas.append(data)
                        stype = data.get("@type")
                        if stype:
                            if isinstance(stype, list):
                                schema_types.extend(stype)
                            else:
                                schema_types.append(str(stype))
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                raw_schemas.append(item)
                                stype = item.get("@type")
                                if stype:
                                    if isinstance(stype, list):
                                        schema_types.extend(stype)
                                    else:
                                        schema_types.append(str(stype))
            except json.JSONDecodeError:
                logger.warning("Failed to parse a JSON-LD script block.")

        schema_types = list(set(schema_types))
        has_schema = len(raw_schemas) > 0

        structured_data = StructuredDataInfo(
            has_schema=has_schema,
            schema_types=schema_types,
            raw_schemas=raw_schemas,
        )

        return FetchedPageContent(
            url=target_url,
            status_code=status_code,
            headers=headers,
            fetch_time_seconds=fetch_time,
            text_content=text_content,
            word_count=word_count,
            metadata=metadata,
            headings=headings,
            images=images,
            links=links,
            structured_data=structured_data,
        )


class DeterministicTechnicalAnalyzer:
    """
    Rule engine performing deterministic technical SEO and AEO checks.
    """

    @classmethod
    def analyze(cls, page: FetchedPageContent) -> TechnicalAuditSummary:
        findings: List[TechnicalFinding] = []
        total_checks = 10
        passed_checks = 0

        # Check 1: Page Title Presence & Length
        if not page.metadata.title:
            findings.append(TechnicalFinding(
                check_id="CHECK-TITLE-01",
                category="SEO",
                title="Missing Page Title Tag",
                description="The page is missing a <title> element, which is essential for search engines and answer engines.",
                severity=SeverityEnum.CRITICAL,
                evidence="<title> tag is absent in the document head.",
                suggested_fix="Add a unique, descriptive <title> tag between 30 and 60 characters long."
            ))
        elif len(page.metadata.title) < 30 or len(page.metadata.title) > 60:
            findings.append(TechnicalFinding(
                check_id="CHECK-TITLE-02",
                category="SEO",
                title="Sub-optimal Title Length",
                description=f"Title length is {len(page.metadata.title)} characters. Ideal length is 30–60 characters.",
                severity=SeverityEnum.WARNING,
                evidence=f"Current title: '{page.metadata.title}'",
                suggested_fix="Adjust title length to be between 30 and 60 characters to avoid truncation."
            ))
        else:
            passed_checks += 1

        # Check 2: Meta Description Presence & Length
        if not page.metadata.meta_description:
            findings.append(TechnicalFinding(
                check_id="CHECK-META-01",
                category="SEO",
                title="Missing Meta Description",
                description="No meta description found. Search engines and AI summaries rely on this snippet.",
                severity=SeverityEnum.CRITICAL,
                evidence="<meta name='description'> tag is missing.",
                suggested_fix="Add a concise meta description summarizing page value in 120–160 characters."
            ))
        elif len(page.metadata.meta_description) < 120 or len(page.metadata.meta_description) > 160:
            findings.append(TechnicalFinding(
                check_id="CHECK-META-02",
                category="SEO",
                title="Sub-optimal Meta Description Length",
                description=f"Meta description is {len(page.metadata.meta_description)} characters. Ideal is 120–160 chars.",
                severity=SeverityEnum.WARNING,
                evidence=f"Current meta description: '{page.metadata.meta_description}'",
                suggested_fix="Revise meta description to be between 120 and 160 characters."
            ))
        else:
            passed_checks += 1

        # Check 3: H1 Heading Structure
        if len(page.headings.h1_list) == 0:
            findings.append(TechnicalFinding(
                check_id="CHECK-H1-01",
                category="SEO & AEO",
                title="Missing H1 Heading",
                description="The page has no <h1> heading tag. AI engines use H1 to establish primary topic entity.",
                severity=SeverityEnum.CRITICAL,
                evidence="No <h1> tag detected in HTML.",
                suggested_fix="Include exactly one main <h1> heading at the top of main content."
            ))
        elif len(page.headings.h1_list) > 1:
            findings.append(TechnicalFinding(
                check_id="CHECK-H1-02",
                category="SEO & AEO",
                title="Multiple H1 Headings Detected",
                description=f"Page contains {len(page.headings.h1_list)} <h1> tags, which can dilute topic focus.",
                severity=SeverityEnum.WARNING,
                evidence=f"H1 tags found: {page.headings.h1_list}",
                suggested_fix="Consolidate to a single <h1> heading and use <h2>/<h3> for sub-sections."
            ))
        else:
            passed_checks += 1

        # Check 4: Image Alt Attributes
        missing_alt_images = [img.src for img in page.images if not img.has_alt]
        if missing_alt_images:
            findings.append(TechnicalFinding(
                check_id="CHECK-ALT-01",
                category="Accessibility & AEO",
                title="Images Missing Alt Text",
                description=f"{len(missing_alt_images)} out of {len(page.images)} images lack descriptive alt text.",
                severity=SeverityEnum.WARNING,
                evidence=f"Images without alt text: {missing_alt_images[:3]}",
                suggested_fix="Add descriptive alt attributes to all content-bearing <img> elements."
            ))
        else:
            passed_checks += 1

        # Check 5: Canonical Link Tag
        if not page.metadata.canonical_url:
            findings.append(TechnicalFinding(
                check_id="CHECK-CANONICAL-01",
                category="Indexability",
                title="Missing Canonical URL Tag",
                description="No rel='canonical' tag found, increasing risk of duplicate content issues.",
                severity=SeverityEnum.WARNING,
                evidence="<link rel='canonical'> is missing.",
                suggested_fix="Add a canonical tag pointing to the authoritative URL of this page."
            ))
        else:
            passed_checks += 1

        # Check 6: Robots Meta Restrictions
        if page.metadata.robots_meta and "noindex" in page.metadata.robots_meta.lower():
            findings.append(TechnicalFinding(
                check_id="CHECK-ROBOTS-01",
                category="Indexability",
                title="Page Has 'noindex' Meta Tag",
                description="The page explicitly instructs search engines not to index its content.",
                severity=SeverityEnum.CRITICAL,
                evidence=f"Meta robots tag: '{page.metadata.robots_meta}'",
                suggested_fix="Remove 'noindex' from the robots meta tag if this page is intended for public discovery."
            ))
        else:
            passed_checks += 1

        # Check 7: Schema.org Structured Data (Core AEO)
        if not page.structured_data.has_schema:
            findings.append(TechnicalFinding(
                check_id="CHECK-SCHEMA-01",
                category="AEO",
                title="Missing Schema.org Structured Data",
                description="No JSON-LD structured data detected. Structured data is vital for AI Answer Engine rich snippets.",
                severity=SeverityEnum.CRITICAL,
                evidence="No <script type='application/ld+json'> blocks found.",
                suggested_fix="Implement JSON-LD schemas such as WebPage, Article, Organization, or FAQPage."
            ))
        else:
            passed_checks += 1

        # Check 8: AEO Specific Schema Types (FAQPage / Article / Product)
        aeo_recommended_types = {"FAQPage", "Article", "NewsArticle", "TechArticle", "Product", "Organization", "HowTo"}
        present_types = set(page.structured_data.schema_types)
        matched_aeo_types = present_types.intersection(aeo_recommended_types)
        if page.structured_data.has_schema and not matched_aeo_types:
            findings.append(TechnicalFinding(
                check_id="CHECK-SCHEMA-02",
                category="AEO",
                title="Lacks High-Value AEO Schema Types",
                description=f"Structured data present ({list(present_types)}), but lacks direct answer schemas like FAQPage, Article, or Organization.",
                severity=SeverityEnum.WARNING,
                evidence=f"Detected types: {list(present_types)}",
                suggested_fix="Add FAQPage, Article, or HowTo schema to help answer engines digest Q&A content."
            ))
        elif page.structured_data.has_schema:
            passed_checks += 1

        # Check 9: Thin Content Check (< 300 words)
        if page.word_count < 300:
            findings.append(TechnicalFinding(
                check_id="CHECK-THIN-CONTENT",
                category="Content & AEO",
                title="Thin Content Detected",
                description=f"Body word count is only {page.word_count} words. Answer engines favor authoritative, comprehensive content.",
                severity=SeverityEnum.WARNING,
                evidence=f"Extracted word count: {page.word_count} words.",
                suggested_fix="Expand main body content to at least 500+ words with structured Q&A sections."
            ))
        else:
            passed_checks += 1

        # Check 10: Sub-heading Structure (H2 / H3)
        if len(page.headings.h2_list) == 0:
            findings.append(TechnicalFinding(
                check_id="CHECK-HEADING-H2",
                category="AEO & Readability",
                title="Missing H2 Section Headings",
                description="No <h2> headings found. Section headings help AI engines extract discrete answers.",
                severity=SeverityEnum.WARNING,
                evidence="Zero <h2> tags found.",
                suggested_fix="Structure main content with clear <h2> subheadings representing question topics."
            ))
        else:
            passed_checks += 1

        # Calculate Score out of 100
        critical_count = sum(1 for f in findings if f.severity == SeverityEnum.CRITICAL)
        warning_count = sum(1 for f in findings if f.severity == SeverityEnum.WARNING)
        info_count = sum(1 for f in findings if f.severity == SeverityEnum.INFO)

        score_deductions = (critical_count * 15) + (warning_count * 5) + (info_count * 2)
        score = max(0, 100 - score_deductions)

        return TechnicalAuditSummary(
            score=score,
            total_checks=total_checks,
            passed_checks=passed_checks,
            critical_count=critical_count,
            warning_count=warning_count,
            info_count=info_count,
            findings=findings,
        )
