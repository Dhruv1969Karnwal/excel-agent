"""Supervisor node for evaluating if new analysis is needed."""

from typing import Any, Dict

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from my_agent.models.state import ExcelAnalysisState, SupervisorDecision
from my_agent.prompts.prompts import SUPERVISOR_SYS_PROMPT, SUPERVISOR_USER_PROMPT
from pprint import pprint
from langchain_core.runnables import RunnableConfig
from datetime import datetime
import json
async def supervisor_node(state: ExcelAnalysisState, config: RunnableConfig) -> Dict[str, Any]:
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
    queue = config.get("configurable", {}).get("stream_queue")

    async def send_status(data):
        if queue:
            await queue.put(data)
        else:
            # Fallback for local testing or if queue not provided
            print(f"[DEBUG NO QUEUE] {data}")

    print("Supervisor: Evaluating if new analysis is needed...")

    await send_status({
        "type": "status",
        "node": "supervisor",
        "message": "Supervisor: Evaluating if new analysis is needed...",
        "payload": {},
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Initialize LLM
    from my_agent.core.llm_client import litellm_completion

    # Get the user's query
    user_messages = [msg for msg in state["messages"] if isinstance(msg, HumanMessage)]
    user_query = user_messages[-1].content if user_messages else "Analyze"

    # Get data context (Multi-Asset Support)
    data_contexts = state.get("data_contexts") or {}

    print("[Supervisor DEBUG inside supervisor_node] Data contexts: ")
    # with open("data_contexts.json", "w") as f:
    #     json.dump(data_contexts, f, indent=4)
    
    data_context = ""
    if data_contexts:
        context_parts = []
        for asset_id, ctx in data_contexts.items():
            desc = ctx.get("description", "No description")
            file_name = ctx.get("file_name", "No file name")
            context_parts.append(f"--- Asset: {file_name} ---\n{desc}")
        data_context = "\n\n".join(context_parts)
    else:
        data_context = "No data description available"

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

    print("[Supervisor DEBUG inside supervisor_node] System prompt is ")
    pprint(system_prompt.content)
    print("[Supervisor DEBUG inside supervisor_node] User prompt is ")
    pprint(user_prompt.content)
    # Get structured output
    response = await litellm_completion(
        messages=[system_prompt, user_prompt],
        temperature=0,
        response_format=SupervisorOutput
    )
    
    print("[Supervisor DEBUG inside supervisor_node] Supervisor Decision obtained.")
    print(f"[Supervisor DEBUG inside supervisor_node] Needs Analysis: {response.needs_analysis}")
    # print(f"[Supervisor DEBUG inside supervisor_node] Reasoning: {response.reasoning}")

    supervisor_decision: SupervisorDecision = {
        "needs_analysis": response.needs_analysis,
        "reasoning": response.reasoning
    }

    await send_status({
        "type": "decision",
        "node": "supervisor",
        "message": f"Supervisor decision: {'Analysis needed' if response.needs_analysis else 'Answer from context'}",
        "payload": {
            "needs_analysis": response.needs_analysis,
            "reasoning": response.reasoning
        },
        "timestamp": datetime.utcnow().isoformat()
    })

    # print(f"[Supervisor DEBUG inside supervisor_node] Supervisor Decision: {'New analysis needed' if response.needs_analysis else 'Answer from context'}")
    # print(f"[Supervisor DEBUG inside supervisor_node] Reasoning: {response.reasoning}")

    return {
        "supervisor_decision": supervisor_decision,
        "user_query": str(user_query)
    }
