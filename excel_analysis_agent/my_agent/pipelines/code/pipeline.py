"""Source code pipeline implementation."""

from typing import Any, Dict, List

from ..base import AssetPipeline
from .inspector import inspect_code
from .prompts import (
    CODE_PLANNING_SYSTEM_PROMPT,
    CODE_PLANNING_USER_PROMPT,
    CODE_CODING_SYSTEM_PROMPT,
    CODE_CODING_USER_PROMPT,
)

class CodePipeline(AssetPipeline):
    """
    Pipeline for analyzing individual source code files.
    
    Supports: .py, .js, .ts, .java, .cpp, .c, .cs, .go, .rb, .php, .rs, .sql, .sh, .html, .css
    
    Capabilities:
    - Code logic analysis
    - Bug detection
    - Refactoring suggestions
    - Architectural overview (single file)
    - Code explanation
    """
    
    @property
    def name(self) -> str:
        return "Code"
    
    @property
    def supported_extensions(self) -> List[str]:
        return [
            "py", "js", "ts", "java", "cpp", "c", "cs", 
            "go", "rb", "php", "rs", "sql", "sh", "html", "css"
        ]
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "code_analysis",
            "debugging",
            "refactoring",
            "logic_extraction",
            "code_explanation",
            "syntax_verification",
        ]
    
    async def inspect(self, file_path: str) -> Dict[str, Any]:
        """
        Inspect code file and extract content/metadata.
        
        Args:
            file_path: Path to code file
            
        Returns:
            Structured data context for analysis
        """
        return await inspect_code(file_path)
    
    def get_planning_system_prompt(self) -> str:
        """Return code-specific planning system prompt."""
        return CODE_PLANNING_SYSTEM_PROMPT
    
    def get_planning_user_prompt(self) -> str:
        """Return code-specific planning user prompt template."""
        return CODE_PLANNING_USER_PROMPT
    
    def get_coding_system_prompt(self) -> str:
        """Return code-specific coding agent system prompt."""
        return CODE_CODING_SYSTEM_PROMPT
    
    def get_coding_user_prompt(self) -> str:
        """Return code-specific coding agent user prompt template."""
    
    def get_tools(self) -> List[Any]:
        """Return code-specific tools."""
        # Only python_repl_tool for code analysis/testing
        # No think_tool needed - full source code is already in context
        return []
        return CODE_CODING_USER_PROMPT
