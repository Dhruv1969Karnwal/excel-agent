"""Coding Agent node for executing Python code to analyze data (Excel, Documents, PowerPoint)."""

from typing import Any, Dict, List, Sequence

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from my_agent.helpers.sandbox import PLOTS_DIR
from my_agent.models.state import AnalysisStep, CodingSubgraphState
from my_agent.pipelines.registry import registry
# Fallback prompts for backward compatibility
from my_agent.prompts.prompts import CODING_AGENT_SYS_PROMPT, CODING_AGENT_USER_PROMPT
from my_agent.tools.tools import bash_tool, python_repl_tool, think_tool, document_search_tool

import json
from pprint import pprint

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
    2. Gets pipeline-specific prompts based on asset type
    3. Uses an LLM with tool-calling to write and execute Python code
    4. Analyzes the results and iterates if needed
    5. Returns the final analysis results

    Supports all asset types (Excel, Document, PowerPoint).

    Args:
        state: Current state containing analysis_plan, data_context, file_path

    Returns:
        Dictionary with execution_result and messages updates
    """
    code_iterations = state.get("code_iterations", 0)
    print(f"[Coding Agent DEBUG inside coding_agent_node] Coding Agent: Starting iteration {state.get('code_iterations', 0) + 1}...")

    # Display step progress if available
    analysis_steps = state.get("analysis_steps", [])
    if analysis_steps:
        print("[Coding Agent DEBUG inside coding_agent_node] Current Analysis Progress:")
        for step in state["analysis_steps"]:
            status = "[DONE]" if step["status"] == "completed" else "[TODO]"
            print(f"   {status} {step['order']}. {step['description']}")

    # Initialize LLM with tool calling
    from my_agent.core.llm_client import litellm_completion
    from my_agent.tools.tools import bash_tool, python_repl_tool, think_tool, document_search_tool

    tools = [python_repl_tool, think_tool, bash_tool, document_search_tool]


    # Get file path (support both new and legacy fields)
    file_path = state.get("file_path") or state.get("excel_file_path", "")
    asset_type = state.get("asset_type", "excel")
    kbid = state.get("kbid")

    
    # Get pipeline-specific prompts based on asset type
    try:
        if file_path:
            pipeline = registry.get_pipeline_for_file(file_path)
            coding_sys_prompt = pipeline.get_coding_system_prompt()
            coding_user_prompt_template = pipeline.get_coding_user_prompt()
            print(f"[Coding Agent DEBUG inside coding_agent_node] Using {pipeline.name} pipeline prompts for coding")
        else:
            coding_sys_prompt = CODING_AGENT_SYS_PROMPT
            coding_user_prompt_template = CODING_AGENT_USER_PROMPT
            print("[Coding Agent DEBUG inside coding_agent_node] Using default prompts for coding")
        
        # Override prompts if this is a RAG-based document (detected by kbid presence)
        if asset_type == "document" and kbid and not file_path:
            # Re-fetch document pipeline to be sure
            pipeline = registry.get_pipeline_by_name("Document")
            coding_sys_prompt = pipeline.get_coding_system_prompt()
            coding_user_prompt_template = pipeline.get_coding_user_prompt()
            print(f"[Coding Agent DEBUG inside coding_agent_node] Forcing RAG Document prompts for KBID: {kbid}")

    except Exception as e:
        print(f"[Coding Agent DEBUG inside coding_agent_node] Could not get pipeline prompts: {e}, using defaults")
        coding_sys_prompt = CODING_AGENT_SYS_PROMPT
        coding_user_prompt_template = CODING_AGENT_USER_PROMPT

    # Prepare the messages
    system_prompt = SystemMessage(content=coding_sys_prompt)

    if code_iterations == 0:
        # First iteration: send system prompt + user query + analysis prompt
        # Include original user query for context
        user_query = state.get("user_query", "Analyze the data")
        user_query_msg = HumanMessage(content=f"User Request: {user_query}")

        # Extract data context description from structured dict
        data_context_dict = state.get("data_context")
        data_context_str = ""
        full_text = ""
        slides = []
        if data_context_dict:
            data_context_str = data_context_dict.get("description", "")
            full_text = data_context_dict.get("full_text", "")  # For documents/pptx
            slides = data_context_dict.get("slides", [])  # For pptx
        
        # Build format arguments based on what's available in the template
        format_args = {
            "analysis_plan": state.get("analysis_plan", ""),
            "data_context": data_context_str,
            "file_path": file_path,
            "plots_dir": str(PLOTS_DIR),
            "kbid": kbid or "N/A",
            # Backward compatibility for Excel-specific template
            "excel_file_path": file_path,
        }

        
        # Add optional format args for documents/pptx
        if full_text:
            format_args["full_text"] = full_text
        if slides:
            format_args["slide_count"] = len(slides)
        
        # Format the prompt with available arguments
        try:
            analysis_content = coding_user_prompt_template.format(**format_args)
        except KeyError as e:
            # Some templates might not have all placeholders, use default
            print(f"[WARNING Coding Agent DEBUG inside coding_agent_node] Template missing key {e}, using simple format")
            analysis_content = coding_user_prompt_template.format(
                analysis_plan=state.get("analysis_plan", ""),
                data_context=data_context_str,
                file_path=file_path,
                excel_file_path=file_path,
                plots_dir=str(PLOTS_DIR),
                kbid=kbid or "N/A",
            )

        
        analysis_prompt = HumanMessage(content=analysis_content)
        messages = [system_prompt, user_query_msg, analysis_prompt]
    else:
        # Subsequent iterations: send system prompt + ALL conversation history
        # This includes previous tool calls, tool results, and reflections
        conversation_history = state.get("messages", [])
        messages = [system_prompt] + conversation_history

    print("[Coding Agent DEBUG inside coding_agent_node] Messages:")
    pprint(messages, indent=2)
    # Invoke the LLM
    response = await litellm_completion(
        messages=messages,
        tools=tools,
        temperature=0
    )


    print("[Coding Agent DEBUG inside coding_agent_node] Response:")
    pprint(response, indent=2)

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

    print("[Coding Agent DEBUG inside tool_execution_node] Tool Execution: Executing tool calls...")

    # Get the last message (should be from the coding agent with tool calls)
    last_message = state["messages"][-1]

    # Check if there are tool calls
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        print("[Coding Agent DEBUG inside tool_execution_node] No tool calls found in the last message")
        return {"messages": []}

    tool_messages = []

    # Execute each tool call
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_call_id = tool_call["id"]

        print(f"[Coding Agent DEBUG inside tool_execution_node] Executing tool with tool name is: {tool_name} and tool arguments are {tool_args} and tool call id is {tool_call_id}")

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
                print("[Coding Agent DEBUG inside tool_execution_node] Tool execution successful")
            else:
                print(f"[Coding Agent DEBUG inside tool_execution_node] Tool execution failed: {result.get('error')}")

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
                print("[Coding Agent DEBUG inside tool_execution_node] Bash command executed successfully")
            else:
                print(f"[Coding Agent DEBUG inside tool_execution_node] Bash command failed: {result.get('error')}")

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
            print("[Coding Agent DEBUG inside tool_execution_node] Reflection recorded")

        elif tool_name == "document_search_tool":
            # Execute document_search_tool (RAG)
            result = await document_search_tool.ainvoke(tool_args)

            # Create a tool message with the result
            tool_message = ToolMessage(
                content=str(result),
                tool_call_id=tool_call_id,
                name=tool_name,
            )
            tool_messages.append(tool_message)
            print(f"[Coding Agent DEBUG inside tool_execution_node] Document search complete for: {tool_args.get('query')}")

    print("[Coding Agent DEBUG inside tool_execution_node] Tool execution completed successfully ")

    pprint(tool_messages, indent=2)
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

    print(f"[Coding Agent DEBUG inside should_continue_coding] Routing: Iteration {current_iteration}/{max_iterations}")

    # Hard safety limit - only trigger if agent isn't self-regulating
    if current_iteration >= max_iterations:
        print("[Coding Agent DEBUG inside should_continue_coding] Maximum safety limit reached, forcing finalization...")
        return "finalize"

    # Soft warning if taking too long
    if current_iteration >= 10:
        print("[Coding Agent DEBUG inside should_continue_coding] Notice: High iteration count - consider if analysis can be completed")

    # Check if the last message has tool calls
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        num_tool_calls = len(last_message.tool_calls)
        tool_names = [tc["name"] for tc in last_message.tool_calls]
        print(f"[Coding Agent DEBUG inside should_continue_coding] 🔧 Found {num_tool_calls} tool call(s): {tool_names}")
        return "execute_tools"

    # If it's an AI message without tool calls, it's likely the final analysis
    if isinstance(last_message, AIMessage):
        print("[Coding Agent DEBUG inside should_continue_coding] ✅ No tool calls found, finalizing analysis...")
        return "finalize"

    # Otherwise, continue
    print("[Coding Agent DEBUG inside should_continue_coding] 🔄 Continuing to coding agent...")
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

    print("[Coding Agent DEBUG inside finalize_analysis_node] Finalizing analysis and extracting artifacts...")

    # Collect all artifacts from tool executions
    internal_messages = state["messages"]
    print("[Coding Agent DEBUG inside finalize_analysis_node] Processing {len(internal_messages)} internal messages for artifacts and messages is ")
    pprint(internal_messages, indent=2)
    artifacts = []
    tool_messages = [
        msg for msg in state["messages"]
        if isinstance(msg, ToolMessage) and msg.name == "python_repl_tool"
    ]
    print("[Coding Agent DEBUG inside finalize_analysis_node] Tool messages is ")
    pprint(tool_messages, indent=2)
    # Extract plots and tables from tool executions
    for tool_msg in tool_messages:
        try:
            import ast
            # Tool messages contain dict as string, parse it
            content_str = str(tool_msg.content)
            
            # Use safe evaluation to get the dictionary
            try:
                result_dict = ast.literal_eval(content_str)
                print("[Coding Agent DEBUG inside finalize_analysis_node] Result dict is ")
                pprint(result_dict, indent=2)
            except (ValueError, SyntaxError):
                # If evaluation fails, it might be raw output or partial string
                print("[Coding Agent DEBUG inside finalize_analysis_node] Could not parse tool message content: ")
                pprint(content_str[:100])
                continue

            if not isinstance(result_dict, dict):
                continue

            # Add plots as artifacts
            if result_dict.get("plots"):
                for plot_path in result_dict["plots"]:
                    # Avoid duplicates
                    if not any(a["content"] == plot_path for a in artifacts if a["type"] == "plot"):
                        artifacts.append({
                            "type": "plot",
                            "content": plot_path,
                            "description": f"Generated plot: {Path(plot_path).name}",
                            "timestamp": datetime.now().isoformat()
                        })

            # Add tables as artifacts
            if result_dict.get("tables"):
                for table in result_dict["tables"]:
                    # Avoid duplicates
                    table_id = f"table_{table.get('name')}"
                    if not any(a.get("id") == table_id for a in artifacts if a["type"] == "table"):
                        artifacts.append({
                            "type": "table",
                            "id": table_id,
                            "content": table["markdown"],
                            "description": f"DataFrame '{table['name']}' (shape: {table['shape']})",
                            "timestamp": datetime.now().isoformat()
                        })
        except Exception as e:
            print(f"[Coding Agent DEBUG inside finalize_analysis_node] Warning : Unexpected error parsing artifacts: {e}")
            continue

    # Get the last AI message content
    ai_messages = [msg for msg in state["messages"] if isinstance(msg, AIMessage)]
    
    # Check if we have a good conversational summary
    final_analysis_text = ""
    needs_conversational_cleanup = True
    
    if ai_messages:
        last_ai_content = ai_messages[-1].content
        # If it's a long message without tool calls, it might be a good summary
        if len(last_ai_content) > 200 and not hasattr(ai_messages[-1], "tool_calls"):
            final_analysis_text = last_ai_content
            needs_conversational_cleanup = False
            print("[Coding Agent DEBUG inside finalize_analysis_node] Using existing AI message as final analysis")

    if needs_conversational_cleanup:
        print("[Coding Agent DEBUG inside finalize_analysis_node] Generating a conversational summary of findings...")
        from my_agent.core.llm_client import litellm_completion
        
        # Prepare a prompt for the cleanup call
        cleanup_system = SystemMessage(content=(
            "You are a helpful Data Analysis Assistant. Your task is to provide a clear, "
            "conversational, and professional summary of the analysis findings based on "
            "the provided execution history. Highlight key numbers, trends, and conclusions. "
            "Do not talk about the code or technical implementation details unless relevant. "
            "Just interpret the results for the user."
        ))
        
        # Include the original query and the tool results
        history_summary = ""
        for msg in state["messages"][-10:]: # Look at recent history
            if isinstance(msg, HumanMessage):
                history_summary += f"User: {msg.content}\n"
            elif isinstance(msg, AIMessage) and msg.content:
                history_summary += f"Assistant: {msg.content[:500]}...\n"
            elif isinstance(msg, ToolMessage):
                history_summary += f"Tool Result: {str(msg.content)[:1000]}...\n"
        
        cleanup_user = HumanMessage(content=(
            f"Based on this history, please provide a final conversational summary:\n\n{history_summary}"
        ))
        print("[Coding Agent DEBUG inside finalize_analysis_node] Cleanup user is ")
        pprint(cleanup_user, indent=2)
        print("[Coding Agent DEBUG inside finalize_analysis_node] Cleanup system is ")
        pprint(cleanup_system, indent=2)
        try:
            cleanup_response = await litellm_completion(
                messages=[cleanup_system, cleanup_user],
                temperature=0.2
            )
            final_analysis_text = str(cleanup_response.content)
            print(f"[Coding Agent DEBUG inside finalize_analysis_node] Generated conversational summary: {len(final_analysis_text)} chars and full resposne is {final_analysis_text}")
        except Exception as e:
            print(f"[Coding Agent DEBUG inside finalize_analysis_node] Failed to generate cleanup summary: {e}")
            # Fallback to internal compilation if LLM fails
            if tool_messages:
                final_analysis_text = "## Analysis Results\n\n"
                for i, msg in enumerate(tool_messages[-3:], 1):
                    final_analysis_text += f"### Results from Step {i}\n{msg.content}\n\n"
            else:
                final_analysis_text = "Analysis completed but no conversational summary was generated."

    # Add insights as an artifact
    artifacts.append({
        "type": "insight",
        "content": final_analysis_text,
        "description": "Final analysis and findings",
        "timestamp": datetime.now().isoformat()
    })
    print(f"[Coding Agent DEBUG inside finalize_analysis_node] Analysis finalized. Length: {len(final_analysis_text)} characters.")
    print(f"[Coding Agent DEBUG inside finalize_analysis_node] Extracted {len(artifacts)} artifacts (plots, tables, insights)")
    for art in artifacts:
        print(f"  - [{art['type'].upper()}] {art['description']}")

    from pathlib import Path

    # Ensure final_analysis_text is a string
    final_analysis_str = str(final_analysis_text) if final_analysis_text else "Analysis completed."
    message_content = final_analysis_str + "\n\n"

    # List plot file paths (plots are saved locally, no base64 embedding)
    plot_artifacts = [a for a in artifacts if a["type"] == "plot"]
    if plot_artifacts:
        message_content += "## Generated Plots\n\n"
        message_content += "Plots have been saved locally:\n\n"

        for plot_artifact in plot_artifacts:
            plot_path = plot_artifact["content"]
            plot_name = Path(plot_path).name
            message_content += f"- **{plot_name}**: `{plot_path}`\n"

        message_content += "\n"

    # Add tables as markdown
    table_artifacts = [a for a in artifacts if a["type"] == "table"]
    if table_artifacts:
        message_content += "## Data Tables\n\n"
        for table_artifact in table_artifacts:
            message_content += f"### {table_artifact['description']}\n\n"
            message_content += table_artifact["content"] + "\n\n"

    # Create AI message with plot references and tables
    final_message = AIMessage(content=message_content, name="CodingAgent")

    print("[Coding Agent DEBUG inside finalize_analysis_node] Final message is ")
    pprint(final_message, indent=2)
    return {
        "final_analysis": message_content,
        "artifacts": artifacts,  # Return artifacts to be merged into parent state
        "messages": [final_message],  # This clean message with embedded images goes to parent
    }
