"""Router node for intelligent query classification using LLM."""

from typing import Any, Dict

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from my_agent.models.state import ExcelAnalysisState, RouterDecision
from my_agent.prompts.prompts import ROUTER_SYS_PROMPT, ROUTER_USER_PROMPT


from langchain_core.callbacks.manager import adispatch_custom_event
from langchain_core.runnables import RunnableConfig
from datetime import datetime


async def router_node(state: ExcelAnalysisState, config: RunnableConfig):
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
    # Helper to send status updates via queue
    queue = config.get("configurable", {}).get("stream_queue")
    
    async def send_status(data):
        if queue:
            await queue.put(data)
        else:
            # Fallback for local testing or if queue not provided
            print(f"[DEBUG NO QUEUE] {data}")

    # Example of a custom yield for real-time UI updates
    print("[DEBUG] About to dispatch status 1")
    await send_status({
        "type": "status",
        "node": "router",
        "message": "Router: Classifying user query...",
        "payload": {},
        "timestamp": datetime.utcnow().isoformat()
    })
    print("[DEBUG] Dispatched status 1")
    print("Router: Classifying user query...")


    # Initialize LLM with structured output
    from my_agent.core.llm_client import litellm_completion

    # Get the latest user query
    user_messages = [msg for msg in state["messages"] if isinstance(msg, HumanMessage)]
    if not user_messages:
        await send_status({
            "type": "error",
            "node": "router",
            "message": "No user query found in the transaction history.",
            "payload": {
                "error": "Missing user message"
            },
            "timestamp": datetime.utcnow().isoformat()
        })
        print("[DEBUG] Dispatched error")
        # Don't return here, return a valid state update
        return 

    user_query = user_messages[-1].content
    
    print("[DEBUG] About to dispatch status 2")
    # await send_status({
    #     "type": "status",
    #     "message": "Analyzing conversation context...",
    #     "node": "router"
    # })
    print("[DEBUG] Dispatched status 2")

    # Get last 5 high-level messages for context (user queries and AI responses)
    recent_messages = state["messages"][-10:] if len(state["messages"]) > 10 else state["messages"]
    conversation_summary = "\n".join([
        f"{'User' if isinstance(msg, HumanMessage) else 'Assistant'}: {msg.content[:200]}..."
        for msg in recent_messages
    ])


    # Check if data context exists (Multi-Asset Support)
    data_contexts = state.get("data_contexts") or {}
    
    has_data_context = len(data_contexts) > 0
    data_context_summary = ""

    if has_data_context:
        summary_parts = []
        for asset_id, ctx in data_contexts.items():
            # Extract summary details based on context type
            file_name = ctx.get("file_name", str(asset_id))
            desc = ctx.get("description", "No description")
            
            # Use specific fields if available for cleaner summary
            if "num_rows" in ctx.get("summary", {}):
                rows = ctx.get("summary", {}).get("num_rows", 0)
                cols = ctx.get("summary", {}).get("num_columns", 0)
                summary_parts.append(f"- Asset: {file_name} (Excel: {rows} rows, {cols} cols)\n  Description: {desc}")
            else:
                summary_parts.append(f"- Asset: {file_name}\n  Description: {desc}")
        
        data_context_summary = "\n".join(summary_parts)
    else:
        data_context_summary = "No data loaded yet."

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

    # print(f"[DEBUG ROUTER] SYSTEM PROMPT: {system_prompt.content}")
    # print(f"[DEBUG ROUTER] USER PROMPT: {user_prompt.content}")

    # Get structured output
    response = await litellm_completion(
        messages=[system_prompt, user_prompt],
        temperature=0,
        response_format=RouterOutput
    )
    
    # print("[DEBUG ROUTER] Router Decision obtained.")
    # print(f"[DEBUG ROUTER] Route: {response.route}")
    # print(f"[DEBUG ROUTER] Reasoning: {response.reasoning}")

    route_decision: RouterDecision = {
        "route": response.route,
        "reasoning": response.reasoning
    }

# Yield the decision as a custom event
    print("[DEBUG] About to dispatch decision")
    await send_status({
        "type": "decision",
        "node": "router",
        "message": f"Query classified as: {response.route}",
        "payload": {
            "route": response.route,
            "reasoning": response.reasoning
        },
        "timestamp": datetime.utcnow().isoformat()
    })
    print("[DEBUG] Dispatched decision")

    return {
        "route_decision": route_decision
    }

