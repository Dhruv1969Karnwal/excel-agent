from langgraph.graph import END, START, StateGraph

from my_agent.graphs.coding_subgraph import create_coding_subgraph
from my_agent.models.state import ExcelAnalysisState
from my_agent.nodes.chat import chat_node
from my_agent.nodes.data_inspector import data_inspector_node
from my_agent.nodes.followup_answer import followup_answer_node
from my_agent.nodes.planning import planning_node
from my_agent.nodes.router import router_node
from my_agent.nodes.supervisor import supervisor_node


def route_after_router(state: ExcelAnalysisState) -> str:
    """
    Conditional edge function after router_node.

    Routes based on the router's classification and data context validation:
    - "chat" -> chat_node
    - "analysis" -> check if data_inspector needed:
        - If data_context missing or file changed -> data_inspector
        - If data_context exists and file matches -> supervisor
    - "analysis_followup" -> supervisor_node
    """
    import os

    route_decision = state.get("route_decision") or {}
    route = route_decision.get("route", "chat")

    # Route 1: Generic chat
    if route == "chat":
        return "chat"

    # Route 2: Follow-up on previous analysis -> always go to supervisor
    elif route == "analysis_followup":
        return "supervisor"

    # Route 3: New analysis request -> check if data inspection needed
    elif route == "analysis":
        data_context = state.get("data_context")
        excel_file_path = state.get("excel_file_path")

        # No context exists -> need inspection
        if not data_context:
            print("🔍 No data context found, routing to data_inspector")
            return "data_inspector"

        # No file path provided -> need inspection
        if not excel_file_path:
            print("⚠️ No excel_file_path provided, routing to data_inspector")
            return "data_inspector"

        # Check if file path matches (use os.path.abspath to avoid blocking resolve())
        stored_path = data_context.get("file_path", "")
        current_path = os.path.abspath(excel_file_path)

        if stored_path != current_path:
            print("📝 File path changed, routing to data_inspector")
            return "data_inspector"

        print("✅ Data context exists and file matches, routing to supervisor")
        return "supervisor"

    # Default fallback
    return "chat"


def route_after_supervisor(state: ExcelAnalysisState) -> str:
    """
    Conditional edge function after supervisor_node.

    Routes based on supervisor's decision:
    - needs_analysis=True -> planning_node
    - needs_analysis=False -> followup_answer_node
    """
    supervisor_decision = state.get("supervisor_decision", {})
    needs_analysis = supervisor_decision.get("needs_analysis", True)

    if needs_analysis:
        return "planning"
    else:
        return "followup_answer"


def create_excel_analysis_graph():
    """
    Create and compile the Excel Analysis Agent graph with intelligent LLM-based routing.

    NEW ARCHITECTURE:

    Workflow:
    1. START -> router_node (LLM classifies query)

    2. Router conditional routing:
       - "chat": Generic conversation -> chat_node -> END
       - "analysis": New analysis request -> check_data_context
       - "analysis_followup": Follow-up on previous analysis -> supervisor_node

    3. check_data_context (validates file_path):
       - If data_context missing OR file changed -> data_inspector_node
       - If data_context exists AND file matches -> supervisor_node

    4. data_inspector_node -> supervisor_node

    5. supervisor_node (evaluates if new code execution needed):
       - needs_analysis=True -> planning_node
       - needs_analysis=False -> followup_answer_node (answers from context)

    6. planning_node -> coding_subgraph -> END

    7. followup_answer_node -> END

    Key Features:
    - LLM-based query classification with structured output
    - Smart file path validation to skip redundant data inspection
    - Supervisor evaluates if analysis needed or can answer from context
    - Separate planning node for detailed analysis plans
    - Direct answer path for follow-up questions that don't need code
    - Coding subgraph isolation (tool calls don't leak to parent)
    - Artifact accumulation across analysis runs
    - Structured step tracking (TodoList pattern)

    The coding_subgraph is a nested graph that handles:
    - Code generation by the coding agent
    - Tool execution (Python REPL with matplotlib Agg backend)
    - Iteration and error handling
    - Final analysis compilation with structured artifacts
    - Step progress tracking

    Returns:
        Compiled LangGraph workflow
    """
    # Initialize the graph with our custom state
    workflow = StateGraph(ExcelAnalysisState)

    # Add all nodes
    workflow.add_node("router", router_node)
    workflow.add_node("chat", chat_node)
    workflow.add_node("data_inspector", data_inspector_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("planning", planning_node)
    workflow.add_node("followup_answer", followup_answer_node)

    # Add the coding subgraph as a node
    coding_subgraph = create_coding_subgraph()
    workflow.add_node("coding_agent", coding_subgraph)

    # START -> router_node (always start with intelligent routing)
    workflow.add_edge(START, "router")

    # Router conditional routing based on classification and data context validation
    workflow.add_conditional_edges(
        "router",
        route_after_router,
        {
            "chat": "chat",
            "data_inspector": "data_inspector",
            "supervisor": "supervisor",
        },
    )

    # After data inspection, always go to supervisor
    workflow.add_edge("data_inspector", "supervisor")

    # Supervisor conditional routing based on needs_analysis decision
    workflow.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "planning": "planning",
            "followup_answer": "followup_answer",
        },
    )

    # After planning, execute the coding subgraph
    workflow.add_edge("planning", "coding_agent")

    # Terminal edges
    workflow.add_edge("coding_agent", END)
    workflow.add_edge("followup_answer", END)
    workflow.add_edge("chat", END)

    # Compile the graph
    graph = workflow.compile()

    return graph


# Create the graph instance for LangGraph Studio
graph = create_excel_analysis_graph()
