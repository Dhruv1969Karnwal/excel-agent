"""Document-specific pipeline implementation."""

from typing import Any, Dict, List

from ..base import AssetPipeline
from .inspector import inspect_document
from .prompts import (
    DOCUMENT_PLANNING_SYSTEM_PROMPT,
    DOCUMENT_PLANNING_USER_PROMPT,
    DOCUMENT_CODING_SYSTEM_PROMPT,
    DOCUMENT_CODING_USER_PROMPT,
)
from my_agent.tools.tools import python_repl_tool, think_tool


class DocumentPipeline(AssetPipeline):
    """
    Pipeline for document analysis (Word, PDF, text files).
    
    Supports: .docx, .doc, .pdf, .txt, .md
    
    Capabilities:
    - Text extraction
    - Section/heading detection
    - Table extraction (from Word docs)
    - Summarization
    - Question answering
    - Information extraction
    
    Uses full-context approach: the entire document is passed
    to the LLM for analysis.
    
    Uses the same core workflow as Excel:
    - Router → Supervisor → Planning → Coding Agent
    - Maintains follow-up conversation support
    - Uses sandbox for code execution (text processing)
    """
    
    @property
    def name(self) -> str:
        return "Document"
    
    @property
    def supported_extensions(self) -> List[str]:
        return ["docx", "doc", "pdf", "txt", "md"]
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "text_extraction",
            "summarization",
            "question_answering",
            "information_extraction",
            "content_analysis",
            "code_execution",
        ]
    
    async def inspect(self, file_path: str) -> Dict[str, Any]:
        """
        Inspect document file and extract full text content.
        
        Extracts:
        - Full document text
        - Headings/structure
        - Tables (from Word docs)
        - Word count and metadata
        
        Args:
            file_path: Path to document file
            
        Returns:
            Structured data context including full text
        """
        return await inspect_document(file_path)
    
    def get_planning_system_prompt(self) -> str:
        """Return document-specific planning system prompt."""
        return DOCUMENT_PLANNING_SYSTEM_PROMPT
    
    def get_planning_user_prompt(self) -> str:
        """Return document-specific planning user prompt template."""
        return DOCUMENT_PLANNING_USER_PROMPT
    
    def get_coding_system_prompt(self) -> str:
        """Return document-specific coding agent system prompt."""
        return DOCUMENT_CODING_SYSTEM_PROMPT
    
    def get_coding_user_prompt(self) -> str:
        """Return document-specific coding agent user prompt template."""
        return DOCUMENT_CODING_USER_PROMPT

    def get_tools(self) -> List[Any]:
        """Return document-specific tools."""
        # Only python_repl_tool for computational text processing
        # No think_tool needed - full document text is already in context
        return []