"""Helper for dynamic pipeline registration based on attachments."""

from typing import Any, Dict, List
from my_agent.pipelines.registry import registry

def register_pipelines_from_attachments(attachments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Register pipelines dynamically based on attachment types.
    
    Args:
        attachments: List of dicts like [{"type": "excel", "path": "x.xlsx"}, ...]
        
    Returns:
        List of normalized asset metadata objects for state['assets']
    """
    from my_agent.pipelines.excel import ExcelPipeline
    from my_agent.pipelines.document import DocumentPipeline
    from my_agent.pipelines.powerpoint import PowerPointPipeline
    from my_agent.pipelines.codebase import CodebasePipeline
    from my_agent.pipelines.code import CodePipeline
    
    # Map type to Pipeline Class
    # This allows us to instantiate pipelines on-demand
    pipeline_class_map = {
        "excel": ExcelPipeline,
        "document": DocumentPipeline,
        "docs": DocumentPipeline, # Alias
        "powerpoint": PowerPointPipeline,
        "ppt": PowerPointPipeline, # Alias
        "codebase": CodebasePipeline,
        "code": CodePipeline,
        "py": CodePipeline,
        "python": CodePipeline,
        "js": CodePipeline,
        "javascript": CodePipeline,
        "image": None # Placeholder for future
    }
    
    normalized_assets = []
    
    for att in attachments:
        # Strict enforcement: Asset must have a 'type'
        asset_type = att.get("type", "").lower()
        if not asset_type:
            continue
            
        asset_metadata = {}
        target_pipeline_class = None
        
        # 1. Check if pipeline is already registered
        if asset_type in registry.registered_pipelines:
            # Already registered, just need to normalize metadata
            # We don't need the class if it's already in the registry instance
            pass
            
        # 2. Check if we have a mapping to instantiate it
        elif asset_type in pipeline_class_map:
            target_pipeline_class = pipeline_class_map[asset_type]
            if target_pipeline_class:
                # Instantiate and Register
                pipeline_instance = target_pipeline_class()
                registry.register(pipeline_instance)
                
        # 3. Populate Metadata
        # We only process if it is now supported
        if asset_type in registry.registered_pipelines:
             asset_metadata["type"] = asset_type
             asset_metadata["name"] = att.get("name") or "Unnamed Asset"
             
             # Identity Logic
             if asset_type == "codebase":
                 asset_metadata["kbid"] = att.get("kbid") or att.get("path")
             else:
                 asset_metadata["path"] = att.get("path")
                 if att.get("kbid"): # Optional for RAG docs
                     asset_metadata["kbid"] = att.get("kbid")
            
             normalized_assets.append(asset_metadata)
        else:
            print(f"⚠️ Warning: Unknown asset type '{asset_type}'. Skipping.")

    return normalized_assets

def process_incoming_request(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Processes chat request and prepares initial agent state.
    """
    query = request_data.get("query", "")
    context_message = request_data.get("context_message", "")
    attachments = request_data.get("attachments", [])
    history = request_data.get("history", [])
    
    # Register pipelines and get asset metadata
    assets = register_pipelines_from_attachments(attachments)
    
    # Prepare messages
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    
    messages = []
    # Add history if provided
    for msg in history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
        elif role == "system":
            messages.append(SystemMessage(content=content))
            
    # Add context message as a system note if present
    if context_message:
        messages.append(SystemMessage(content=f"Context: {context_message}"))
        
    # Add final query
    messages.append(HumanMessage(content=query))
    
    initial_state = {
        "messages": messages,
        "assets": assets,
        "user_query": query,
        "code_iterations": 0
    }
    
    return initial_state
