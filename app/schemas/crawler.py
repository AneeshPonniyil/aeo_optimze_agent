from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class HeadingStructure(BaseModel):
    h1_list: List[str] = Field(default_factory=list)
    h2_list: List[str] = Field(default_factory=list)
    h3_list: List[str] = Field(default_factory=list)
    h4_to_h6_count: int = 0


class ImageInfo(BaseModel):
    src: str
    alt: str
    has_alt: bool


class LinkInfo(BaseModel):
    href: str
    text: str
    is_internal: bool
    is_external: bool
    rel: Optional[str] = None


class PageMetadata(BaseModel):
    title: Optional[str] = None
    meta_description: Optional[str] = None
    canonical_url: Optional[str] = None
    robots_meta: Optional[str] = None
    opengraph: Dict[str, str] = Field(default_factory=dict)
    twitter_card: Dict[str, str] = Field(default_factory=dict)


class StructuredDataInfo(BaseModel):
    has_schema: bool = False
    schema_types: List[str] = Field(default_factory=list)
    raw_schemas: List[Dict[str, Any]] = Field(default_factory=list)


class FetchedPageContent(BaseModel):
    url: str
    status_code: int
    headers: Dict[str, str] = Field(default_factory=dict)
    fetch_time_seconds: float
    text_content: str
    word_count: int
    metadata: PageMetadata
    headings: HeadingStructure
    images: List[ImageInfo] = Field(default_factory=list)
    links: List[LinkInfo] = Field(default_factory=list)
    structured_data: StructuredDataInfo
