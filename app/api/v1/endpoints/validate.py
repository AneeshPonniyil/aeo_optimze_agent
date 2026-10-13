from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from app.core.security import SSRFSecurityValidator, URLValidationError

router = APIRouter()


class URLValidateRequest(BaseModel):
    url: str = Field(..., json_schema_extra={"example": "https://example.com"}, description="Public website URL to validate")


class URLValidateResponse(BaseModel):
    is_valid: bool
    normalized_url: str
    message: str


@router.post("/validate-url", response_model=URLValidateResponse, summary="Validate URL for SSRF Safety")
async def validate_url(payload: URLValidateRequest):
    """
    Validate target website URL against SSRF rules, IP blacklists, and scheme restrictions.
    """
    try:
        normalized = await SSRFSecurityValidator.validate_and_normalize_url(payload.url)
        return URLValidateResponse(
            is_valid=True,
            normalized_url=normalized,
            message="URL is valid and safe for auditing."
        )
    except URLValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
