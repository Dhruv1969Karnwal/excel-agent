"""Follow-up answer node for answering questions from existing analysis context."""

from typing import Any, Dict

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from my_agent.core.infisical_client import get_secret
from my_agent.models.state import ExcelAnalysisState
from my_agent.prompts.prompts import FOLLOWUP_ANSWER_SYS_PROMPT, FOLLOWUP_ANSWER_USER_PROMPT


async def followup_answer_node(state: ExcelAnalysisState) -> Dict[str, Any]:
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
    print("💡 Follow-up Answer: Answering from existing context...")

    # Initialize LLM
    llm = init_chat_model(
        model="gpt-4o", api_key=get_secret("OPENAI_API_KEY"), temperature=0
    )

    # Get the user's query
    user_messages = [msg for msg in state["messages"] if isinstance(msg, HumanMessage)]
    user_query = user_messages[-1].content if user_messages else "Please provide more details"

    # Get data context
    data_context_dict = state.get("data_context")
    data_context = ""
    if data_context_dict:
        data_context = data_context_dict.get("description", "No data description available")

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

    # Get response
    response = await llm.ainvoke([system_prompt, user_prompt])

    print(f"✅ Follow-up Answer: Response generated")

    # Create AI message
    answer_message = AIMessage(
        content=response.content,
        name="FollowupAssistant"
    )

    return {
        "messages": [answer_message]
    }
