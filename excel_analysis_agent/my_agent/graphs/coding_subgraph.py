"""Coding Agent Subgraph - Handles code execution and iteration."""

from langgraph.graph import END, StateGraph

from my_agent.models.state import CodingSubgraphState
from my_agent.nodes.coding_agent import (
    coding_agent_node,
    finalize_analysis_node,
    should_continue_coding,
    tool_execution_node,
)
from my_agent.nodes.dispatcher import task_dispatcher_node


def create_coding_subgraph():
    """
    Create the Orchestrator-Worker Coding Agent subgraph.
    
    1. Dispatcher: Picks the next step.
    2. Coding Agent: Specialized worker for that step.
    3. Tool Execution: Runs tools.
    4. Loop: Goes back to Dispatcher after each step complete.
    """
    # Initialize the subgraph with isolated state
    workflow = StateGraph(CodingSubgraphState)

    # Add nodes
    workflow.add_node("dispatcher", task_dispatcher_node)
    workflow.add_node("coding_agent", coding_agent_node)
    workflow.add_node("execute_tools", tool_execution_node)
    workflow.add_node("finalize", finalize_analysis_node)

    # Set entry point
    workflow.set_entry_point("dispatcher")

    # Routing from Dispatcher
    def route_from_dispatcher(state: CodingSubgraphState):
        if state.get("active_step_index", -1) == -1:
            return "finalize"
        return "coding_agent"

    workflow.add_conditional_edges(
        "dispatcher",
        route_from_dispatcher,
        {
            "coding_agent": "coding_agent",
            "finalize": "finalize"
        }
    )

    # Routing from coding_agent
    workflow.add_conditional_edges(
        "coding_agent",
        should_continue_coding,
        {
            "execute_tools": "execute_tools",
            "finalize": "finalize", # Fallback for legacy
            "finalize_step": "execute_tools", # We execute the 'complete_step' tool
            "continue": "coding_agent",
        },
    )

    # After tool execution
    def route_after_tools(state: CodingSubgraphState):
        # Check if the last tool executed was 'complete_step'
        last_msg = state["messages"][-1]
        if hasattr(last_msg, "name") and last_msg.name == "complete_step":
            return "dispatcher"
        return "coding_agent"

    workflow.add_conditional_edges(
        "execute_tools",
        route_after_tools,
        {
            "dispatcher": "dispatcher",
            "coding_agent": "coding_agent"
        }
    )

    # After finalization, end the subgraph
    workflow.add_edge("finalize", END)

    return workflow.compile()
