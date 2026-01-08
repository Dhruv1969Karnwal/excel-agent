"""Asset Dispatcher Node - Routes to correct pipeline based on file type."""

import os
from typing import Any, Dict, List

from langchain_core.messages import AIMessage

from my_agent.models.state import UnifiedAnalysisState
from my_agent.pipelines.registry import registry


async def asset_dispatcher_node(state: UnifiedAnalysisState) -> Dict[str, Any]:
    """
    Dispatch to the correct asset pipeline based on file type for ALL attached assets.
    
    This node:
    1. Gets the list of assets from state
    2. Iterates through each asset (file_path or kbid)
    3. Checks if context already exists for each (skip re-inspection)
    4. Determines asset type and gets appropriate pipeline
    5. Calls pipeline's inspect method
    6. Updates state with data_contexts (plural) mapping and maintains legacy context for primary
    
    Returns:
        Dictionary with data_contexts (map), asset_type, and messages updates
    """
    assets = state.get("assets")
    if not assets:
        # Fallback to single fields for backward compatibility if no assets list
        file_path = state.get("file_path") or state.get("excel_file_path")
        kbid = state.get("kbid")
        if file_path or kbid:
            # Normalize to assets list structure
            assets = []
            if file_path:
                assets.append({"path": file_path, "type": state.get("asset_type")})
            if kbid:
                assets.append({"kbid": kbid, "type": "document"})
        else:
            return {
                "data_contexts": {"error": "No assets provided"},
                "messages": [AIMessage(
                    content="Please provide at least one file or Knowledge Base ID to analyze. I support Excel (.xlsx, .xls, .csv), "
                            "Documents (.docx, .pdf, .txt, .md, or RAG via kbid), and PowerPoint (.pptx) files.",
                    name="AssetDispatcher"
                )]
            }

    data_contexts = state.get("data_contexts") or {}
    new_messages = []
    
    for asset in assets:
        asset_path = asset.get("path") or asset.get("file_path")
        asset_kbid = asset.get("kbid") or asset.get("kb_id")
        asset_id = asset_path or asset_kbid
        
        if not asset_id:
            continue
            
        # Skip if already inspected
        if asset_id in data_contexts:
            print(f"✅ Using existing context for: {asset_id}")
            continue

        try:
            # Resolve pipeline
            target_type = asset.get("type", "").lower()
            
            if target_type and target_type in registry.registered_pipelines:
                # Get pipeline by name (which is the key and is normalized)
                pipeline = registry.get_pipeline_by_name(target_type)
                
                asset_name = asset.get("name", "Unnamed Asset")
                if asset_kbid and not asset_path:
                    print(f"📡 Dispatching to {pipeline.name} pipeline for RAG (KBID: {asset_kbid}, Name: {asset_name})")
                    context = await pipeline.inspect(asset_kbid)
                else:
                    abs_path = os.path.abspath(asset_path)
                    print(f"📂 Dispatching to {pipeline.name} pipeline for: {abs_path} (Name: {asset_name})")
                    context = await pipeline.inspect(abs_path)
            elif asset_kbid and not asset_path:
                # Fallback for KBID if type not provided
                pipeline = registry.get_pipeline_by_name("Document")
                print(f"📡 Dispatching to {pipeline.name} pipeline for RAG (KBID: {asset_kbid})")
                context = await pipeline.inspect(asset_kbid)
            else:
                # Fallback for path if type not provided
                abs_path = os.path.abspath(asset_path)
                if not registry.is_supported(abs_path):
                    supported = ", ".join(f".{ext}" for ext in registry.supported_extensions)
                    print(f"⚠️ Unsupported file type: {abs_path}. Supported: {supported}")
                    continue
                
                pipeline = registry.get_pipeline_for_file(abs_path)
                print(f"📂 Dispatching to {pipeline.name} pipeline for: {abs_path}")
                context = await pipeline.inspect(abs_path)
            
            data_contexts[asset_id] = context
            new_messages.append(AIMessage(
                content=f"File inspection complete for {pipeline.name}. File: {asset_id}",
                name="AssetDispatcher"
            ))
            
        except Exception as e:
            error_msg = f"Error inspecting {asset_id}: {str(e)}"
            print(f"❌ {error_msg}")
            data_contexts[asset_id] = {"error": error_msg}
            new_messages.append(AIMessage(content=error_msg, name="AssetDispatcher"))

    # Determine "primary" asset for prompts/UI hints (Legacy fallback)
    # We still calculate this for the 'asset_type' field used by the UI, 
    # but we DO NOT let it overwrite the detailed data_contexts.
    primary_asset_id = None
    asset_type = "excel" # default fallback
    
    # Check for Codebase assets
    codebase_assets = []
    for aid, ctx in data_contexts.items():
        if ctx.get("document_type") == "Codebase/Collection (RAG)":
            codebase_assets.append(aid)
            
    # Check for Excel assets
    excel_assets = []
    for aid, ctx in data_contexts.items():
        if "." in str(aid) and "excel" in str(ctx.get("description", "")).lower():
             excel_assets.append(aid)

    if codebase_assets:
        primary_asset_id = codebase_assets[0]
        asset_type = "codebase"
    elif excel_assets:
        primary_asset_id = excel_assets[0]
        asset_type = "excel"
    elif data_contexts:
        primary_asset_id = list(data_contexts.keys())[0]
        # Peek at context the type
        target_ctx = data_contexts[primary_asset_id]
        if "excel" in target_ctx.get("description", "").lower():
            asset_type = "excel"
        elif "powerpoint" in target_ctx.get("description", "").lower():
            asset_type = "powerpoint"
        elif "codebase" in target_ctx.get("description", "").lower():
            asset_type = "codebase"
        else:
            asset_type = "document"

    result = {
        "data_contexts": data_contexts,
        "messages": new_messages,
        "asset_type": asset_type
    }
    
    return result
