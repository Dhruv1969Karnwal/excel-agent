"""Planning node for creating detailed analysis plans."""

import json
import re
from typing import Any, Dict

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

from my_agent.models.state import UnifiedAnalysisState
from my_agent.pipelines.registry import registry
# Fallback prompts for backward compatibility
from my_agent.prompts.prompts import PLANNING_SYS_PROMPT, PLANNING_USER_PROMPT
from pprint import pprint

async def planning_node(state: UnifiedAnalysisState) -> Dict[str, Any]:
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
    print("Planning: Creating analysis plan...")

    # Initialize LLM
    from my_agent.core.llm_client import litellm_completion

    # Get user query
    user_query = state.get("user_query", "Analyze the data")

    # Get data context
    data_context_dict = state.get("data_context")
    data_context = ""
    if data_context_dict:
        data_context = data_context_dict.get("description", "No data description available")

    # Get pipeline-specific prompts based on asset type
    asset_type = state.get("asset_type", "excel").lower()
    file_path = state.get("file_path") or state.get("excel_file_path")
    
    # Try to get prompts from pipeline, fallback to default
    try:
        if file_path:
            pipeline = registry.get_pipeline_for_file(file_path)
            planning_sys_prompt = pipeline.get_planning_system_prompt()
            planning_user_prompt = pipeline.get_planning_user_prompt()
            print(f"[Planning DEBUG inside planning_node] Using {pipeline.name} pipeline prompts for planning")
        else:
            planning_sys_prompt = PLANNING_SYS_PROMPT
            planning_user_prompt = PLANNING_USER_PROMPT
            print("[Planning DEBUG inside planning_node] Using default prompts for planning")
    except Exception as e:
        print("[Planning DEBUG inside planning_node] Could not get pipeline prompts: {e}, using defaults")
        planning_sys_prompt = PLANNING_SYS_PROMPT
        planning_user_prompt = PLANNING_USER_PROMPT

    # Create prompts
    system_prompt = SystemMessage(content=planning_sys_prompt)
    user_prompt = HumanMessage(
        content=planning_user_prompt.format(
            user_query=user_query,
            data_context=data_context
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
                    "result_summary": ""
                })
            except json.JSONDecodeError:
                print(f"⚠️ Could not parse step JSON: {match}")
                continue

    if structured_steps:
        print(f"[DEBUG] Created {len(structured_steps)} structured analysis steps")
    else:
        print("[DEBUG] No structured steps found, using text plan only")

    print(f"[DEBUG] Planning: Analysis plan created with {len(structured_steps)} structured steps.")
    for step in structured_steps:
        print(f"  - Step {step['order']}: {step['description']}")

    print("[Planning DEBUG inside planning_node] Analysis plan is ", analysis_plan_text)
    print("[Planning DEBUG inside planning_node] Structured steps are ", structured_steps)
    return {
        "analysis_plan": analysis_plan_text,
        "analysis_steps": structured_steps
    }
