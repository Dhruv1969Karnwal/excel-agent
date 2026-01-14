"""Codebase pipeline implementation for RAG-based analysis."""

from datetime import datetime
from typing import Any, Dict, List

from ..base import AssetPipeline
from .prompts import (
    CODEBASE_PLANNING_SYSTEM_PROMPT,
    CODEBASE_PLANNING_USER_PROMPT,
    CODEBASE_CODING_SYSTEM_PROMPT,
    CODEBASE_CODING_USER_PROMPT,
)
from my_agent.tools.tools import python_repl_tool, think_tool, document_search_tool


class CodebasePipeline(AssetPipeline):
    """
    Pipeline for codebase and collection analysis via RAG.
    
    Capabilities:
    - Code exploration
    - Architectural analysis
    - Remote knowledge base search (RAG)
    """
    
    @property
    def name(self) -> str:
        return "Codebase"
    
    @property
    def supported_extensions(self) -> List[str]:
        # Codebase is strictly RAG-based and doesn't rely on local file extensions.
        return []
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "codebase_analysis",
            "remote_search",
            "rag_exploration",
            "summarization",
            "qa",
        ]
    
    async def inspect(self, identifier: str) -> Dict[str, Any]:
        """
        Initialize context for a remote knowledge base or collection.
        
        Args:
            identifier: The Knowledge Base ID (kbid)
            
        Returns:
            Structured data context for RAG mode
        """
        return {
            "kbid": identifier,
            "document_type": "Codebase/Collection (RAG)",
            "analyzed_at": datetime.now().isoformat(),
            "description": (
                f"Remote Knowledge Base / Codebase (ID: {identifier})\n"
                "- Mode: RAG (Retrieval-Augmented Generation)\n"
                "- Search Endpoint: /knowledge/search\n"
                "- Tool required: Use `document_search_tool` to query this codebase.\n"
                "- Capabilities: code_exploration, architecture_analysis, technical_qa"
            ),
            "full_text": "[Managed via document_search_tool]",
            "capabilities": ["document_search", "codebase_analysis"]
        }
    
    def get_planning_system_prompt(self) -> str:
        return CODEBASE_PLANNING_SYSTEM_PROMPT
    
    def get_planning_user_prompt(self) -> str:
        return CODEBASE_PLANNING_USER_PROMPT
    
    def get_coding_system_prompt(self) -> str:
        return CODEBASE_CODING_SYSTEM_PROMPT
    
    def get_coding_user_prompt(self) -> str:
        return CODEBASE_CODING_USER_PROMPT

    def get_tools(self) -> List[Any]:
        """Return codebase-specific tools."""
        return [document_search_tool, think_tool]
