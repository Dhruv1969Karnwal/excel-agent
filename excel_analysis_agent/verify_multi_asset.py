
import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from my_agent.nodes.router import router_node
from my_agent.nodes.planning import planning_node
from langchain_core.messages import HumanMessage

async def test_multi_asset_flow():
    print("🚀 Starting Multi-Asset Verification...")

    # Mock Data Contexts for Multi-Asset Scenario
    mock_data_contexts = {
        "sales_data.xlsx": {
            "document_type": "Excel",
            "file_name": "sales_data.xlsx",
            "description": "Contains columns: [Date, Revenue, Customer_ID]. 500 rows.",
            "summary": {"num_rows": 500, "num_columns": 3}
        },
        "IAM_Server_Repo": {
            "document_type": "Codebase/Collection (RAG)",
            "file_name": "IAM_Server_Repo",
            "description": "Python codebase for IAM. Files: [auth.py, user.py].",
            "summary": {}
        }
    }

    # Mock State
    mock_state = {
        "messages": [HumanMessage(content="Find high revenue customers in Excel and check if they exist in the IAM codebase.")],
        "data_contexts": mock_data_contexts,
        "assets": [
            {"path": "sales_data.xlsx", "type": "excel"},
            {"kbid": "IAM_Server_Repo", "type": "codebase"}
        ],
        "user_query": "Find high revenue customers in Excel and check if they exist in the IAM codebase."
    }

    print("\n--- Testing Router Node ---")
    # We can't easily capture the internal prompt print without capturing stdout, 
    # but we can observe if it crashes and what the reasoning is.
    try:
        router_result = await router_node(mock_state)
        print(f"✅ Router Result: {router_result}")
        if router_result['route_decision']['route'] == 'analysis':
             print("✅ Router correctly classified as 'analysis'")
        else:
             print(f"⚠️ Router classification unexpected: {router_result['route_decision']['route']}")
    except Exception as e:
        print(f"❌ Router Node Failed: {e}")

    print("\n--- Testing Planning Node ---")
    try:
        planning_result = await planning_node(mock_state)
        print("✅ Planning Node Executed.")
        
        # Check if the "Mixed asset types" logic was triggered
        # (This relies on side-effects/prints usually, but we can infer from the quality or just successful execution)
        # In a real unit test we would mock the LLM and check inputs. 
        # Here we trust the print statements we added in the code will show up in the terminal output.
        
    except Exception as e:
        print(f"❌ Planning Node Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_multi_asset_flow())
