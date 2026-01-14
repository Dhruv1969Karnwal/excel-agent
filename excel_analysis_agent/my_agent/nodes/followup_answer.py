"""Follow-up answer node for answering questions from existing analysis context."""

from typing import Any, Dict

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from my_agent.models.state import ExcelAnalysisState
from my_agent.prompts.prompts import FOLLOWUP_ANSWER_SYS_PROMPT, FOLLOWUP_ANSWER_USER_PROMPT
from pprint import pprint
from langchain_core.runnables import RunnableConfig
from datetime import datetime

async def followup_answer_node(state: ExcelAnalysisState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Follow-up Answer Node - Answers questions from existing analysis context.

    This node:
    1. Extracts user's follow-up question
    2. References previous analysis and data context
    3. Provides direct answer without running new code

    Args:
        state: Current state containing messages, data_context, final_analysis

    Returns:
        Dictionary with messages update
    """

    queue = config.get("configurable", {}).get("stream_queue")

    async def send_status(data):
        if queue:
            await queue.put(data)
        else:
            # Fallback for local testing or if queue not provided
            print(f"[DEBUG NO QUEUE] {data}")

    print("Follow-up Answer: Answering from existing context...")
    await send_status({
        "type": "status",
        "node": "followup_answer",
        "message": "Follow-up Answer: Answering from existing context...",
        "payload": {},
        "timestamp": datetime.utcnow().isoformat()
    })

    # Initialize LLM
    from my_agent.core.llm_client import litellm_completion, litellm_completion_stream

    # Get the user's query
    user_messages = [msg for msg in state["messages"] if isinstance(msg, HumanMessage)]
    user_query = user_messages[-1].content if user_messages else "Please provide more details"

    # Get data context (Multi-Asset Support)
    data_contexts = state.get("data_contexts") or {}

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
    previous_analysis = state.get("final_analysis", "No previous analysis available")

    # Create prompts
    system_prompt = SystemMessage(content=FOLLOWUP_ANSWER_SYS_PROMPT)
    user_prompt = HumanMessage(
        content=FOLLOWUP_ANSWER_USER_PROMPT.format(
            user_query=user_query,
            data_context=data_context,
            previous_analysis=previous_analysis
        )
    )
    print("[Follow-up Answer DEBUG inside followup_answer_node] System prompt is ")
    pprint(system_prompt, indent=2)
    print("[Follow-up Answer DEBUG inside followup_answer_node] User prompt is ")
    pprint(user_prompt, indent=2)
    # Get response
    try:
        # Send status update
        await send_status({
            "type": "stream_start",
            "node": "followup_answer",
            "message": "Follow-up Answer: Getting response from LLM...",
            "payload": {},
            "timestamp": datetime.utcnow().isoformat()
        })
        response, reasoning_content = await litellm_completion_stream(
            messages=[system_prompt, user_prompt],
            queue=queue,
            temperature=0
        )
        print("[Follow-up Answer DEBUG inside followup_answer_node] Response is ")
        pprint(response, indent=2)
        await send_status({
            "type": "stream_end",
            "node": "followup_answer",
            "message": "Follow-up answer generated.",
            "payload": {
                "answer": response.content,
                "reasoning_content": reasoning_content
            },
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception as e:
        print(f"[Follow-up Answer DEBUG inside followup_answer_node] Exception: {e}")
        response = AIMessage(content=str(e))
    # print(f"✅ Follow-up Answer: Response generated")

    # Create AI message
    answer_message = AIMessage(
        content=response.content,
        name="FollowupAssistant"
    )
    print("[Follow-up Answer DEBUG inside followup_answer_node] Answer message is ")
    pprint(answer_message, indent=2)

    return {
        "messages": [answer_message]
    }
