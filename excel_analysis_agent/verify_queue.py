
import asyncio
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_core.runnables import RunnableConfig

class State(TypedDict):
    messages: list

async def node_a(state: State, config: RunnableConfig):
    print("Executing Node A")
    queue = config.get("configurable", {}).get("stream_queue")
    if queue:
        print("Queue found in Node A")
        await queue.put("Hello from Node A")
    else:
        print("Queue NOT found in Node A")
    return {"messages": ["A"]}

workflow = StateGraph(State)
workflow.add_node("node_a", node_a)
workflow.add_edge(START, "node_a")
workflow.add_edge("node_a", END)
app = workflow.compile()

async def main():
    queue = asyncio.Queue()
    
    async def run_graph():
        await app.ainvoke(
            {"messages": []},
            config={"configurable": {"stream_queue": queue}}
        )
        await queue.put(None) # Signal done

    task = asyncio.create_task(run_graph())
    
    print("Listening to queue...")
    while True:
        item = await queue.get()
        if item is None:
            break
        print(f"Received: {item}")
    
    await task

if __name__ == "__main__":
    asyncio.run(main())
