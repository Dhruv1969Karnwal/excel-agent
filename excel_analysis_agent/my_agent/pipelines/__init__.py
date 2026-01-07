"""
Pipelines module for multi-asset analysis support.

This module provides:
- AssetPipeline: Abstract base class for all asset-specific pipelines
- PipelineRegistry: Singleton registry for dynamic pipeline resolution
- Concrete pipelines: ExcelPipeline, DocumentPipeline, PowerPointPipeline
"""

from .base import AssetPipeline
from .registry import PipelineRegistry, registry

__all__ = [
    "AssetPipeline",
    "PipelineRegistry", 
    "registry",
]
