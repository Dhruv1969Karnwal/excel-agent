"""Asset Dispatcher Node - Routes to correct pipeline based on file type."""

import os
from typing import Any, Dict

from langchain_core.messages import AIMessage

from my_agent.models.state import UnifiedAnalysisState
from my_agent.pipelines.registry import registry


async def asset_dispatcher_node(state: UnifiedAnalysisState) -> Dict[str, Any]:
    """
    Dispatch to the correct asset pipeline based on file type.
    
    This node replaces the old data_inspector_node with unified pipeline support.
    It:
    1. Gets the file path from state (either file_path or excel_file_path)
    2. Checks if context already exists for this file (skip re-inspection)
    3. Determines asset type from extension
    4. Gets the appropriate pipeline from registry
    5. Calls the pipeline's inspect method
    6. Updates state with context and asset type
    
    Maintains backward compatibility with excel_file_path for existing code.
    
    Args:
        state: Current state containing file path and optional existing context
        
    Returns:
        Dictionary with data_context, asset_type, and messages updates
    """
    # Support both new file_path and legacy excel_file_path
    file_path = state.get("file_path") or state.get("excel_file_path")
    existing_context = state.get("data_context")
    
    if not file_path:
        return {
            "data_context": {"error": "No file path provided"},
            "messages": [AIMessage(
                content="Please provide a file path to analyze. I support Excel (.xlsx, .xls, .csv), "
                        "Documents (.docx, .pdf, .txt, .md), and PowerPoint (.pptx) files.",
                name="AssetDispatcher"
            )]
        }
    
    # Resolve absolute path
    abs_file_path = os.path.abspath(file_path)
    
    # Check if we already have context for this exact file (context caching)
    if existing_context and isinstance(existing_context, dict):
        stored_path = existing_context.get("file_path", "")
        if stored_path == abs_file_path:
            print(f"✅ Using existing context for: {file_path}")
            # Return empty dict - no state update needed, context already exists
            return {}
    
    # Check if file type is supported
    if not registry.is_supported(file_path):
        supported = ", ".join(f".{ext}" for ext in registry.supported_extensions)
        error_msg = (
            f"Unsupported file type: {os.path.splitext(file_path)[1]}. "
            f"Supported types: {supported}"
        )
        return {
            "data_context": {"error": error_msg},
            "messages": [AIMessage(
                content=error_msg,
                name="AssetDispatcher"
            )]
        }
    
    try:
        # Get pipeline from registry
        pipeline = registry.get_pipeline_for_file(file_path)
        asset_type = pipeline.name.lower()
        
        print(f"📂 Dispatching to {pipeline.name} pipeline for: {file_path}")
        
        # Inspect the file using the pipeline
        data_context = await pipeline.inspect(file_path)
        
        # Prepare result
        result = {
            "asset_type": asset_type,
            "data_context": data_context,
            "file_path": abs_file_path,  # Store normalized path
            "messages": [AIMessage(
                content=f"File inspection complete. Detected asset type: {pipeline.name}. "
                        f"File: {data_context.get('file_name', file_path)}",
                name="AssetDispatcher"
            )]
        }
        
        # Backward compatibility: also set excel_file_path for Excel files
        if asset_type == "excel":
            result["excel_file_path"] = abs_file_path
        
        print(f"✅ {pipeline.name} inspection complete for: {file_path}")
        
        return result
        
    except ImportError as e:
        # Missing library for this file type
        error_msg = str(e)
        print(f"❌ Import error: {error_msg}")
        return {
            "data_context": {"error": error_msg},
            "messages": [AIMessage(
                content=f"Missing required library: {error_msg}",
                name="AssetDispatcher"
            )]
        }
    except ValueError as e:
        # Unsupported file type or other value error
        error_msg = str(e)
        print(f"❌ Value error: {error_msg}")
        return {
            "data_context": {"error": error_msg},
            "messages": [AIMessage(
                content=error_msg,
                name="AssetDispatcher"
            )]
        }
    except Exception as e:
        # General error during inspection
        error_msg = f"Error inspecting file: {str(e)}"
        print(f"❌ {error_msg}")
        return {
            "data_context": {"error": error_msg},
            "messages": [AIMessage(
                content=error_msg,
                name="AssetDispatcher"
            )]
        }
