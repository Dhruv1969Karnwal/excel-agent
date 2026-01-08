import requests
import json
import os
import time
from pprint import pprint

# Base URL for the new API
BASE_URL = "http://localhost:8000"

def test_root():
    print("\n--- Testing Root Endpoint ---")
    response = requests.get(f"{BASE_URL}/")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

def test_chat_excel():
    print("\n--- Testing /chat with Excel ---")
    payload = {
        "query": "Show me the top 5 rows of this data",
        "attachments": [
            {"excel": "testData/esd.xlsx"}
        ]
    }
    response = requests.post(f"{BASE_URL}/chat", json=payload)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        res_data = response.json()
        print(f"Analysis Summary: {res_data.get('analysis')[:200]}...")
        print(f"Artifacts Found: {len(res_data.get('artifacts', []))}")
    else:
        print(f"Error: {response.text}")

def test_chat_codebase():
    print("\n--- Testing /chat with Codebase (RAG) ---")
    payload = {
        "query": "How is authentication handled in this codebase?",
        "attachments": [
            {"codebase": "iam-server", "kbid": "xxxx-yyyy-zzzz"}
        ]
    }
    response = requests.post(f"{BASE_URL}/chat", json=payload)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        res_data = response.json()
        print(f"Analysis Summary: {res_data.get('analysis')[:500]}...")
    else:
        print(f"Error: {response.text}")

if __name__ == "__main__":
    # Ensure relative paths work
    # os.chdir("c:/Users/Dhruv/Desktop/CodeMate.AI/crafting-ai-agents/excel_analysis_agent")
    
    print("🚀 Starting API Tests...")
    print("Note: Ensure 'python main.py' is running in another terminal.")
    
    try:
        test_root()
        test_chat_excel()
        test_chat_codebase()
    except Exception as e:
        print(f"❌ Test failed: {e}")
