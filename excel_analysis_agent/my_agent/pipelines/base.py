"""Base pipeline interface for all asset types."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class AssetPipeline(ABC):
    """
    Abstract base class for asset-specific processing pipelines.
    
    All asset pipelines (Excel, Document, PowerPoint, etc.) must implement
    this interface to ensure consistent behavior across the system.
    
    Each pipeline provides:
    - File inspection and metadata extraction
    - Asset-specific prompts for planning and coding agents
    - Capability information for the router
    
    The core workflow (router → supervisor → planning → coding) remains
    the same across all pipelines - only the inspection and prompts differ.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Human-readable name for this pipeline.
        
        Returns:
            Pipeline name, e.g., 'Excel', 'Document', 'PowerPoint'
        """
        pass
    
    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """
        List of file extensions this pipeline can handle.
        
        Returns:
            List of extensions without leading dot, lowercase.
            Example: ['xlsx', 'xls', 'csv']
        """
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> List[str]:
        """
        List of analysis capabilities this pipeline supports.
        
        Used by router and planning nodes to understand what
        operations are possible with this asset type.
        
        Returns:
            List of capability strings.
            Example: ['statistical_analysis', 'visualization', 'machine_learning']
        """
        pass
    
    @abstractmethod
    async def inspect(self, file_path: str) -> Dict[str, Any]:
        """
        Inspect the file and extract structured metadata/context.
        
        This is called once when a file is first loaded to understand
        its structure, content, and capabilities.
        
        Args:
            file_path: Absolute path to the file
            
        Returns:
            Dictionary containing:
                - file_path: Absolute path to the file
                - file_name: Name of the file
                - analyzed_at: ISO timestamp
                - description: Human-readable description
                - summary: Structured summary (varies by asset type)
                - capabilities: What analyses are possible
        """
        pass
    
    @abstractmethod
    def get_planning_system_prompt(self) -> str:
        """
        Return the system prompt for the planning node.
        
        This prompt guides the LLM to create appropriate analysis
        plans based on the asset type's capabilities.
        """
        pass
    
    @abstractmethod
    def get_planning_user_prompt(self) -> str:
        """
        Return the user prompt template for the planning node.
        
        Template should include placeholders for:
        - {user_query}: The user's analysis request
        - {data_context}: The inspected file context
        """
        pass
    
    @abstractmethod
    def get_coding_system_prompt(self) -> str:
        """
        Return the system prompt for the coding agent.
        
        This prompt guides the coding agent on how to analyze
        this specific asset type.
        """
        pass
    
    @abstractmethod
    def get_coding_user_prompt(self) -> str:
        """
        Return the user prompt template for the coding agent.
        
        Template should include placeholders for:
        - {analysis_plan}: The plan from planning node
        - {data_context}: The inspected file context
        - {file_path}: Path to the file
        - {plots_dir}: Directory for saving plots
        """
        pass
    
    @abstractmethod
    def get_tools(self) -> List[Any]:
        """
        Return the list of tools available for this pipeline's specialist.
        """
        pass
    
    def can_handle(self, file_path: str) -> bool:
        """
        Check if this pipeline can handle the given file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if this pipeline supports the file type
        """
        import os
        ext = os.path.splitext(file_path)[1].lower().lstrip('.')
        return ext in [e.lower() for e in self.supported_extensions]
    
    def get_router_context(self) -> str:
        """
        Return context about this pipeline for the router.
        
        Used to help the router understand what this pipeline
        can and cannot do.
        """
        return f"""
Asset Type: {self.name}
Supported Extensions: {', '.join(self.supported_extensions)}
Capabilities: {', '.join(self.capabilities)}
"""
