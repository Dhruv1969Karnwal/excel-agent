"""PowerPoint-specific pipeline implementation."""

from typing import Any, Dict, List

from ..base import AssetPipeline
from .inspector import inspect_presentation
from .prompts import (
    PPTX_PLANNING_SYSTEM_PROMPT,
    PPTX_PLANNING_USER_PROMPT,
    PPTX_CODING_SYSTEM_PROMPT,
    PPTX_CODING_USER_PROMPT,
)


class PowerPointPipeline(AssetPipeline):
    """
    Pipeline for PowerPoint presentation analysis.
    
    Supports: .pptx, .ppt
    
    Capabilities:
    - Slide content extraction
    - Speaker notes extraction
    - Image/chart/table detection
    - Presentation summarization
    - Slide-specific queries
    
    Uses full-context approach: all slides are passed to the LLM.
    
    Uses the same core workflow as Excel:
    - Router → Supervisor → Planning → Coding Agent
    - Maintains follow-up conversation support
    - Uses sandbox for code execution (text processing)
    """
    
    @property
    def name(self) -> str:
        return "PowerPoint"
    
    @property
    def supported_extensions(self) -> List[str]:
        return ["pptx", "ppt"]
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "slide_extraction",
            "notes_extraction",
            "summarization",
            "content_search",
            "presentation_analysis",
            "code_execution",
        ]
    
    async def inspect(self, file_path: str) -> Dict[str, Any]:
        """
        Inspect PowerPoint file and extract all slide content.
        
        Extracts:
        - Slide titles and content
        - Speaker notes
        - Image/chart/table indicators
        - Full text for LLM context
        
        Args:
            file_path: Path to .pptx file
            
        Returns:
            Structured data context including all slides
        """
        return await inspect_presentation(file_path)
    
    def get_planning_system_prompt(self) -> str:
        """Return PowerPoint-specific planning system prompt."""
        return PPTX_PLANNING_SYSTEM_PROMPT
    
    def get_planning_user_prompt(self) -> str:
        """Return PowerPoint-specific planning user prompt template."""
        return PPTX_PLANNING_USER_PROMPT
    
    def get_coding_system_prompt(self) -> str:
        """Return PowerPoint-specific coding agent system prompt."""
        return PPTX_CODING_SYSTEM_PROMPT
    
    def get_coding_user_prompt(self) -> str:
        """Return PowerPoint-specific coding agent user prompt template."""
        return PPTX_CODING_USER_PROMPT
