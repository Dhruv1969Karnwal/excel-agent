import asyncio
import logging
import os
from langchain_core.messages import HumanMessage
from my_agent.agent import graph

# Enable logging for LangGraph internals
logging.basicConfig(level=logging.INFO)

async def main():
    # Generate and print Mermaid diagram for static visualization
    mermaid_code = graph.get_graph().draw_mermaid()
    print("📊 Graph Mermaid Diagram:")
    print(mermaid_code)
    print("\n" + "="*50 + "\n")
    # Path to the Excel file
    excel_file_path = r"C:\Users\Dhruv\Downloads\esd.xlsx"
    
    if not os.path.exists(excel_file_path):
        print(f"❌ Error: File not found at {excel_file_path}")
        return

    print(f"📂 Found Excel file: {excel_file_path}")
    
    # Test query
    # query = "List down count of employee along with their name whose annual salary is more than $100000 and country is United States"
    query = "Show me a chart of employees by gender"
    print(f"🤖 User Query: {query}")
    print("🚀 Starting analysis (this may take a minute as LiteLLM is called)...")
    
    # Initial state
    initial_state = {
        "messages": [HumanMessage(content=query)],
        "excel_file_path": excel_file_path,
    }
    
    # Run the graph with streaming to trace steps
    print("🔍 Tracing agent steps...\n")
    result = None
    async for event in graph.astream(initial_state, stream_mode="values"):
        result = event  # Update result with latest state
        # Print key state changes for tracing
        if "messages" in event and event["messages"]:
            last_msg = event["messages"][-1]
            print(f"📝 Message: {last_msg.content[:100]}...")
        if "route_decision" in event and event["route_decision"]:
            print(f"🛤️ Route Decision: {event['route_decision']}")
        if "supervisor_decision" in event and event["supervisor_decision"]:
            print(f"👨‍💼 Supervisor Decision: {event['supervisor_decision']}")
        if "data_context" in event and event["data_context"]:
            print(f"📊 Data Context Loaded: {event['data_context'].get('file_path', 'N/A')}")
        if "artifacts" in event and event["artifacts"]:
            print(f"📦 Artifacts Added: {len(event['artifacts'])} total")
        print("─" * 30)  # Separator

    print("\n" + "="*50)
    print("✅ ANALYSIS COMPLETE")
    print("="*50 + "\n")

    if "final_analysis" in result and result["final_analysis"]:
        print(result["final_analysis"])
    else:
        # Fallback to last message if final_analysis isn't set
        last_message = result["messages"][-1]
        print(last_message.content)

    # ============================================
    # DETAILED ARTIFACT INFORMATION
    # ============================================
    print("\n" + "="*50)
    print("📦 ARTIFACTS DETAILED VIEW")
    print("="*50 + "\n")

    if "artifacts" in result and result["artifacts"]:
        print(f"📊 Total Artifacts Generated: {len(result['artifacts'])}\n")

        # Count by type
        type_counts = {}
        for artifact in result["artifacts"]:
            artifact_type = artifact.get("type", "unknown")
            type_counts[artifact_type] = type_counts.get(artifact_type, 0) + 1

        print("📈 Artifacts by Type:")
        for atype, count in type_counts.items():
            icon = {
                "plot": "🖼️",
                "table": "📋",
                "insight": "💡",
                "code": "📝"
            }.get(atype, "📦")
            print(f"   {icon} {atype.capitalize()}: {count}")
        print()

        # Display each artifact in detail
        for i, artifact in enumerate(result["artifacts"], 1):
            print(f"{'─'*50}")
            print(f"Artifact #{i}")
            print(f"{'─'*50}")

            # Type
            artifact_type = artifact.get("type", "unknown")
            print(f"📌 Type: {artifact_type}")

            # Description
            description = artifact.get("description", "No description")
            print(f"📝 Description: {description}")

            # Timestamp
            timestamp = artifact.get("timestamp", "No timestamp")
            print(f"🕐 Timestamp: {timestamp}")

            # Content based on type
            content = artifact.get("content", "")

            if artifact_type == "plot":
                # Plot: show file path
                print(f"📁 File Path: {content}")
                # Check if file exists
                if os.path.exists(content):
                    print(f"✅ File exists!")
                else:
                    print(f"⚠️ File NOT found at specified path")
            elif artifact_type == "table":
                # Table: show markdown preview (first 20 lines)
                print(f"📋 Table Preview (first 20 lines):\n")
                lines = content.split("\n")[:20]
                for line in lines:
                    print(f"   {line}")
                if len(content.split("\n")) > 20:
                    print(f"   ... (truncated, {len(content.split('|'))} columns total)")
            elif artifact_type == "insight":
                # Insight: show text content (first 500 chars)
                print(f"💡 Insight Content:\n")
                preview = content[:500] if len(content) > 500 else content
                print(f"   {preview}")
                if len(content) > 500:
                    print(f"   ... ({len(content)} total characters)")
            elif artifact_type == "code":
                # Code: show code snippet
                print(f"📝 Code Content:\n")
                preview = content[:300] if len(content) > 300 else content
                print(f"   {preview}")
                if len(content) > 300:
                    print(f"   ... ({len(content)} total characters)")
            else:
                # Unknown type
                print(f"📦 Content: {content[:200]}...")

            print()  # Empty line between artifacts

        print(f"{'─'*50}")
        print(f"✅ All {len(result['artifacts'])} artifacts displayed")

    else:
        print("📭 No artifacts were generated for this analysis.")
        print("\n💡 Tips to generate artifacts:")
        print("   - Ask for visualizations: 'Show me a chart of...'")
        print("   - Request data tables: 'Display the filtered data'")
        print("   - The agent auto-generates insights for analysis results")

    print("\n" + "="*50)

if __name__ == "__main__":
    asyncio.run(main())
