import httpx
import json
import base64
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

# Import the new Dokploy client
from my_agent.helpers.dokploy_client import DokployClient

# Global client instance
_dokploy_client = None

def get_dokploy_client() -> DokployClient:
    global _dokploy_client
    if _dokploy_client is None:
        _dokploy_client = DokployClient()
    return _dokploy_client

async def reset_execution_context():
    """Reset the execution context."""
    global _dokploy_client
    _dokploy_client = DokployClient() # Just create a fresh client to clear history

@tool(parse_docstring=True)
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection on code execution progress and decision-making.

    Use this tool after each code execution to analyze results and plan next steps systematically.
    This creates a deliberate pause in the coding workflow for quality decision-making.

    When to use:
    - After receiving code execution results: What did the code produce? Was it successful?
    - After encountering errors: What went wrong? How can I fix it?
    - Before deciding next steps: Do I need to write more code or is the analysis complete?
    - When assessing progress: Have I addressed all steps in the analysis plan?
    - Before concluding: Can I provide a comprehensive final analysis now?

    Reflection should address:
    1. Analysis of current results - What did the code output? Were there any errors?
    2. Gap assessment - What parts of the analysis plan are still incomplete?
    3. Quality evaluation - Do I have sufficient data/insights for a good answer?
    4. Strategic decision - Should I continue coding, fix errors, or finalize the analysis?

    Args:
        reflection: Your detailed reflection on code execution progress, findings, errors, and next steps

    Returns:
        Confirmation that reflection was recorded for decision-making
    """

    return f"Reflection recorded: {reflection}"


@tool
async def python_repl_tool(code: str, file_paths: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Execute Python code in a sandboxed environment (Dokploy) with persistent context.

    This tool executes Python code via a remote Dokploy container. 
    The execution context persists across multiple calls by replaying history.

    The environment has the following libraries installed:
    - Data: pandas, numpy, openpyxl
    - Visualization: matplotlib, seaborn
    - Statistics & ML: scipy, statsmodels, scikit-learn
    - Utilities: tabulate, python-dateutil

    The tool automatically:
    - Detects and saves matplotlib plots to disk (.vdb/plots/...)
    - Returns structured output for creating artifacts

    Args:
        code: Python code to execute. Should be valid Python code.
              Variables and imports persist across calls within the same session.
        file_paths: Optional list of local file paths to upload to the execution environment.
                    These files will be available in the current working directory.

    Returns:
        Dictionary containing:
            - success: Boolean indicating if execution was successful
            - output: Captured stdout from the code execution
            - error: Error message if execution failed, None otherwise
            - plots: List of saved plot file paths
            - tables: List of formatted markdown tables (currently empty for Dokploy)

    Example:
        >>> await python_repl_tool("import pandas as pd\\ndf = pd.read_excel('data.xlsx')")
        {'success': True, 'output': '...', 'error': None, 'plots': [], 'tables': []}
    """
    print(f"[Python REPL via Dokploy] Executing code (UPDATED): {code}")
    print(f"[Python REPL via Dokploy] DEBUG: file_paths received: {file_paths}")
    if file_paths:
        print(f"[Python REPL via Dokploy] Including files: {file_paths}")
    
    client = get_dokploy_client()
    result = await client.execute_code(code, file_paths=file_paths)
    
    with open("result_inside_execute_code.txt", "w") as f:
        f.write(str(result))
    # Process plots: Save base64 strings to files
    saved_plots = []
    if result.get("plots"):
        # Ensure directory exists: .vdb/plots/{uuid}
        # We'll use a single directory for the session or per request? 
        # User asked for: .vdb/plots/uuid...
        # Let's generate a unique request ID for this batch of plots
        request_uuid = str(uuid.uuid4())
        plots_dir = Path(".vdb/plots") / request_uuid
        plots_dir.mkdir(parents=True, exist_ok=True)
        
        for i, plot_b64 in enumerate(result["plots"]):
            try:
                plot_data = base64.b64decode(plot_b64)
                file_path = plots_dir / f"plot_{request_uuid}_{i}.png"
                with open(file_path, "wb") as f:
                    f.write(plot_data)
                saved_plots.append(str(file_path.absolute()))
                print(f"📊 Saved plot to {file_path}")
            except Exception as e:
                print(f"❌ Error saving plot {i}: {e}")
                
    result["plots"] = saved_plots
    
    # Pass through tables if we implement table detection later
    if "tables" not in result:
        result["tables"] = []
        
    return result


@tool
async def bash_tool(command: str) -> Dict[str, Any]:
    """
    Execute bash commands. 
    
    NOTE: With Dokploy integration, dynamic pip installs are not persisted 
    unless we add them to the Code History as !pip magic commands or similar.
    For now, we return a warning or try to implement it.
    """
    return {
        "success": False,
        "output": "",
        "error": "Bash tool is currently limited in Dokploy environment. Please use python_repl_tool for code execution."
    }

# Configuration for remote search
SEARCH_URL = "https://backend.v3.codemateai.dev/knowledge/search"
SSL_CONTEXT = True  # Use standard SSL verification

@tool
async def document_search_tool(query: str, kbid: str) -> str:
    """
    Perform a remote vector search on a document knowledge base to find relevant information.
    
    Use this tool when you need to find specific information within documents that are not
    fully loaded into the context. It returns the most relevant snippets from the document.
    
    Args:
        query: The search query or question to find in the document
        kbid: The Knowledge Base ID to search within
        
    Returns:
        A string containing the relevant document snippets and metadata.
    """
    try:
        data = {"collection_id": kbid, "search_queries": query}
        # Use the session ID provided by the user
        headers = {"X-Session": "e04230cd-0ed7-41d0-a70a-d699b3b4957c"}
        
        async with httpx.AsyncClient(verify=SSL_CONTEXT) as client:
            response = await client.post(
                SEARCH_URL,
                json=data,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            results = response.json()
            
            if not results:
                return "No relevant information found in the document."
                
            formatted_results = []
            for i, res in enumerate(results):
                payload = res.get("payload", {})
                content = payload.get("content", "")
                if isinstance(content, dict):
                    content = content.get("text", "")
                
                file_info = f"Source: {payload.get('file', 'Unknown')}"
                lines = payload.get("lines", [])
                if lines:
                    file_info += f" (Lines {lines[0]}-{lines[1]})"
                
                formatted_results.append(f"Result {i+1}:\n{file_info}\nContent: {content}\n")
                
            return "\n".join(formatted_results)
            
    except Exception as e:
        print(f"Error in document_search_tool: {e}")
        return f"Error performing document search: {str(e)}"
