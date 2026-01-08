"""Task Dispatcher Node - Orchestrates the execution of analysis steps."""

from typing import Any, Dict, List

from langchain_core.messages import SystemMessage, HumanMessage

from my_agent.models.state import CodingSubgraphState, AnalysisStep
from my_agent.pipelines.registry import registry
from my_agent.prompts.prompts import CODING_AGENT_SYS_PROMPT

def task_dispatcher_node(state: CodingSubgraphState) -> Dict[str, Any]:
    """
    Task Dispatcher - Selects the next step and prepares the worker.
    
    This node:
    1. Checks for pending steps in analysis_steps
    2. If all done -> routes to finalize
    3. If pending -> selects the next step
    4. Configures the environment for the assigned agent (Excel, Codebase, etc.)
    5. Returns state updates to trigger the worker
    
    Args:
        state: Current subgraph state
        
    Returns:
        State updates (active_step_index, messages, etc.)
    """
    print("[Dispatcher] Checking task progress...")
    
    steps = state.get("analysis_steps", [])
    if not steps:
        print("[Dispatcher] No steps found, finalizing.")
        return {"active_step_index": -1}
        
    # Find first pending step
    next_step_index = -1
    for i, step in enumerate(steps):
        if step.get("status") == "pending":
            next_step_index = i
            break
            
    if next_step_index == -1:
        print("[Dispatcher] All steps completed! Finalizing.")
        return {"active_step_index": -1}
        
    current_step = steps[next_step_index]
    print(f"[Dispatcher] Starting Step {current_step.get('order')}: {current_step.get('description')}")
    print(f"             Assigned Agent: {current_step.get('assigned_agent')}")
    
    # Get previous context/summaries
    completed_steps = [s for s in steps if s.get("status") == "completed"]
    context_summary = ""
    if completed_steps:
        context_summary = "\n### Previous Steps History\n"
        for s in completed_steps:
            context_summary += f"- Step {s['order']}: {s['description']}\n  Result: {s.get('result_summary', 'Done')}\n"
            
    # Get pipeline-specific system prompt
    assigned_agent = current_step.get("assigned_agent", "General").lower()
    sys_prompt = CODING_AGENT_SYS_PROMPT # Fallback
    user_prompt_template = ""
    
    try:
        pipeline = registry.get_pipeline_by_name(assigned_agent)
        sys_prompt = pipeline.get_coding_system_prompt()
        user_prompt_template = pipeline.get_coding_user_prompt()
        print(f"[Dispatcher] Loaded specialized prompts for {pipeline.name}")
    except:
        print(f"[Dispatcher] No specific pipeline for '{assigned_agent}', using default.")
        
    # Add Orchestrator Instructions (Task Focus)
    orchestrator_instructions = f"""
\n\n--- CURRENT TASK ONLY ---
You are now acting as the {assigned_agent.upper()} Specialist.
Your SOLE objective right now is to execute Step {current_step.get('order')}:
"{current_step.get('description')}"

1. FOCUS ONLY on this specific step.
2. Use the available tools to complete it.
3. If you need data from previous steps, check 'Previous Steps History'.
4. WHEN DONE: You MUST call the `complete_step` tool to mark this task as finished.
   Provide a summary of what you did and any important values found.
5. DO NOT process future steps yet.
"""
    full_sys_prompt = sys_prompt + orchestrator_instructions
    
    # Construct User Prompt
    from my_agent.helpers.sandbox import PLOTS_DIR
    user_query = state.get("user_query")
    data_contexts = state.get("data_contexts", {})
    
    context_parts = []
    for aid, ctx in data_contexts.items():
        desc = ctx.get("description", "")
        context_parts.append(f"### Asset: {aid} ###\n{desc}")
    full_data_context = "\n\n".join(context_parts)

    # Primary asset for template
    primary_asset_id = "N/A"
    if data_contexts:
        primary_asset_id = list(data_contexts.keys())[0]

    # If we have a specialist template, try to use it
    if user_prompt_template:
         try:
             # Most templates expect these keys
             formatted_user_prompt = user_prompt_template.format(
                 analysis_plan=current_step.get("description"),
                 data_context=full_data_context,
                 file_path=primary_asset_id,
                 plots_dir=str(PLOTS_DIR),
                 # Fallbacks for older templates
                 excel_file_path=primary_asset_id,
                 full_text=state.get("full_text", "N/A"),
                 slide_count=state.get("slide_count", "0"),
                 kbid=state.get("kbid", "N/A")
             )
         except Exception as e:
             print(f"[Dispatcher] Template formatting failed: {e}. Falling back to simple prompt.")
             user_prompt_template = ""

    if not user_prompt_template:
        formatted_user_prompt = f"""
User Query: {user_query}

Data Context:
{full_data_context}

{context_summary}

--- ACTION REQUIRED ---
Execute Step {current_step.get('order')}: {current_step.get('description')}

Plots should be saved to: {PLOTS_DIR}
"""

    return {
        "active_step_index": next_step_index,
        "messages": [
            SystemMessage(content=full_sys_prompt),
            HumanMessage(content=formatted_user_prompt)
        ],
        "code_iterations": 0 
    }
