from langgraph.graph import END, START, StateGraph

from my_agent.graphs.coding_subgraph import create_coding_subgraph
from my_agent.models.state import UnifiedAnalysisState
from my_agent.nodes.chat import chat_node
from my_agent.nodes.asset_dispatcher import asset_dispatcher_node
from my_agent.nodes.followup_answer import followup_answer_node
from my_agent.nodes.planning import planning_node
from my_agent.nodes.router import router_node
from my_agent.nodes.supervisor import supervisor_node

# Note: Pipelines are now registered dynamically via the /chat endpoint
# in main.py using process_incoming_request.


def route_after_router(state: UnifiedAnalysisState) -> str:
    """
    Conditional edge function after router_node.

    Routes based on the router's classification and data context validation:
    - "chat" -> chat_node
    - "analysis" -> check if data inspection needed:
        - If data_context missing or file changed -> asset_dispatcher
        - If data_context exists and file matches -> supervisor
    - "analysis_followup" -> supervisor_node
    
    Supports both new file_path and legacy excel_file_path for backward compatibility.
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
    # Route 3: New analysis request -> check if data inspection needed
    elif route == "analysis":
        # Multi-Asset Validation Logic
        requested_assets = state.get("assets") or []
        data_contexts = state.get("data_contexts") or {}
        
        # If no assets requested, generic chat or error
        if not requested_assets:
            print("⚠️ No assets provided, might be a generic query or early state, routing to asset_dispatcher just in case")
            # If we trust the prompt, we should have gone to 'chat', but 'analysis' with no asset is weird.
            # We send to asset_dispatcher which will handle the "0 assets" case (graceful error/hint).
            return "asset_dispatcher"

        # Check if ALL requested assets have a corresponding context
        all_assets_ready = True
        for asset in requested_assets:
            # Asset ID is either path or kbid
            asset_id = asset.get("path") or asset.get("file_path") or asset.get("kbid")
            
            # Normalize ID check (contexts are stored by absolute path or kbid string)
            if asset_id:
                # If path, ensure we check absolute path
                if "." in asset_id and "/" in asset_id: # likely path
                    asset_id = os.path.abspath(asset_id)
                
                if asset_id not in data_contexts:
                     print(f"🔍 Missing context for {asset_id}, routing to asset_dispatcher")
                     all_assets_ready = False
                     break
        
        if not all_assets_ready:
            return "asset_dispatcher"

        print("✅ All requested assets have valid contexts, routing to supervisor")
        return "supervisor"


    # Default fallback
    return "chat"


def route_after_supervisor(state: UnifiedAnalysisState) -> str:
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


def create_analysis_graph():
    """
    Create and compile the Unified Analysis Agent graph with intelligent LLM-based routing.
    
    UNIFIED ARCHITECTURE (supports Excel, Documents, PowerPoint):

    Workflow:
    1. START -> router_node (LLM classifies query)

    2. Router conditional routing:
       - "chat": Generic conversation -> chat_node -> END
       - "analysis": New analysis request -> check_data_context
       - "analysis_followup": Follow-up on previous analysis -> supervisor_node

    3. check_data_context (validates file_path):
       - If data_context missing OR file changed -> asset_dispatcher_node
       - If data_context exists AND file matches -> supervisor_node

    4. asset_dispatcher_node (detects file type, routes to correct pipeline):
       - Excel (.xlsx, .xls, .csv) -> Excel pipeline inspection
       - Documents (.docx, .pdf, .txt, .md) -> Document pipeline inspection
       - PowerPoint (.pptx, .ppt) -> PowerPoint pipeline inspection
       -> supervisor_node

    5. supervisor_node (evaluates if new code execution needed):
       - needs_analysis=True -> planning_node
       - needs_analysis=False -> followup_answer_node (answers from context)

    6. planning_node -> coding_subgraph -> END

    7. followup_answer_node -> END

    Key Features:
    - Multi-asset support (Excel, Documents, PowerPoint)
    - Pluggable pipeline architecture for easy asset type additions
    - LLM-based query classification with structured output
    - Smart file path validation to skip redundant data inspection
    - Context caching - same file won't be re-inspected
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
    # Initialize the graph with unified state
    workflow = StateGraph(UnifiedAnalysisState)

    # Add all nodes
    workflow.add_node("router", router_node)
    workflow.add_node("chat", chat_node)
    workflow.add_node("asset_dispatcher", asset_dispatcher_node)  # Replaces data_inspector
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
            "asset_dispatcher": "asset_dispatcher",
            "supervisor": "supervisor",
        },
    )

    # After asset dispatch, always go to supervisor
    workflow.add_edge("asset_dispatcher", "supervisor")

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


# # Backward compatibility alias
# def create_excel_analysis_graph():
#     """DEPRECATED: Use create_analysis_graph() instead. Kept for backward compatibility."""
#     return create_analysis_graph()


# Create the graph instance for LangGraph Studio
graph = create_analysis_graph()

