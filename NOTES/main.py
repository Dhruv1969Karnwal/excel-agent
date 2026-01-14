"""Main entry point for the Multi-Asset Analysis Agent API."""

import os
import uvicorn
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from my_agent.agent import graph
from my_agent.helpers.dynamic_registration import process_incoming_request
from pprint import pprint
import datetime
import pydantic
from langchain_core.messages import BaseMessage




app = FastAPI(
    title="Multi-Asset Analysis Agent API",
    description="API for analyzing Excel, Documents, and PowerPoint files.",
    version="1.0.0"
)

from my_agent.models.request_models import ChatRequest

@app.get("/")
async def root():
    return {"message": "Multi-Asset Analysis Agent API is running"}

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Main endpoint for chat interactions with multi-asset support.
    """
    import json
    from fastapi.responses import StreamingResponse
    
    try:
        initial_state = process_incoming_request(request.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request: {str(e)}")

    async def chat_stream():
        """Generator function to stream events from the agent graph using a Queue."""
        import asyncio
        MESSAGE_DELIMITER = "<__!!__END__!!__>"
        
        # Emit Start Event
        yield json.dumps({
            "type": "start", 
            "message": "Conversation started"
        }) + MESSAGE_DELIMITER

        # Create a queue for streaming
        stream_queue = asyncio.Queue()
        
        # Define background task to run the graph
        async def run_graph():
            try:
                print(f"[DEBUG MAIN] Starting graph.ainvoke with queue...")
                # We use ainvoke instead of astream, as we are manually streaming via queue
                result = await graph.ainvoke(
                    initial_state,
                    config={"configurable": {"stream_queue": stream_queue}, "recursion_limit": 100}
                )
                print(f"[DEBUG MAIN] Graph execution completed.")
                # We can optionally put the final result in queue if needed, but for now just signal done
            except Exception as e:
                import traceback
                traceback.print_exc()
                await stream_queue.put({
                    "type": "error",
                    "error": str(e)
                })
            finally:
                # Signal end of stream
                await stream_queue.put(None)

        # Start the graph execution in background
        task = asyncio.create_task(run_graph())

        # Read from queue
        while True:
            try:
                # Wait for next item
                item = await stream_queue.get()
                
                if item is None:
                    # Sentinel for end of stream
                    break
                
                # print(f"[DEBUG MAIN] Dequeued item: {item}")
                # 
                # Check for error in item
                if isinstance(item, dict) and item.get("type") == "error":
                    print(f"[DEBUG MAIN] Error received in queue: {item}")

                # Serialize and yield
                try:
                    json_data = json.dumps(item)
                    yield json_data + MESSAGE_DELIMITER
                    
                    # Write to file
                    with open("stream_output.jsonl", "a") as f:
                        f.write(json_data + "\n")
                except Exception as json_err:
                    print(f"[DEBUG MAIN] JSON Serialization error: {str(json_err)}")

            except Exception as e:
                print(f"[DEBUG MAIN] Error reading from queue: {e}")
                break
        
        # Ensure task is done (should be, as we received None)
        await task
        
        # Emit Complete Event
        yield json.dumps({
            "type": "complete",
            "message": "Processing finished"
        }) + MESSAGE_DELIMITER
        
        # Emit Complete Event
        yield json.dumps({
            "type": "complete",
            "message": "Processing finished"
        }) + MESSAGE_DELIMITER

    return StreamingResponse(
        chat_stream(),
        media_type="text/event-stream",
    )

if __name__ == "__main__":
    # Start the server
    uvicorn.run(app, host="0.0.0.0", port=8000)
