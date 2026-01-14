"""Chatbot node for handling general queries without file uploads."""

from typing import Any, Dict

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from datetime import datetime
from my_agent.models.state import ExcelAnalysisState
from langchain_core.runnables import RunnableConfig


# Modify the pronpt asd we support Excel , Document, Codebase, Presentation
CHATBOT_SYSTEM_PROMPT = """You are a helpful AI assistant specialized in Multi-assest Analysis.

You can analyze multiple assets like Excel, Document, Codebase, Presentation etc.

You can help with:
- Explaining Multi-assest analysis concepts
- Suggesting analysis approaches for Multi-assest data

When users interact with you:
- If they ask general questions, provide helpful information about Multi-assest analysis. 
- Be friendly, concise, and helpful

"""


async def chatbot_node(state: ExcelAnalysisState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Chatbot Node - Handles general queries without file uploads.

    This node responds to user questions when:
    - No Excel file has been uploaded
    - No previous analysis context exists
    - User is asking general questions or needs guidance

    Args:
        state: Current state containing messages

    Returns:
        Dictionary with messages update
    """
    print("Chatbot: Responding to general query...")

    queue = config.get("configurable", {}).get("stream_queue")
    
    async def send_status(data):
        if queue:
            await queue.put(data)
        else:
            # Fallback for local testing or if queue not provided
            print(f"[DEBUG NO QUEUE] {data}")
    
    await send_status({
        "type": "status",
        "node": "chatbot",
        "message": "Chatbot: Responding to general query...",
        "payload": {},
        "timestamp": datetime.utcnow().isoformat()
    })
    # Initialize LLM
    from my_agent.core.llm_client import litellm_completion, litellm_completion_stream
    from datetime import datetime

    # Get user's query from messages
    user_messages = [msg for msg in state["messages"] if isinstance(msg, HumanMessage)]
    user_query = user_messages[-1].content if user_messages else "Hello"

    # Create conversation with context
    system_prompt = SystemMessage(content=CHATBOT_SYSTEM_PROMPT)
    user_prompt = HumanMessage(content=str(user_query))

    print(f'[Chatbot DEBUG] SYSTEM PROMPT: {system_prompt.content}')
    print(f'[Chatbot DEBUG] USER PROMPT: {user_prompt.content}')
    # Get response from LLM


    try:
        # Send status update
        await send_status({
            "type": "stream_start",
            "node": "chatbot",
            "message": "Chatbot: Getting response from LLM...",
            "payload": {},
            "timestamp": datetime.utcnow().isoformat()
        })
        response, reasoning_content = await litellm_completion_stream(
            messages=[system_prompt, user_prompt],
            queue=queue,
            temperature=0.7
        )

        print(f"[Chatbot DEBUG] RESPONSE: {response.content}")
        print(f"[Chatbot DEBUG] REASONING: {reasoning_content}")
        # Send status update
        await send_status({
            "type": "stream_end",
            "node": "chatbot",
            "message": "Chatbot: Response from LLM received.",
            "payload": {
                "response_content": response.content,
                "reasoning_content": reasoning_content
            },
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception as e:
        print(f"[Chatbot DEBUG] Exception: {e}")
        response = AIMessage(content=str(e))

    print(f"[Chatbot DEBUG] RESPONSE: {response.content}")

    return {"messages": [response]}
