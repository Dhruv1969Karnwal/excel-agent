"""Main entry point for the Multi-Asset Analysis Agent API."""

import os
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from my_agent.agent import graph
from my_agent.helpers.dynamic_registration import process_incoming_request

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
    try:
        # Prepare initial state from request
        initial_state = process_incoming_request(request.model_dump())
        
        # Run the agent graph
        final_state = await graph.ainvoke(initial_state)
        
        # Extract relevant info from final state
        response = {
            "analysis": final_state.get("final_analysis", ""),
            "artifacts": final_state.get("artifacts", []),
            "route": final_state.get("route_decision", {}).get("route", "chat"),
            "asset_type": final_state.get("asset_type", "excel")
        }
        
        # Optionally include the full message history
        # response["messages"] = [str(m) for m in final_state.get("messages", [])]
        
        return response
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Start the server
    uvicorn.run(app, host="0.0.0.0", port=8000)
