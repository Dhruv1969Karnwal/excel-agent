"""Excel-specific pipeline implementation."""

from typing import Any, Dict, List

from ..base import AssetPipeline
from .inspector import inspect_excel_file
from .prompts import (
    EXCEL_PLANNING_SYSTEM_PROMPT,
    EXCEL_PLANNING_USER_PROMPT,
    EXCEL_CODING_SYSTEM_PROMPT,
    EXCEL_CODING_USER_PROMPT,
)
from my_agent.tools.tools import python_repl_tool, think_tool, bash_tool

def complete_step_placeholder():
    # This is a placeholder as complete_step is defined locally in coding_agent_node
    # We will handle this in the coding_agent_node by injecting it.
    pass

class ExcelPipeline(AssetPipeline):
    """
    Pipeline for Excel file analysis.
    
    Supports: .xlsx, .xls, .csv
    
    Capabilities:
    - Data inspection and profiling
    - Statistical analysis
    - Visualizations (matplotlib, seaborn)
    - Machine learning (scikit-learn)
    - Code execution via sandbox
    
    Uses the existing coding subgraph for code execution,
    maintaining full compatibility with the current system.
    """
    
    @property
    def name(self) -> str:
        return "Excel"
    
    @property
    def supported_extensions(self) -> List[str]:
        return ["xlsx", "xls", "csv"]
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "statistical_analysis",
            "visualization",
            "machine_learning",
            "data_transformation",
            "correlation_analysis",
            "trend_analysis",
            "code_execution",
        ]
    
    async def inspect(self, file_path: str) -> Dict[str, Any]:
        """
        Inspect Excel file and extract metadata.
        
        Uses pandas to analyze:
        - Row/column counts
        - Column types
        - Missing values
        - Sample data
        - Numeric statistics
        
        Args:
            file_path: Path to Excel/CSV file
            
        Returns:
            Structured data context for the agent
        """
        return await inspect_excel_file(file_path)
    
    def get_planning_system_prompt(self) -> str:
        """Return Excel-specific planning system prompt."""
        return EXCEL_PLANNING_SYSTEM_PROMPT
    
    def get_planning_user_prompt(self) -> str:
        """Return Excel-specific planning user prompt template."""
        return EXCEL_PLANNING_USER_PROMPT
    
    def get_coding_system_prompt(self) -> str:
        """Return Excel-specific coding agent system prompt."""
        return EXCEL_CODING_SYSTEM_PROMPT
    
    def get_coding_user_prompt(self) -> str:
        """Return Excel-specific coding agent user prompt template."""
        return EXCEL_CODING_USER_PROMPT

    def get_tools(self) -> List[Any]:
        """Return Excel-specific tools."""
        return [python_repl_tool, think_tool, bash_tool]
