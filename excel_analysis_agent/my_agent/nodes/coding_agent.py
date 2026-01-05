"""Coding Agent node for executing Python code to analyze Excel data."""

from typing import Any, Dict, List, Sequence

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from my_agent.helpers.sandbox import PLOTS_DIR
from my_agent.models.state import AnalysisStep, CodingSubgraphState
from my_agent.prompts.prompts import CODING_AGENT_SYS_PROMPT, CODING_AGENT_USER_PROMPT
from my_agent.tools.tools import bash_tool, python_repl_tool, think_tool


def display_step_progress(steps: Sequence[AnalysisStep]) -> None:
    """
    Display current progress of analysis steps.

    Args:
        steps: List of analysis steps with status
    """
    if not steps:
        return

    print("\n📋 Analysis Progress:")
    for step in steps:
        status = step.get("status", "pending")
        order = step.get("order", 0)
        description = step.get("description", "")

        if status == "completed":
            icon = "✅"
        elif status == "in_progress":
            icon = "🔄"
        elif status == "skipped":
            icon = "⏭️"
        else:
            icon = "⬜"

        print(f"   {icon} {order}. {description}")
    print()


async def coding_agent_node(state: CodingSubgraphState) -> Dict[str, Any]:
    """
    Coding Agent Node - Executes Python code to perform data analysis.

    This node:
    1. Takes the analysis plan from the supervisor
    2. Uses an LLM with tool-calling to write and execute Python code
    3. Analyzes the results and iterates if needed
    4. Returns the final analysis results

    Args:
        state: Current state containing analysis_plan, data_context, excel_file_path

    Returns:
        Dictionary with execution_result and messages updates
    """
    code_iterations = state.get("code_iterations", 0)
    print(f"[ACTION] Coding Agent: Starting iteration {state.get('code_iterations', 0) + 1}...")

    # Display step progress if available
    analysis_steps = state.get("analysis_steps", [])
    if analysis_steps:
        print("[DEBUG] Current Analysis Progress:")
        for step in state["analysis_steps"]:
            status = "[DONE]" if step["status"] == "completed" else "[TODO]"
            print(f"   {status} {step['order']}. {step['description']}")

    # Initialize LLM with tool calling
    from my_agent.core.llm_client import litellm_completion
    from my_agent.tools.tools import bash_tool, python_repl_tool, think_tool

    # Prepare the messages
    system_prompt = SystemMessage(content=CODING_AGENT_SYS_PROMPT)

    if code_iterations == 0:
        # First iteration: send system prompt + user query + analysis prompt
        # Include original user query for context
        user_query = state.get("user_query", "Analyze the data")
        user_query_msg = HumanMessage(content=f"User Request: {user_query}")

        # Extract data context description from structured dict
        data_context_dict = state.get("data_context")
        data_context_str = ""
        if data_context_dict:
            data_context_str = data_context_dict.get("description", "")

        analysis_prompt = HumanMessage(
            content=CODING_AGENT_USER_PROMPT.format(
                analysis_plan=state.get("analysis_plan", ""),
                data_context=data_context_str,
                excel_file_path=state.get("excel_file_path", ""),
                plots_dir=str(PLOTS_DIR),
            )
        )
        messages = [system_prompt, user_query_msg, analysis_prompt]
    else:
        # Subsequent iterations: send system prompt + ALL conversation history
        # This includes previous tool calls, tool results, and reflections
        conversation_history = state.get("messages", [])
        messages = [system_prompt] + conversation_history

    # Invoke the LLM
    response = await litellm_completion(
        messages=messages,
        tools=[python_repl_tool, bash_tool, think_tool],
        temperature=0
    )

    print("✅ Coding Agent: Received response from LLM")

    # Add the response to messages
    return {
        "messages": [response],
        "code_iterations": state.get("code_iterations", 0) + 1,
    }


