from typing import List
from app.core.llm.base import LLMProvider
from app.schemas.crawler import FetchedPageContent
from app.schemas.technical import TechnicalFinding
from app.schemas.aeo import AEOCopilotResult, AEOSuggestion


class MockLLMProvider(LLMProvider):
    """
    Mock LLM provider generating grounded, schema-validated AEO recommendations
    without requiring external paid API keys. Perfect for testing and offline environments.
    """

    async def generate_aeo_recommendations(
        self,
        page_content: FetchedPageContent,
        technical_findings: List[TechnicalFinding],
    ) -> AEOCopilotResult:
        title_str = page_content.metadata.title or "Target Web Page"
        domain = page_content.url

        # Compute Grounded Entity Clarity & Answer Readiness Scores
        entity_score = 85 if page_content.metadata.title and len(page_content.headings.h1_list) == 1 else 55
        if page_content.structured_data.has_schema:
            entity_score = min(100, entity_score + 15)

        answer_score = 90 if page_content.word_count > 300 and len(page_content.headings.h2_list) >= 2 else 50

        # Build Grounded Recommendations
        recommendations: List[AEOSuggestion] = []

        # 1. Structured Data Recommendation
        if not page_content.structured_data.has_schema or "FAQPage" not in page_content.structured_data.schema_types:
            recommendations.append(
                AEOSuggestion(
                    check_id="AEO-SCHEMA-FAQ",
                    category="Structured Data",
                    title="Implement FAQPage JSON-LD Schema",
                    current_state_evidence=f"Page currently has schema types: {page_content.structured_data.schema_types or 'None'}.",
                    suggested_aeo_content="Add FAQPage schema to directly feed conversational search engines like Perplexity, ChatGPT Search, and Google Gemini.",
                    suggested_schema_code='''<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [{
    "@type": "Question",
    "name": "What services does ''' + title_str + ''' provide?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "''' + title_str + ''' provides AI-driven website auditing and Answer Engine Optimization (AEO) analysis."
    }
  }]
}
</script>''',
                    confidence_score=0.95,
                    limitations="Based on current missing schema analysis. Code should be verified against target business Q&As."
                )
            )

        # 2. Section Sub-heading Q&A Optimization
        if len(page_content.headings.h2_list) < 2:
            recommendations.append(
                AEOSuggestion(
                    check_id="AEO-STRUCTURE-QA",
                    category="Content Structure",
                    title="Format Sub-headings as Direct Questions",
                    current_state_evidence=f"Page has {len(page_content.headings.h2_list)} H2 sub-headings.",
                    suggested_aeo_content="Transform generic <h2> titles into explicit question queries (e.g. 'How does X work?') followed by a concise 40-word direct answer paragraph.",
                    suggested_schema_code=None,
                    confidence_score=0.90,
                    limitations="Requires editorial content rewrite to match target user query intent."
                )
            )

        # 3. Entity Definition Paragraph
        recommendations.append(
            AEOSuggestion(
                check_id="AEO-ENTITY-DEF",
                category="Entity Optimization",
                title="Add Concise Definition Sentence in Lead Paragraph",
                current_state_evidence=f"Analyzed lead content for page '{title_str}'.",
                suggested_aeo_content=f"Ensure the first 100 words explicitly define '{title_str}' using declarative is-a syntax for generative extraction.",
                suggested_schema_code=None,
                confidence_score=0.88,
                limitations="Grounded solely on visible extracted body text."
            )
        )

        # Grounded FAQ Opportunities
        faq_opportunities = [
            {
                "question": f"What is the main purpose of {title_str}?",
                "answer": f"{title_str} offers structured information on {page_content.headings.h1_list[0] if page_content.headings.h1_list else 'the target domain'}, designed for fast retrieval by search engines and generative AI tools."
            },
            {
                "question": f"How is content structured on {domain}?",
                "answer": f"The page includes {page_content.word_count} words of body content across {len(page_content.headings.h2_list)} sub-sections with {len(page_content.images)} visual assets."
            }
        ]

        # Grounded Schema Code Block
        suggested_schema = {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": title_str,
            "url": page_content.url,
            "description": page_content.metadata.meta_description or f"AEO Audited page for {title_str}",
            "publisher": {
                "@type": "Organization",
                "name": title_str,
                "url": page_content.url
            }
        }

        return AEOCopilotResult(
            summary=f"AEO Analysis for '{title_str}': Entity clarity score is {entity_score}/100 and answer readiness score is {answer_score}/100. Incorporating structured FAQPage schemas and Q&A subheadings will significantly boost AI answer engine citations.",
            entity_clarity_score=entity_score,
            answer_readiness_score=answer_score,
            key_recommendations=recommendations,
            faq_opportunities=faq_opportunities,
            suggested_json_ld_schema=suggested_schema,
        )
