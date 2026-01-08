from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, validator

class Asset(BaseModel):
    """
    Standardized Asset Schema.
    type: The specific pipeline type (excel, codebase, document, powerpoint, image).
    identifier: The path or ID. We support path and kbid as explicit fields, 
               but also allow 'identifier' as a generic fallback if needed.
    """
    type: str = Field(..., description="Type of the asset (excel, codebase, document, powerpoint, image)")
    path: Optional[str] = Field(None, description="Absolute file path for local assets")
    kbid: Optional[str] = Field(None, description="Knowledge Base ID for RAG assets")
    name: Optional[str] = Field(None, description="Human readable name for the asset")
    
    # Allow extra fields for flexibility without breaking
    class Config:
        extra = "ignore"

class ChatRequest(BaseModel):
    query: str
    attachments: List[Asset] = Field(default_factory=list)
    context_message: Optional[str] = None
    history: List[Dict[str, Any]] = Field(default_factory=list)
