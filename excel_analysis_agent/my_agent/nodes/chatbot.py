"""Chatbot node for handling general queries without file uploads."""

from typing import Any, Dict

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

from my_agent.models.state import ExcelAnalysisState


CHATBOT_SYSTEM_PROMPT = """You are a helpful AI assistant specialized in Excel data analysis.

When users interact with you:
- If they upload an Excel file, you'll analyze it and provide insights
- If they ask general questions, provide helpful information about Excel analysis, data science, or related topics
- Be friendly, concise, and helpful

You can help with:
- Explaining data analysis concepts
- Suggesting analysis approaches for Excel data
- Answering questions about pandas, matplotlib, and data visualization
- Providing general advice on working with spreadsheet data

If the user wants to analyze data, politely ask them to upload an Excel file (.xlsx, .xls, or .csv).
"""


async def chatbot_node(state: ExcelAnalysisState) -> Dict[str, Any]:
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

    # Initialize LLM
    from my_agent.core.llm_client import litellm_completion

    # Get user's query from messages
    user_messages = [msg for msg in state["messages"] if isinstance(msg, HumanMessage)]
    user_query = user_messages[-1].content if user_messages else "Hello"

    # Create conversation with context
    system_prompt = SystemMessage(content=CHATBOT_SYSTEM_PROMPT)
    user_prompt = HumanMessage(content=str(user_query))

    print(f'[Chatbot DEBUG] SYSTEM PROMPT: {system_prompt.content}')
    print(f'[Chatbot DEBUG] USER PROMPT: {user_prompt.content}')
    # Get response from LLM
    response = await litellm_completion(
        messages=[system_prompt, user_prompt],
        temperature=0.7
    )

    print(f"[Chatbot DEBUG] RESPONSE: {response.content}")

    return {"messages": [response]}
