"""Planning node for creating detailed analysis plans."""

import json
import re
from typing import Any, Dict

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

from my_agent.models.state import UnifiedAnalysisState
from my_agent.pipelines.registry import registry
# Fallback prompts for backward compatibility
# from my_agent.prompts.prompts import PLANNING_SYS_PROMPT, PLANNING_USER_PROMPT
from pprint import pprint
from langchain_core.runnables import RunnableConfig
from datetime import datetime

async def planning_node(state: UnifiedAnalysisState, config: RunnableConfig ) -> Dict[str, Any]:
    """
    Planning Node - Creates a detailed analysis plan.

    This node:
    1. Takes the user query and data context
    2. Gets pipeline-specific prompts based on asset type
    3. Uses an LLM to generate a comprehensive analysis plan
    4. Parses structured steps for tracking
    5. Returns the plan for the coding agent

    Supports all asset types (Excel, Document, PowerPoint).

    Args:
        state: Current state containing user query and data_context

    Returns:
        Dictionary with analysis_plan and analysis_steps updates
    """

    queue = config.get("configurable", {}).get("stream_queue")

    async def send_status(data):
        if queue:
            await queue.put(data)
        else:
            # Fallback for local testing or if queue not provided
            print(f"[DEBUG NO QUEUE] {data}")

    print("Planning: Creating analysis plan...")
    await send_status({
        "type": "status",
        "node": "planning",
        "message": "Planning: Creating analysis plan...",
        "payload": {},
        "timestamp": datetime.utcnow().isoformat()
    })
    # Initialize LLM
    from my_agent.core.llm_client import litellm_completion

    # Get user query
    user_query = state.get("user_query", "Analyze")

    # Get data contexts (plural)
    data_contexts = state.get("data_contexts") or {}
    # print("[Planning DEBUG inside planning_node] Data contexts: ")
    # pprint(data_contexts, indent=2)
    combined_data_context = ""
    
    if data_contexts:
        context_parts = []
        for asset_id, ctx in data_contexts.items():
            desc = ctx.get("description", "No description")
            file_name = ctx.get("file_name", "No file name")
            context_parts.append(f"--- Asset: {file_name} ---\n{desc}")
        combined_data_context = "\n\n".join(context_parts)
    else:
        combined_data_context = "No data loaded."

    # Determine prompt strategy based on asset types
    asset_types = set()
    for ctx in data_contexts.values():
        dtype = ctx.get("document_type", "").lower()
        if "excel" in dtype or "csv" in dtype:
            asset_types.add("Excel")
        elif "codebase" in dtype:
            asset_types.add("Codebase")
        elif "powerpoint" in dtype:
            asset_types.add("PowerPoint")
        else:
            asset_types.add("Document")

    print("[Planning DEBUG inside planning_node] Asset types: ")
    pprint(asset_types, indent=2)
    # Select Pipeline Prompts
    # Case 1: Single Asset Type -> Use that pipeline's specific prompts
    if len(asset_types) == 1:
        print("[Planning DEBUG inside planning_node] Single asset type detected.")
        target_type = list(asset_types)[0]
        print(f"[Planning DEBUG inside planning_node] Target type: {target_type}")
        try:
            pipeline = registry.get_pipeline_by_name(target_type)
            print(f"[Planning DEBUG inside planning_node] Pipeline: {pipeline}")
            planning_sys_prompt = pipeline.get_planning_system_prompt()
            planning_user_prompt = pipeline.get_planning_user_prompt()
            print(f"[Planning DEBUG inside planning_node] Using {pipeline.name} pipeline prompts")
        except Exception as e:
            # Fallback only if pipeline fetch fails (should not happen in unified plan)
            print(f"[Planning DEBUG inside planning_node] Error getting pipeline prompts: {e}.")
            from my_agent.prompts.prompts import PLANNING_SYS_PROMPT, PLANNING_USER_PROMPT
            planning_sys_prompt = PLANNING_SYS_PROMPT
            planning_user_prompt = PLANNING_USER_PROMPT
            
    # Case 2: Mixed Asset Types -> Dynamically Merge Prompts
    elif len(asset_types) > 1:
        print(f"[Planning] Mixed asset types detected {asset_types}. Merging prompts dynamically.")
        
        sys_prompts = []
        user_prompts = []
        
        # 1. Fetch prompts from ALL active pipelines
        try:
            print("[Planning DEBUG inside planning_node] Fetching prompts from ALL active pipelines.")
            for dtype in asset_types:
                # Map asset type string back to pipeline instance
                # The registry names are usually capitalized (Excel, Document), asset_types has them.
                pipeline = registry.get_pipeline_by_name(dtype)
                sys_prompts.append(f"--- Instructions for {dtype} Analysis ---\n{pipeline.get_planning_system_prompt()}")
                # We typically use the first user prompt or a generic one, but let's check
                # Ideally user prompt is just "Here is the query: {query}", so we can use a generic header.
            
            # 2. Combine System Prompts
            header = "You are a Multi-Asset Analysis Agent. You must combine the capabilities of the following specialists:"
            planning_sys_prompt = f"{header}\n\n" + "\n\n".join(sys_prompts)
            planning_sys_prompt += "\n\nIMPORTANT: You must cross-reference information between these assets. Plan steps that involve switching contexts (e.g., read Excel -> search Codebase)."
            planning_sys_prompt += "\n\nCRITICAL: For each step, you MUST assign the single most relevant agent/pipeline (e.g., 'Excel', 'Codebase', 'Document')."
            planning_sys_prompt += "\nFormat your steps as a JSON list with keys: 'order', 'description', 'assigned_agent'."

            # 3. Use Generic User Prompt (to avoid conflict/duplication)
            # We import this just for the structure "{user_query} ... {data_context}"
            from my_agent.prompts.prompts import PLANNING_USER_PROMPT
            planning_user_prompt = PLANNING_USER_PROMPT

        except Exception as e:
            print(f"[Planning DEBUG inside planning_node] Error merging prompts: {e}.")
            print("[Planning DEBUG inside planning_node] Using default prompts.")
            from my_agent.prompts.prompts import PLANNING_SYS_PROMPT, PLANNING_USER_PROMPT
            planning_sys_prompt = PLANNING_SYS_PROMPT
            planning_user_prompt = PLANNING_USER_PROMPT

    # Case 3: No Data -> Default
    else:
        print("[Planning DEBUG inside planning_node] No data detected. Using default prompts.")
        from my_agent.prompts.prompts import PLANNING_SYS_PROMPT, PLANNING_USER_PROMPT
        planning_sys_prompt = PLANNING_SYS_PROMPT
        planning_user_prompt = PLANNING_USER_PROMPT

    # Create prompts
    system_prompt = SystemMessage(content=planning_sys_prompt)
    user_prompt = HumanMessage(
        content=planning_user_prompt.format(
            user_query=user_query,
            data_context=combined_data_context
        )
    )

    print("[Planning DEBUG inside planning_node] System prompt is ")
    pprint(system_prompt, indent=2)
    print("[Planning DEBUG inside planning_node] User prompt is ")
    pprint(user_prompt, indent=2)

    # Generate the plan
    response = await litellm_completion(
        messages=[system_prompt, user_prompt],
        temperature=0
    )

    print(f"[Planning DEBUG inside planning_node] Response is ", response.content)

    # Parse response to extract text plan and structured steps
    response_text = str(response.content)
    analysis_plan_text = response_text
    structured_steps = []

    await send_status({
        "type": "plan",
        "node": "planning",
        "message": "Analysis plan generated successfully.",
        "payload": {
            "plan_text": analysis_plan_text
        },
        "timestamp": datetime.utcnow().isoformat()
    })

    # with open("response.txt", "w") as f:
    #     f.write(response_text)

    # Check if response contains structured steps
    if "---STEPS---" in response_text:
        parts = response_text.split("---STEPS---")
        analysis_plan_text = parts[0].strip()

        # Parse JSON steps
        steps_text = parts[1].strip()

        # Extract JSON objects line by line
        json_pattern = r'\{[^}]+\}'
        matches = re.findall(json_pattern, steps_text)

        for match in matches:
            try:
                step_data = json.loads(match)
                structured_steps.append({
                    "description": step_data.get("description", ""),
                    "status": "pending",
                    "order": step_data.get("order", 0),
                    "assigned_agent": step_data.get("assigned_agent", "General"),
                    "result_summary": ""
                })
            except json.JSONDecodeError:
                print(f"⚠️ Could not parse step JSON: {match}")
                continue
    
    await send_status({
        "type": "steps",
        "node": "planning",
        "message": f"Identified {len(structured_steps)} analysis steps.",
        "payload": {
            "steps": structured_steps
        },
        "timestamp": datetime.utcnow().isoformat()
    })
    if structured_steps:
        print(f"[Planning DEBUG inside planning_node] Created {len(structured_steps)} structured analysis steps and all steps are {structured_steps}")
    #     print(f"[DEBUG] Created {len(structured_steps)} structured analysis steps")
    # else:
    #     print("[DEBUG] No structured steps found, using text plan only")

    # print(f"[DEBUG] Planning: Analysis plan created with {len(structured_steps)} structured steps.")
    # for step in structured_steps:
    #     print(f"  - Step {step['order']}: {step['description']}")

    print("[Planning DEBUG inside planning_node] Analysis plan is ", analysis_plan_text)
    print("[Planning DEBUG inside planning_node] Structured steps are ", structured_steps)
    return {
        "analysis_plan": analysis_plan_text,
        "analysis_steps": structured_steps,
        "active_step_index": 0
    }
