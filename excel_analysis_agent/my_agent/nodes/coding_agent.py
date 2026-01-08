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
from pathlib import Path

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
    # Initialize LLM with tool calling
    from my_agent.core.llm_client import litellm_completion
    from my_agent.tools.tools import bash_tool, python_repl_tool, think_tool, document_search_tool
    from langchain_core.tools import tool

    @tool
    def complete_step(summary: str) -> str:
        """
        Mark the current analysis step as complete.
        
        Call this tool ONLY when you have successfully finished the current assigned step.
        Provide a brief summary of what was achieved and any key results/values found.
        
        Args:
           summary: A concise summary of the step's result (e.g., "Loaded data, found 150 rows").
        """
        return "Step marked as complete."

    tools = [python_repl_tool, think_tool, bash_tool, document_search_tool, complete_step]


    # Check if we are in Dispatcher mode (active_step_index >= 0)
    active_step_index = state.get("active_step_index", -1)
    
    if active_step_index >= 0 and code_iterations == 0:
        # Dispatcher has already set the correct system and user prompts
        print(f"[Coding Agent] Dispatcher mode active for Step Index {active_step_index}. Using provided prompts.")
        messages = state.get("messages", [])
    
    elif code_iterations == 0:
        # LEGACY MODE: Build prompts manually if no dispatcher (backward compatibility)
        
        # Get file path (support both new and legacy fields)
        file_path = state.get("file_path") or state.get("excel_file_path", "")
        asset_type = state.get("asset_type", "excel")
        kbid = state.get("kbid")
    
        
        # Get data contexts (plural)
        data_contexts = state.get("data_contexts") or {}
        
        # Prioritize Excel for coding prompts
        primary_asset_id = None
        excel_assets = [aid for aid in data_contexts if registry.is_supported(aid) and registry.get_pipeline_for_file(aid).name == "Excel"]
        
        if excel_assets:
            primary_asset_id = excel_assets[0]
        elif data_contexts:
            primary_asset_id = list(data_contexts.keys())[0]
        else:
            primary_asset_id = state.get("file_path") or state.get("excel_file_path", "")
    
        # Determine involved asset types from data contexts
        asset_types = set()
        for ctx in data_contexts.values():
            dtype = ctx.get("document_type", "").lower()
            if "excel" in dtype or "csv" in dtype:
                asset_types.add("Excel")
            elif "codebase" in dtype:
                asset_types.add("Codebase")
            elif "powerpoint" in dtype:
                asset_types.add("PowerPoint")
            else:
                asset_types.add("Document")
    
        # Select Pipeline Prompts
        # Case 1: Single Asset Type -> Use that pipeline's specific prompts
        if len(asset_types) == 1:
            target_type = list(asset_types)[0]
            try:
                pipeline = registry.get_pipeline_by_name(target_type)
                coding_sys_prompt = pipeline.get_coding_system_prompt()
                coding_user_prompt_template = pipeline.get_coding_user_prompt()
                print(f"[Coding Agent] Using {pipeline.name} pipeline prompts for coding")
            except Exception as e:
                print(f"[Coding Agent] Could not get pipeline prompts for {target_type}: {e}, using defaults")
                coding_sys_prompt = CODING_AGENT_SYS_PROMPT
                coding_user_prompt_template = CODING_AGENT_USER_PROMPT
    
        # Case 2: Mixed Asset Types -> Dynamically Merge Prompts
        elif len(asset_types) > 1:
            print(f"[Coding Agent] Mixed asset types detected {asset_types}. Merging prompts dynamically.")
            
            sys_instructions = []
            for dtype in asset_types:
                try:
                    pipeline = registry.get_pipeline_by_name(dtype)
                    # Extract core capabilities/instructions from the specialist prompt
                    sys_instructions.append(f"--- Instructions for {dtype} Operations ---\n{pipeline.get_coding_system_prompt()}")
                except:
                    pass
            
            # Combine specialized instructions
            header = "You are a Multi-Asset Coding Agent. You must combine the capabilities of the following specialists:"
            coding_sys_prompt = f"{header}\n\n" + "\n\n".join(sys_instructions)
            
            # IMPORTANT: When mixed, ALWAYS append the strong Agentic Looping instructions 
            # (usually found in the Excel/Global prompt) to ensure it doesn't stop early.
            agentic_loop_instructions = """
    --- CRITICAL AGENTIC INSTRUCTIONS ---
    1. FOLLOW THE ANALYSIS PLAN: You MUST execute the provided plan step-by-step.
    2. DO NOT STOP EARLY: You are in an iterative loop. After each tool call, check if the ENTIRE plan is complete.
    3. LOOPING: If there are pending steps in the plan, continue with more tool calls in the NEXT iteration.
    4. THINKING: Use the `think_tool` after every significant tool result to evaluate progress against the plan.
    5. FINAL RESPONSE: Only provide the final analysis once ALL steps of the plan are successfully finished.
    """
            coding_sys_prompt += agentic_loop_instructions
            coding_user_prompt_template = CODING_AGENT_USER_PROMPT
        
        # Case 3: Fallback (no assets or unknown)
        else:
            print("[Coding Agent] Using Global prompts for coding")
            coding_sys_prompt = CODING_AGENT_SYS_PROMPT
            coding_user_prompt_template = CODING_AGENT_USER_PROMPT
    
        # Prepare the messages
        system_prompt = SystemMessage(content=coding_sys_prompt)
    
        # First iteration: send system prompt + user query + analysis prompt
        # Include original user query for context
        user_query = state.get("user_query", "Analyze the data")
        user_query_msg = HumanMessage(content=f"User Request: {user_query}")
    
        # Aggregate contexts for prompt
        full_data_context_str = ""
        context_parts = []
        full_texts = []
        slide_counts = []
        
        for aid, ctx in data_contexts.items():
            desc = ctx.get("description", "")
            context_parts.append(f"### Asset: {aid} ###\n{desc}")
            if ctx.get("full_text"):
                full_texts.append(f"### Full Text: {aid} ###\n{ctx['full_text']}")
            if ctx.get("slides"):
                slide_counts.append(f"{aid}: {len(ctx['slides'])} slides")
        
        full_data_context_str = "\n\n".join(context_parts)
        combined_full_text = "\n\n".join(full_texts)
        combined_slide_count_str = ", ".join(slide_counts)
        
        # Build format arguments based on what's available in the template
        format_args = {
            "analysis_plan": state.get("analysis_plan", ""),
            "data_context": full_data_context_str,
            "file_path": primary_asset_id or "N/A",
            "plots_dir": str(PLOTS_DIR),
            "kbid": kbid or "N/A",
            "excel_file_path": primary_asset_id or "N/A",
            "full_text": combined_full_text or "N/A",
            "slide_count": combined_slide_count_str or "0",
        }
    
        # Format the prompt with available arguments
        try:
            # We use string template formatting but need to be careful with extra braces in prompts
            # For simplicity, we'll try to match the expected keys
            analysis_content = coding_user_prompt_template.format(**format_args)
        except KeyError as e:
            print(f"[WARNING Coding Agent] Template missing key {e}, using partial format")
            # Minimal required keys for most templates
            analysis_content = coding_user_prompt_template.replace("{analysis_plan}", format_args["analysis_plan"])
            analysis_content = analysis_content.replace("{data_context}", format_args["data_context"])
            analysis_content = analysis_content.replace("{file_path}", format_args["file_path"])
        
        analysis_prompt = HumanMessage(content=analysis_content)
        messages = [system_prompt, user_query_msg, analysis_prompt]
    
    else:
        # Subsequent iterations: send system prompt + ALL conversation history
        # but for Dispatcher mode we need to preserve the system prompt from iteration 0
        if len(state["messages"]) > 0 and isinstance(state["messages"][0], SystemMessage):
             system_prompt = state["messages"][0]
        else:
             # Fallback
             system_prompt = SystemMessage(content=CODING_AGENT_SYS_PROMPT)
             
        conversation_history = state.get("messages", [])
        # Avoid duplicating system prompt if it's already in history?
        # Typically state["messages"] accumulates.
        # But if we rebuilt 'messages' in Dispatcher, state["messages"] HAS the system prompt.
        # So we just pass state["messages"].
        
        # WAIT: In the original code:
        # messages = [system_prompt] + conversation_history
        # Because `CodingSubgraphState` uses `add_messages`.
        # So `state["messages"]` contains ALL history.
        # But `system_prompt` is usually NOT in `state["messages"]` (it's ephemeral in the node).
        # EXCEPT in my Dispatcher I explicitly put SystemMessage in `messages`.
        # So if Dispatcher mode: Just use `state.get("messages")`.
        
        messages = state.get("messages", [])
        
        # If legacy mode, we might need to prepend system prompt...
        # Actually, let's keep it simple:
        # If active_step_index is set, trust state['messages'].
        if active_step_index == -1:
             # Re-instantiate system prompt for legacy
             # ... (This is tricky to reconstruct perfectly without the logic block above)
             # Ideally we persist system prompt in state or just handle it.
             # For now, let's assume legacy flow re-runs the logic or we just grab CODING_AGENT_SYS_PROMPT
             # The original code re-ran the logic to get `system_prompt`.
             # I should probably refactor the "Get Prompts" logic into a helper function?
             # Or just copy the fallback:
             messages = [SystemMessage(content=CODING_AGENT_SYS_PROMPT)] + conversation_history

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
        if state.get("active_step_index", -1) >= 0:
            from langchain_core.messages import HumanMessage
            return {"messages": [HumanMessage(content="You haven't called any tools. If you are finished with this step, you MUST call 'complete_step(summary=...)'.")]}
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

        elif tool_name == "complete_step":
            # Execute complete_step (State Update)
            result = "Step marked as complete."
            summary = tool_args.get("summary", "Step completed.")
            
            # Update state
            active_step_index = state.get("active_step_index", -1)
            steps = state.get("analysis_steps", [])
            
            if active_step_index >= 0 and active_step_index < len(steps):
                steps[active_step_index]["status"] = "completed"
                steps[active_step_index]["result_summary"] = summary
                print(f"[Tool Execution] Marked Step {active_step_index} as completed.")

            # Create a tool message
            tool_message = ToolMessage(
                content=result,
                tool_call_id=tool_call_id,
                name=tool_name,
            )
            tool_messages.append(tool_message)
            
            # Return updated steps immediately
            print("[Coding Agent DEBUG inside tool_execution_node] Tool execution completed successfully ")
            pprint(tool_messages, indent=2)
            return {
                "messages": tool_messages,
                "analysis_steps": steps
            }

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
        
        # If the agent called complete_step, we go to finalize the STEP (not the whole analysis)
        if "complete_step" in tool_names:
            print("[Coding Agent] Step completion tool called. Routing to dispatcher...")
            return "finalize_step"
            
        return "execute_tools"

    # If it's an AI message without tool calls, it's likely the final analysis summary for the SUB-TASK
    if isinstance(last_message, AIMessage):
        print("[Coding Agent DEBUG inside should_continue_coding] AI sent a direct response.")
        # In Dispatcher mode, if the agent just talks without calling complete_step, 
        # we'll treat it as a "continue" for now to let it try again or prompt it.
        # However, to avoid infinite loop, let's force it to execute_tools with an empty call which we'll trap.
        if state.get("active_step_index", -1) >= 0:
             return "execute_tools"
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
    print(f"[Coding Agent DEBUG inside finalize_analysis_node] Processing {len(internal_messages)} internal messages for artifacts and messages is ")
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
            "You are a helpful Multi-Asset Analysis Assistant. Your task is to provide a clear, "
            "conversational, and professional summary of the analysis findings based on "
            "the provided structured steps results. Highlight key findings from ALL completed tasks, "
            "linking them together into a cohesive narrative (e.g., connecting Excel statistics with "
            "Codebase insights). Do not talk about the code or technical implementation details. "
            "Just interpret the results for the user."
        ))
        
        # Include the original query and the tool results
        #        # Include the results from each completed step (Orchestrator-Worker pattern)
        steps_summary = "### ANALYSIS STEPS SUMMARY ###\n"
        analysis_steps = state.get("analysis_steps", [])
        if analysis_steps:
            for step in analysis_steps:
                if step.get("status") == "completed":
                    steps_summary += f"Step {step['order']}: {step['description']}\nResult Summary: {step.get('result_summary', 'Detailed work completed.')}\n\n"
        else:
            # Fallback for legacy if steps are missing
            steps_summary += "No structured steps found. Relying on recent conversation history.\n"
            for msg in state["messages"][-10:]:
                if isinstance(msg, HumanMessage):
                    steps_summary += f"User: {msg.content}\n"
                elif isinstance(msg, ToolMessage):
                    steps_summary += f"Tool Result: {str(msg.content)[:500]}\n"

        cleanup_user = HumanMessage(content=(
            f"Please provide a final conversational summary of the following analysis results:\n\n{steps_summary}"
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

    # Finalize message content

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
