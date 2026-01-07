"""Chat node for handling generic non-analysis queries."""

from typing import Any, Dict

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from my_agent.models.state import ExcelAnalysisState
from my_agent.prompts.prompts import CHAT_SYS_PROMPT, CHAT_USER_PROMPT


async def chat_node(state: ExcelAnalysisState) -> Dict[str, Any]:
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
    print("Chat: Handling general query...")

    # Initialize LLM
    from my_agent.core.llm_client import litellm_completion

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

    # Get response
    response = await litellm_completion(
        messages=[system_prompt, user_prompt],
        temperature=0.7
    )



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
