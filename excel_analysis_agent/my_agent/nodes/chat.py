"""Chat node for handling generic non-analysis queries."""

from typing import Any, Dict

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from my_agent.models.state import ExcelAnalysisState
from my_agent.prompts.prompts import CHAT_SYS_PROMPT, CHAT_USER_PROMPT
from langchain_core.runnables import RunnableConfig
from datetime import datetime

async def chat_node(state: ExcelAnalysisState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Chat Node - Handles generic conversational queries.

    This node:
    1. Responds to non-data-analysis queries (greetings, general questions, etc.)
    2. Can provide guidance on how to use the system
    3. Maintains friendly, helpful tone

    Args:
        state: Current state containing messages

    Returns:
        Dictionary with messages update
    """

    from my_agent.core.llm_client import litellm_completion, litellm_completion_stream


    print("Chat: Handling general query...")
    queue = config.get("configurable", {}).get("stream_queue")
    
    async def send_status(data):
        if queue:
            await queue.put(data)
        else:
            # Fallback for local testing or if queue not provided
            print(f"[DEBUG NO QUEUE] {data}")

    await send_status({
        "type": "status",
        "node": "chat",
        "message": "Chat: Handling general query...",
        "payload": {},
        "timestamp": datetime.utcnow().isoformat()
    })
    # Initialize LLM
    


    # Get the user's query
    user_messages = [msg for msg in state["messages"] if isinstance(msg, HumanMessage)]
    user_query = user_messages[-1].content if user_messages else "Hello"

    # Create prompts
    system_prompt = SystemMessage(content=CHAT_SYS_PROMPT)
    user_prompt = HumanMessage(
        content=CHAT_USER_PROMPT.format(user_query=user_query)
    )

    print(f"[CHAT DEBUG] SYSTEM PROMPT: {system_prompt.content}")
    print(f"[CHAT DEBUG] USER PROMPT: {user_prompt.content}")

    try:
        # Send status update
        await send_status({
            "type": "stream_start",
            "node": "chat",
            "message": "Chat: Getting response from LLM...",
            "payload": {},
            "timestamp": datetime.utcnow().isoformat()
        })
        response, reasoning_content = await litellm_completion_stream(
            messages=[system_prompt, user_prompt],
            queue=queue,
            temperature=0.7
        )

        print(f"[CHAT DEBUG] RESPONSE: {response.content}")
        print(f"[CHAT DEBUG] REASONING: {reasoning_content}")
        # Send status update
        await send_status({
            "type": "stream_end",
            "node": "chat",
            "message": "Chat: Response from LLM received.",
            "payload": {
                "response_content": response.content,
                "reasoning_content": reasoning_content
            },
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception as e:
        print(f"[CHAT DEBUG] Exception: {e}")
        response = AIMessage(content=str(e))

    # print(f"✅ Chat: Response generated")

    # Create AI message
    chat_message = AIMessage(
        content=response.content,
        name="ChatAssistant"
    )

    print(f"[CHAT DEBUG] RESPONSE: {response.content}")

    return {
        "messages": [chat_message]
    }
