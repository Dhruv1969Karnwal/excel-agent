import asyncio
import os
import pandas as pd
from my_agent.tools.tools import python_repl_tool

async def test_attachment_upload():
    # Simulate an asset path (we'll use esd.xlsx which the user mentioned)
    # The actual file might be in testData/esd.xlsx
    asset_path = "C:\\Users\\Dhruv\\Desktop\\CodeMate.AI\\crafting-ai-agents\\testData\\esd.xlsx"
    
    if not os.path.exists(asset_path):
        print(f"❌ Error: {asset_path} does not exist on your computer. Please make sure it's there.")
        return

    code = f"""
import pandas as pd
import os

print("Files in current directory:", os.listdir('.'))

try:
    df = pd.read_excel('esd.xlsx')
    print("✅ Success! Read Excel file. Rows:", len(df))
    print("Columns:", df.columns.tolist())
except Exception as e:
    print("❌ Failed:", str(e))
"""
    
    print("🧪 Testing attachment upload to Dokploy...")
    # We call the tool directly with the file_path
    result = await python_repl_tool.ainvoke({"code": code, "file_paths": [asset_path]})
    
    print("\n--- Execution Result ---")
    print(result.get("output"))
    if result.get("error"):
        print("Error:", result["error"])

if __name__ == "__main__":
    asyncio.run(test_attachment_upload())
