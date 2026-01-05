import asyncio
import os
from langchain_core.messages import HumanMessage
from my_agent.agent import graph

async def main():
    # Path to the Excel file
    excel_file_path = r"C:\Users\Dhruv\Downloads\esd.xlsx"
    
    if not os.path.exists(excel_file_path):
        print(f"❌ Error: File not found at {excel_file_path}")
        return

    print(f"📂 Found Excel file: {excel_file_path}")
    
    # Test query
    query = "List down count of employee along with their name whose annual salary is more than $100000 and country is United States"
    
    print(f"🤖 User Query: {query}")
    print("🚀 Starting analysis (this may take a minute as LiteLLM is called)...")
    
    # Initial state
    initial_state = {
        "messages": [HumanMessage(content=query)],
        "excel_file_path": excel_file_path,
    }
    
    # Run the graph using ainvoke to get the final result directly
    # (since we don't have a checkpointer configured for aget_state)
    result = await graph.ainvoke(initial_state)
    
    print("\n" + "="*50)
    print("✅ ANALYSIS COMPLETE")
    print("="*50 + "\n")
    
    if "final_analysis" in result and result["final_analysis"]:
        print(result["final_analysis"])
    else:
        # Fallback to last message if final_analysis isn't set
        last_message = result["messages"][-1]
        print(last_message.content)

    print("\n" + "="*50)
    if "artifacts" in result and result["artifacts"]:
        print(f"📊 Generated {len(result['artifacts'])} artifacts (plots, tables, etc.)")
        for artifact in result["artifacts"]:
            if artifact["type"] == "plot":
                print(f"   - Plot saved at: {artifact['content']}")

if __name__ == "__main__":
    asyncio.run(main())
