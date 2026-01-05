"""Planning node for creating detailed analysis plans."""

import json
import re
from typing import Any, Dict

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

from my_agent.core.infisical_client import get_secret
from my_agent.models.state import ExcelAnalysisState
from my_agent.prompts.prompts import PLANNING_SYS_PROMPT, PLANNING_USER_PROMPT


async def planning_node(state: ExcelAnalysisState) -> Dict[str, Any]:
    """
    Planning Node - Creates a detailed analysis plan.

    This node:
    1. Takes the user query and data context
    2. Uses an LLM to generate a comprehensive analysis plan
    3. Parses structured steps for tracking
    4. Returns the plan for the coding agent

    Args:
        state: Current state containing user query and data_context

    Returns:
        Dictionary with analysis_plan and analysis_steps updates
    """
    print("📋 Planning: Creating analysis plan...")

    # Initialize LLM
    llm = init_chat_model(
        model="gpt-4o", api_key=get_secret("OPENAI_API_KEY"), temperature=0
    )

    # Get user query
    user_query = state.get("user_query", "Analyze the data")

    # Get data context
    data_context_dict = state.get("data_context")
    data_context = ""
    if data_context_dict:
        data_context = data_context_dict.get("description", "No data description available")

    # Create prompts
    system_prompt = SystemMessage(content=PLANNING_SYS_PROMPT)
    user_prompt = HumanMessage(
        content=PLANNING_USER_PROMPT.format(
            user_query=user_query,
            data_context=data_context
        )
    )

    # Generate the plan
    response = await llm.ainvoke([system_prompt, user_prompt])

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
        print(f"✅ Created {len(structured_steps)} structured analysis steps")
    else:
        print("⚠️ No structured steps found, using text plan only")

    print(f"✅ Planning: Analysis plan created")

    return {
        "analysis_plan": analysis_plan_text,
        "analysis_steps": structured_steps
    }
