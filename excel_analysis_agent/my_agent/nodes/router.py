"""Router node for intelligent query classification using LLM."""

from typing import Any, Dict

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from my_agent.models.state import ExcelAnalysisState, RouterDecision
from my_agent.prompts.prompts import ROUTER_SYS_PROMPT, ROUTER_USER_PROMPT


async def router_node(state: ExcelAnalysisState) -> Dict[str, Any]:
    """
    Router Node - Classifies user queries using LLM with structured output.

    This node:
    1. Analyzes the user's query and conversation context
    2. Uses LLM to classify into: "chat", "analysis", or "analysis_followup"
    3. Returns routing decision for conditional edges

    Args:
        state: Current state containing messages and data_context

    Returns:
        Dictionary with route_decision update
    """
    print("🧭 Router: Classifying user query...")

    # Initialize LLM with structured output
    from my_agent.core.llm_client import litellm_completion

    # Get the latest user query
    user_messages = [msg for msg in state["messages"] if isinstance(msg, HumanMessage)]
    if not user_messages:
        print("⚠️ No user messages found, defaulting to chat")
        return {
            "route_decision": {
                "route": "chat",
                "reasoning": "No user query found"
            }
        }

    user_query = user_messages[-1].content

    # Get last 5 high-level messages for context (user queries and AI responses)
    recent_messages = state["messages"][-10:] if len(state["messages"]) > 10 else state["messages"]
    conversation_summary = "\n".join([
        f"{'User' if isinstance(msg, HumanMessage) else 'Assistant'}: {msg.content[:200]}..."
        for msg in recent_messages
    ])

    # Check if data context exists
    data_context = state.get("data_context")
    has_data_context = data_context is not None
    data_context_summary = ""

    if has_data_context:
        file_name = data_context.get("file_name", "unknown")
        num_rows = data_context.get("summary", {}).get("num_rows", 0)
        num_columns = data_context.get("summary", {}).get("num_columns", 0)
        data_context_summary = f"File: {file_name} ({num_rows} rows, {num_columns} columns)"

    # Create prompts
    system_prompt = SystemMessage(content=ROUTER_SYS_PROMPT)
    user_prompt = HumanMessage(
        content=ROUTER_USER_PROMPT.format(
            user_query=user_query,
            conversation_summary=conversation_summary,
            has_data_context="Yes" if has_data_context else "No",
            data_context_summary=data_context_summary if has_data_context else "No data loaded yet"
        )
    )

    # Define structured output schema
    class RouterOutput(BaseModel):
        route: str = Field(
            description="Classification: 'chat', 'analysis', or 'analysis_followup'",
            validation_alias="classification"
        )
        reasoning: str = Field(
            description="Explanation for this classification"
        )

    # Get structured output
    response = await litellm_completion(
        messages=[system_prompt, user_prompt],
        temperature=0,
        response_format=RouterOutput
    )
    
    print("[DEBUG] Router Decision obtained.")
    print(f"[DEBUG] Route: {response.route}")
    print(f"[DEBUG] Reasoning: {response.reasoning}")

    route_decision: RouterDecision = {
        "route": response.route,
        "reasoning": response.reasoning
    }

    print(f"✅ Router Decision: {response.route}")
    print(f"   Reasoning: {response.reasoning}")

    return {
        "route_decision": route_decision
    }
