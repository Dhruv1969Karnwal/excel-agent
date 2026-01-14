import asyncio
import os
import sys
from pathlib import Path
import json
# Add the project root to sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from my_agent.tools.tools import python_repl_tool

async def main():
    print("🧪 Starting Dokploy Integration Test...")
    
    # # Test 1: Basic variable assignment and persistence
    # print("\n--- Test 1: Persistence ---")
    # code1 = "x = 42\nprint(f'Setting x to {x}')"
    # print(f"Executing: {code1}")
    # result1 = await python_repl_tool.ainvoke({"code": code1})
    # print(f"Result 1 Success: {result1.get('success')}")
    # print(f"Result 1 Output: {result1.get('output').strip()}")
    # if result1.get('error'):
    #     print(f"Result 1 Error: {result1.get('error')}")

    # # Test 2: Accessing variable from previous call
    # code2 = "print(f'Retrieving x: {x}')\ny = x * 2\nprint(f'Computed y = {y}')"
    # print(f"\nExecuting: {code2}")
    # result2 = await python_repl_tool.ainvoke({"code": code2})
    # print(f"Result 2 Success: {result2.get('success')}")
    # print(f"Result 2 Output: {result2.get('output').strip()}")
    # if result2.get('error'):
    #     print(f"Result 2 Error: {result2.get('error')}")

    # Test 3: Plot generation
    print("\n--- Test 3: Plot Generation ---")
    code3 = """
import matplotlib.pyplot as plt
import numpy as np

t = np.arange(0.0, 2.0, 0.01)
s = 1 + np.sin(2 * np.pi * t)

fig, ax = plt.subplots()
ax.plot(t, s)

ax.set(xlabel='time (s)', ylabel='voltage (mV)',
       title='About as simple as it gets, folks')
ax.grid()

plt.show()
print("Plot generated and plt.show() called.")
"""
    print(f"Executing plot code...")
    result3 = await python_repl_tool.ainvoke({"code": code3})
    with open ("result3.json", "w") as f:
        json.dump(result3, f)
    # print(f"Result 3 Success: {result3.get('success')}")
    # print(f"Result 3 Output: {result3.get('output').strip()}")
    # print(f"Result 3 Plots: {result3.get('plots')}")
    # if result3.get('error'):
    #     print(f"Result 3 Error: {result3.get('error')}")

    # print("\n✅ Dokploy Integration Test Complete.")

if __name__ == "__main__":
    asyncio.run(main())
