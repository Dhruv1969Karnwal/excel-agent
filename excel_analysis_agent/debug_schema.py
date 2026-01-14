from my_agent.tools.tools import python_repl_tool
import asyncio

def debug_schema():
    print("--- Tool Args Schema ---")
    print(python_repl_tool.args)
    
    print("\n--- Invocation Test ---")
    try:
        # We can't await the result easily without mocking, but we can check if it accepts the args
        # or at least print the plan
        print("Schema properties:", python_repl_tool.args_schema.schema())
    except Exception as e:
        print(f"Error checking schema: {e}")

if __name__ == "__main__":
    debug_schema()
