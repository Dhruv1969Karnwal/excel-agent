import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from my_agent.nodes.asset_dispatcher import asset_dispatcher_node
from my_agent.nodes.planning import planning_node
from my_agent.helpers.dynamic_registration import process_incoming_request
from langchain_core.runnables import RunnableConfig

async def test_code_pipeline():
    print("🚀 Verifying CodePipeline...")

    # Simulating an attached code file
    # We use main.py as it exists in the root
    code_file_path = os.path.abspath("main.py")
    
    mock_request = {
        "query": "Explain the logic in main.py",
        "attachments": [
            {"path": code_file_path, "type": "code", "name": "main.py"}
        ]
    }

    # 1. Test Request Processing & Registration
    print("\n--- Phase 1: Dynamic Registration ---")
    initial_state = process_incoming_request(mock_request)
    print(f"✅ State assets: {initial_state['assets']}")
    
    # 2. Test Asset Dispatcher (Inspection)
    print("\n--- Phase 2: Asset Dispatcher (Inspection) ---")
    config = RunnableConfig(configurable={"stream_queue": asyncio.Queue()})
    dispatch_result = await asset_dispatcher_node(initial_state, config)
    
    data_contexts = dispatch_result.get("data_contexts", {})
    if code_file_path in data_contexts:
        ctx = data_contexts[code_file_path]
        print(f"✅ File inspected: {ctx.get('file_name')}")
        print(f"✅ Document Type: {ctx.get('document_type')}")
        print(f"✅ Description Preview: {ctx.get('description')[:100]}...")
    else:
        print("❌ Code file not found in data_contexts!")
        return

    # 3. Test Planning Node (Prompts)
    print("\n--- Phase 3: Planning Node (Code Prompts) ---")
    # Update state with dispatch result
    initial_state["data_contexts"] = data_contexts
    
    try:
        planning_result = await planning_node(initial_state)
        print("✅ Planning Node executed successfully.")
        # The planning result would show code-specific steps if the mock LLM was used,
        # but here we just verify the flow and context usage.
    except Exception as e:
        print(f"❌ Planning Node failed: {e}")

    print("\n✨ CodePipeline verification complete!")

if __name__ == "__main__":
    asyncio.run(test_code_pipeline())
