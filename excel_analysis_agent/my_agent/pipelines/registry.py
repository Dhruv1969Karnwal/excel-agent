"""Pipeline registry for dynamic asset type resolution."""

import os
from typing import Dict, List, Optional

from .base import AssetPipeline


class PipelineRegistry:
    """
    Singleton registry for asset pipelines.
    
    Enables dynamic pipeline registration and lookup by file extension.
    New asset types can be added by simply registering their pipeline.
    
    Usage:
        # Register a pipeline
        registry = PipelineRegistry()
        registry.register(ExcelPipeline())
        
        # Get pipeline for a file
        pipeline = registry.get_pipeline_for_file("data.xlsx")
        
        # Check if file type is supported
        if registry.is_supported("report.docx"):
            ...
    """
    
    _instance: Optional["PipelineRegistry"] = None
    _pipelines: Dict[str, AssetPipeline]
    _initialized: bool = False
    
    def __new__(cls) -> "PipelineRegistry":
        """Singleton pattern - return existing instance if available."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._pipelines = {}
            cls._instance._initialized = False
        return cls._instance
    
    def register(self, pipeline: AssetPipeline) -> None:
        """
        Register a pipeline for its supported extensions.
        
        Args:
            pipeline: An instance of AssetPipeline
        """
        for ext in pipeline.supported_extensions:
            ext_lower = ext.lower().lstrip('.')
            self._pipelines[ext_lower] = pipeline
            print(f"✅ Registered {pipeline.name} pipeline for .{ext_lower}")
    
    def unregister(self, extension: str) -> None:
        """
        Unregister a pipeline for an extension.
        
        Args:
            extension: File extension to unregister
        """
        ext_lower = extension.lower().lstrip('.')
        if ext_lower in self._pipelines:
            pipeline = self._pipelines.pop(ext_lower)
            print(f"❌ Unregistered pipeline for .{ext_lower}")
    
    def get_pipeline(self, extension: str) -> AssetPipeline:
        """
        Get the pipeline for a file extension.
        
        Args:
            extension: File extension (with or without dot)
            
        Returns:
            The registered pipeline for this extension
            
        Raises:
            ValueError: If no pipeline is registered for this extension
        """
        ext_lower = extension.lower().lstrip('.')
        if ext_lower not in self._pipelines:
            supported = ", ".join(f".{e}" for e in self._pipelines.keys())
            raise ValueError(
                f"No pipeline registered for .{ext_lower}. "
                f"Supported extensions: {supported or 'none'}"
            )
        return self._pipelines[ext_lower]
    
    def get_pipeline_for_file(self, file_path: str) -> AssetPipeline:
        """
        Get the pipeline for a file based on its extension.
        
        Args:
            file_path: Path to the file
            
        Returns:
            The registered pipeline for this file type
        """
        ext = os.path.splitext(file_path)[1]
        return self.get_pipeline(ext)
    
    def get_asset_type(self, file_path: str) -> str:
        """
        Get the asset type name for a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Asset type name in lowercase (e.g., 'excel', 'document', 'powerpoint')
        """
        pipeline = self.get_pipeline_for_file(file_path)
        return pipeline.name.lower()
    
    @property
    def supported_extensions(self) -> List[str]:
        """List all supported file extensions."""
        return list(self._pipelines.keys())
    
    @property
    def registered_pipelines(self) -> Dict[str, str]:
        """Get a mapping of extension -> pipeline name."""
        return {ext: p.name for ext, p in self._pipelines.items()}
    
    def is_supported(self, file_path: str) -> bool:
        """
        Check if a file type is supported.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if a pipeline exists for this file type
        """
        ext = os.path.splitext(file_path)[1].lower().lstrip('.')
        return ext in self._pipelines
    
    def get_all_capabilities(self) -> Dict[str, List[str]]:
        """
        Get capabilities for all registered pipelines.
        
        Returns:
            Dictionary mapping pipeline name to list of capabilities
        """
        # Get unique pipelines (avoid duplicates for multiple extensions)
        unique_pipelines = {}
        for pipeline in self._pipelines.values():
            if pipeline.name not in unique_pipelines:
                unique_pipelines[pipeline.name] = pipeline.capabilities
        return unique_pipelines
    
    def get_router_context(self) -> str:
        """
        Get combined router context for all registered pipelines.
        
        Returns:
            String describing all available pipelines and their capabilities
        """
        unique_pipelines = set(self._pipelines.values())
        contexts = [p.get_router_context() for p in unique_pipelines]
        return "\n---\n".join(contexts)
    
    def clear(self) -> None:
        """Clear all registered pipelines (useful for testing)."""
        self._pipelines.clear()
        print("🗑️ Cleared all registered pipelines")


# Global registry instance
registry = PipelineRegistry()
