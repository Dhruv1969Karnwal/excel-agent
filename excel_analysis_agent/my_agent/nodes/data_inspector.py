from typing import Any, Dict

from langchain_core.messages import AIMessage

from my_agent.helpers.sandbox_client import check_server_health
from my_agent.helpers.utils import (
    analyze_dataframe,
    generate_data_description,
    load_excel_file,
)
from my_agent.models.state import ExcelAnalysisState
from my_agent.tools.tools import reset_execution_context


async def data_inspector_node(state: ExcelAnalysisState) -> Dict[str, Any]:
    """
    Data Inspector Node - Analyzes Excel file and generates description.

    This node:
    1. Checks if the sandbox server is running
    2. Gets the excel_file_path from state
    3. Resets the Python REPL execution context for a fresh start
    4. Loads and analyzes the Excel file
    5. Generates a detailed textual description of the data
    6. Updates the state with the data context

    Args:
        state: Current state containing excel_file_path

    Returns:
        Dictionary with data_context and messages updates
    """
    # Health check: Ensure sandbox server is running
    print("🔍 Checking sandbox server health...")
    try:
        healthy = await check_server_health()
        if not healthy:
            error_msg = (
                "Sandbox server is not running or unhealthy. "
                "Please start the server in a separate terminal:\n"
                "  python run_sandbox_server.py"
            )
            print(f"❌ {error_msg}")
            return {
                "data_context": f"Error: {error_msg}",
                "messages": [AIMessage(
                    content=error_msg,
                    name="DataInspector"
                )]
            }
    except Exception as e:
        error_msg = (
            f"Cannot connect to sandbox server: {str(e)}\n"
            "Please start the server in a separate terminal:\n"
            "  python run_sandbox_server.py"
        )
        print(f"❌ {error_msg}")
        return {
            "data_context": f"Error: {error_msg}",
            "messages": [AIMessage(
                content=error_msg,
                name="DataInspector"
            )]
        }

    # Reset the Python REPL execution context for a clean start
    await reset_execution_context()

    print("📊 Data Inspector: Analyzing Excel file...")

    # Get file path from state
    excel_path = state.get("excel_file_path")

    if not excel_path:
        # No file path - this shouldn't happen if router works correctly
        print("❌ No excel_file_path found in state!")
        return {
            "data_context": "Error: No Excel file path was provided.",
            "messages": [AIMessage(
                content="Please provide an excel_file_path in the input to analyze.",
                name="DataInspector"
            )]
        }

    print(f"📎 Analyzing file: {excel_path}")

    # Load and analyze the Excel file
    try:
        import asyncio
        import os
        from datetime import datetime
        from pathlib import Path

        df = await load_excel_file(excel_path)
        analysis = await analyze_dataframe(df)
        data_description = await generate_data_description(analysis)

        print(
            f"✅ Data Inspector: Analysis complete. Found {analysis['num_rows']} rows and {analysis['num_columns']} columns."
        )

        # Get file name using asyncio.to_thread to avoid blocking
        file_name = await asyncio.to_thread(lambda: Path(excel_path).name)

        # Create structured data context with file path for validation
        # Use os.path.abspath instead of Path.resolve() to avoid blocking symlink resolution
        data_context = {
            "file_path": os.path.abspath(excel_path),  # Absolute path without symlink resolution
            "file_name": file_name,
            "analyzed_at": datetime.now().isoformat(),
            "description": data_description,
            "summary": {
                "num_rows": analysis['num_rows'],
                "num_columns": analysis['num_columns'],
                "column_names": analysis['column_names'],
                "numeric_columns": analysis['numeric_columns'],
                "categorical_columns": analysis['categorical_columns'],
            }
        }

        # Add a message to the conversation history
        inspector_message = AIMessage(
            content=f"Data inspection complete. The Excel file '{data_context['file_name']}' contains {analysis['num_rows']} rows and {analysis['num_columns']} columns.",
            name="DataInspector",
        )

        return {
            "data_context": data_context,
            "messages": [inspector_message]
        }

    except Exception as e:
        print(f"❌ Error analyzing file: {e}")
        return {
            "data_context": f"Error analyzing file: {str(e)}",
            "messages": [AIMessage(
                content=f"I encountered an error while analyzing the file: {str(e)}",
                name="DataInspector"
            )]
        }