async def tool_execution_node(state: CodingSubgraphState) -> Dict[str, Any]:
    """
    Tool Execution Node - Executes the tools called by the coding agent.

    This node:
    1. Extracts tool calls from the last AI message
    2. Executes each tool call asynchronously (runs blocking code in thread pool)
    3. Returns the results as tool messages

    Args:
        state: Current state containing messages with tool calls

    Returns:
        Dictionary with messages containing tool results
    """
    from langchain_core.messages import ToolMessage

    print("🔧 Tool Execution: Executing tool calls...")

    # Get the last message (should be from the coding agent with tool calls)
    last_message = state["messages"][-1]

    # Check if there are tool calls
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        print("⚠️ No tool calls found in the last message")
        return {"messages": []}

    tool_messages = []

    # Execute each tool call
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_call_id = tool_call["id"]

        print(f"🔧 Executing tool: {tool_name}")

        # Execute the appropriate tool asynchronously
        if tool_name == "python_repl_tool":
            # Use ainvoke to run the blocking exec() call in a thread pool
            result = await python_repl_tool.ainvoke(tool_args)

            # Create a tool message with the result
            tool_message = ToolMessage(
                content=str(result),
                tool_call_id=tool_call_id,
                name=tool_name,
            )
            tool_messages.append(tool_message)

            # Store execution result in state
            if result.get("success"):
                print("✅ Tool execution successful")
            else:
                print(f"❌ Tool execution failed: {result.get('error')}")

        elif tool_name == "bash_tool":
            # Execute bash_tool for package installation
            result = await bash_tool.ainvoke(tool_args)

            # Create a tool message with the result
            tool_message = ToolMessage(
                content=str(result),
                tool_call_id=tool_call_id,
                name=tool_name,
            )
            tool_messages.append(tool_message)

            # Log installation result
            if result.get("success"):
                print("✅ Bash command executed successfully")
            else:
                print(f"❌ Bash command failed: {result.get('error')}")

        elif tool_name == "think_tool":
            # Execute think_tool for reflection (lightweight, no need for thread pool)
            result = await think_tool.ainvoke(tool_args)

            # Create a tool message with the result
            tool_message = ToolMessage(
                content=str(result),
                tool_call_id=tool_call_id,
                name=tool_name,
            )
            tool_messages.append(tool_message)
            print("✅ Reflection recorded")

    return {"messages": tool_messages}


def should_continue_coding(state: CodingSubgraphState) -> str:
    """
    Routing function to determine if coding agent should continue or finish.

    Checks if:
    1. The last message has tool calls (continue to tool execution)
    2. Maximum iterations reached (end) - soft limit, agent should self-regulate
    3. No tool calls and valid response (end)

    Args:
        state: Current state

    Returns:
        "execute_tools" if there are tool calls to execute
        "finalize" if the coding is complete
        "continue" if the agent should continue reasoning
    """
    last_message = state["messages"][-1]
    max_iterations = 40  # Safety limit - increased for complex analyses with package installation
    current_iteration = state.get("code_iterations", 0)

    print(f"🔀 Routing: Iteration {current_iteration}/{max_iterations}")

    # Hard safety limit - only trigger if agent isn't self-regulating
    if current_iteration >= max_iterations:
        print("⚠️ Maximum safety limit reached, forcing finalization...")
        return "finalize"

    # Soft warning if taking too long
    if current_iteration >= 10:
        print("⚠️ Notice: High iteration count - consider if analysis can be completed")

    # Check if the last message has tool calls
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        num_tool_calls = len(last_message.tool_calls)
        tool_names = [tc["name"] for tc in last_message.tool_calls]
        print(f"🔧 Found {num_tool_calls} tool call(s): {tool_names}")
        return "execute_tools"

    # If it's an AI message without tool calls, it's likely the final analysis
    if isinstance(last_message, AIMessage):
        print("✅ No tool calls found, finalizing analysis...")
        return "finalize"

    # Otherwise, continue
    print("🔄 Continuing to coding agent...")
    return "continue"


