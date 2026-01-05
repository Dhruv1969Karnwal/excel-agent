"""Supervisor node for evaluating if new analysis is needed."""

from typing import Any, Dict

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from my_agent.models.state import ExcelAnalysisState, SupervisorDecision
from my_agent.prompts.prompts import SUPERVISOR_SYS_PROMPT, SUPERVISOR_USER_PROMPT


async def supervisor_node(state: ExcelAnalysisState) -> Dict[str, Any]:
    """
    Supervisor Node - Evaluates if new code execution is needed.

    This node:
    1. Analyzes user query and existing analysis context
    2. Decides if query can be answered from existing data or needs new code
    3. Returns decision for routing

    Args:
        state: Current state containing messages, data_context, final_analysis

    Returns:
        Dictionary with supervisor_decision and user_query updates
    """
    print("🎯 Supervisor: Evaluating if new analysis is needed...")

    # Initialize LLM
    from my_agent.core.llm_client import litellm_completion

    # Get the user's query
    user_messages = [msg for msg in state["messages"] if isinstance(msg, HumanMessage)]
    user_query = user_messages[-1].content if user_messages else "Analyze the data"

    # Get data context
    data_context_dict = state.get("data_context")
    data_context = ""
    if data_context_dict:
        data_context = data_context_dict.get("description", "No data description available")

    # Get previous analysis
    previous_analysis = state.get("final_analysis", "No previous analysis exists")

    # Create prompts
    system_prompt = SystemMessage(content=SUPERVISOR_SYS_PROMPT)
    user_prompt = HumanMessage(
        content=SUPERVISOR_USER_PROMPT.format(
            user_query=user_query,
            data_context=data_context,
            previous_analysis=previous_analysis
        )
    )

    # Define structured output schema
    class SupervisorOutput(BaseModel):
        needs_analysis: bool = Field(
            description="True if new code execution needed, False if can answer from context"
        )
        reasoning: str = Field(
            description="Explanation for this decision"
        )

    # Get structured output
    response = await litellm_completion(
        messages=[system_prompt, user_prompt],
        temperature=0,
        response_format=SupervisorOutput
    )
    
    print("[DEBUG] Supervisor Decision obtained.")
    print(f"[DEBUG] Needs Analysis: {response.needs_analysis}")
    print(f"[DEBUG] Reasoning: {response.reasoning}")

    supervisor_decision: SupervisorDecision = {
        "needs_analysis": response.needs_analysis,
        "reasoning": response.reasoning
    }

    print(f"✅ Supervisor Decision: {'New analysis needed' if response.needs_analysis else 'Answer from context'}")
    print(f"   Reasoning: {response.reasoning}")

    return {
        "supervisor_decision": supervisor_decision,
        "user_query": str(user_query)  # Pass user query for downstream nodes
    }