async def finalize_analysis_node(state: CodingSubgraphState) -> Dict[str, Any]:
    """
    Finalize Analysis Node - Creates the final analysis summary with structured artifacts.

    This node:
    1. Reviews all execution results and extracts findings
    2. Collects all artifacts (plots, tables, code) from tool executions
    3. Creates a comprehensive structured analysis
    4. Returns artifacts and clean message for the parent graph

    Args:
        state: Current state with all execution history

    Returns:
        Dictionary with final_analysis, artifacts, and a clean message for parent
    """
    from datetime import datetime
    from langchain_core.messages import ToolMessage

    print("[ACTION] Finalizing analysis and extracting artifacts...")

    # Collect all artifacts from tool executions
    internal_messages = state["messages"]
    print(f"[DEBUG] Processing {len(internal_messages)} internal messages for artifacts.")
    artifacts = []
    tool_messages = [
        msg for msg in state["messages"]
        if isinstance(msg, ToolMessage) and msg.name == "python_repl_tool"
    ]

    # Extract plots and tables from tool executions
    for tool_msg in tool_messages:
        try:
            import ast
            # Tool messages contain dict as string, parse it
            content_str = str(tool_msg.content)
            result_dict = ast.literal_eval(content_str)

            # Add plots as artifacts
            if result_dict.get("plots"):
                for plot_path in result_dict["plots"]:
                    artifacts.append({
                        "type": "plot",
                        "content": plot_path,
                        "description": f"Generated plot: {plot_path.split('/')[-1]}",
                        "timestamp": datetime.now().isoformat()
                    })

            # Add tables as artifacts
            if result_dict.get("tables"):
                for table in result_dict["tables"]:
                    artifacts.append({
                        "type": "table",
                        "content": table["markdown"],
                        "description": f"DataFrame '{table['name']}' (shape: {table['shape']})",
                        "timestamp": datetime.now().isoformat()
                    })
        except Exception as e:
            print(f"Warning: Could not parse tool message for artifacts: {e}")
            continue

    # Get the last AI message which should contain the final analysis text
    ai_messages = [msg for msg in state["messages"] if isinstance(msg, AIMessage)]

    if ai_messages and ai_messages[-1].content:
        final_analysis_text = ai_messages[-1].content
        print(f"✅ Analysis finalized: {len(final_analysis_text)} characters")
    else:
        # Fallback: compile from tool execution results
        print("⚠️ No AI message found, compiling from execution history...")

        if tool_messages:
            final_analysis_text = "## Analysis Results\n\n"
            for i, msg in enumerate(tool_messages[-3:], 1):  # Last 3 executions
                final_analysis_text += f"### Execution {i}\n{msg.content}\n\n"
        else:
            final_analysis_text = "Analysis completed but no results were captured."

    # Add insights as an artifact
    artifacts.append({
        "type": "insight",
        "content": final_analysis_text,
        "description": "Final analysis and findings",
        "timestamp": datetime.now().isoformat()
    })
    print(f"[DEBUG] Analysis finalized. Length: {len(final_analysis_text)} characters.")
    print(f"[DEBUG] Extracted {len(artifacts)} artifacts (plots, tables, insights)")
    for art in artifacts:
        print(f"  - [{art['type'].upper()}] {art['description']}")

    from pathlib import Path

    # Ensure final_analysis_text is a string
    final_analysis_str = str(final_analysis_text) if final_analysis_text else "Analysis completed."
    message_content = final_analysis_str + "\n\n"

    # List plot file paths (plots are saved locally, no base64 embedding)
    plot_artifacts = [a for a in artifacts if a["type"] == "plot"]
    if plot_artifacts:
        message_content += "## 📊 Generated Plots\n\n"
        message_content += "Plots have been saved locally:\n\n"

        for plot_artifact in plot_artifacts:
            plot_path = plot_artifact["content"]
            plot_name = Path(plot_path).name
            message_content += f"- **{plot_name}**: `{plot_path}`\n"

        message_content += "\n"

    # Add tables as markdown
    table_artifacts = [a for a in artifacts if a["type"] == "table"]
    if table_artifacts:
        message_content += "## 📋 Data Tables\n\n"
        for table_artifact in table_artifacts:
            message_content += f"### {table_artifact['description']}\n\n"
            message_content += table_artifact["content"] + "\n\n"

    # Create AI message with plot references and tables
    final_message = AIMessage(content=message_content, name="CodingAgent")

    return {
        "final_analysis": message_content,
        "artifacts": artifacts,  # Return artifacts to be merged into parent state
        "messages": [final_message],  # This clean message with embedded images goes to parent
    }
