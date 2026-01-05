import litellm
import asyncio
from typing import Any, Dict, List, Optional, Union, Type
from pydantic import BaseModel
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
import json

# LiteLLM Configuration
BASE_URL = "https://backend.v3.codemateai.dev/v2"
API_KEY = "97cf2e7c-8738-4495-9c82-ec01f30b9836"
MODEL = "sub_chat"

def convert_message_to_dict(message: BaseMessage) -> Dict[str, Any]:
    """Convert LangChain message to LiteLLM/OpenAI format."""
    if isinstance(message, HumanMessage):
        return {"role": "user", "content": message.content}
    elif isinstance(message, SystemMessage):
        return {"role": "system", "content": message.content}
    elif isinstance(message, AIMessage):
        msg = {"role": "assistant", "content": message.content}
        if hasattr(message, "tool_calls") and message.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc["args"])
                    }
                } for tc in message.tool_calls
            ]
        return msg
    elif isinstance(message, ToolMessage):
        return {
            "role": "tool",
            "content": str(message.content),
            "tool_call_id": message.tool_call_id
        }
    return {"role": "user", "content": str(message.content)}

async def litellm_completion(
    messages: List[BaseMessage],
    temperature: float = 0,
    tools: Optional[List[Any]] = None,
    response_format: Optional[Type[BaseModel]] = None,
    **kwargs
) -> Union[AIMessage, Any]:
    """
    Call LiteLLM with LangChain messages and return LangChain-compatible output.
    """
    formatted_messages = [convert_message_to_dict(m) for m in messages]
    
    # [LOG] LLM Input Preparation
    print("-" * 80)
    print("[DEBUG] Preparing LiteLLM Request")
    print(f"[DEBUG] Model: {MODEL}")
    print(f"[DEBUG] Base URL: {BASE_URL}")
    print("[DEBUG] Messages sent to LLM:")
    for i, msg in enumerate(formatted_messages):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        # Handle cases where content might be a list (multimodal)
        display_content = content[:500] + "..." if isinstance(content, str) and len(content) > 500 else content
        print(f"  {i+1}. role={role}: {display_content}")

    # Prepare litellm arguments
    litellm_kwargs = {
        "model": MODEL,
        "messages": formatted_messages,
        "base_url": BASE_URL,
        "api_api_key": API_KEY, # Fixed potential typo if exists, or kept consistent
        "api_key": API_KEY,
        "temperature": temperature,
        "custom_llm_provider": "openai",
        **kwargs
    }
    
    if tools:
        print("[DEBUG] Tools provided to LLM:")
        litellm_kwargs["tools"] = []
        for tool in tools:
            if hasattr(tool, "args_schema") and tool.args_schema:
                schema = tool.args_schema.schema()
                tool_def = {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": schema
                    }
                }
                litellm_kwargs["tools"].append(tool_def)
                print(f"  - function: {tool.name}")
            else:
                tool_def = {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": {"type": "object", "properties": {}}
                    }
                }
                litellm_kwargs["tools"].append(tool_def)
                print(f"  - function (no schema): {tool.name}")

    if response_format:
        litellm_kwargs["response_format"] = {"type": "json_object"}
        properties = response_format.schema().get("properties", {})
        keys_desc = [f'"{k}": ({p.get("description", "no description")})' for k, p in properties.items()]
        keys_str = "\n".join(keys_desc)
        instruction = f"\n\nCRITICAL: Return your response ONLY as a JSON object with the following keys:\n{keys_str}\n\nExample:\n{{\n  " + ',\n  '.join([f'"{k}": "..." ' for k in properties.keys()]) + "\n}"
        
        print("[DEBUG] Structured output requested. Appending schema instruction to last message.")
        if isinstance(formatted_messages[-1]["content"], str):
             formatted_messages[-1]["content"] += instruction
        else:
             added = False
             for part in reversed(formatted_messages[-1]["content"]):
                 if isinstance(part, dict) and part.get("type") == "text":
                     part["text"] += instruction
                     added = True
                     break
             if not added:
                 formatted_messages[-1]["content"].append({"type": "text", "text": instruction})

    try:
        print("[ACTION] Calling LiteLLM API...")
        response = await litellm.acompletion(**litellm_kwargs)
        
        choice = response.choices[0].message
        content = choice.content
        
        print("[DEBUG] LiteLLM Response Received")
        if content:
            print("[DEBUG] Final Content Response:")
            print(content)
            
        # If we requested structured output (response_format), parse it
        if response_format and content:
            try:
                print("[ACTION] Parsing structured output...")
                clean_content = content.replace("```json", "").replace("```", "").strip()
                parsed_data = json.loads(clean_content)
                result = response_format(**parsed_data)
                print("[DEBUG] Successfully parsed structured output")
                print("-" * 80)
                return result
            except Exception as e:
                print(f"[ERROR] Failed to parse structured output: {e}\nRaw Content: {content}")
                raise
            
        # Handle tool calls
        tool_calls = []
        if hasattr(choice, "tool_calls") and choice.tool_calls:
            print(f"[DEBUG] Tool calls detected: {len(choice.tool_calls)}")
            for tc in choice.tool_calls:
                tc_data = {
                    "name": tc.function.name,
                    "args": json.loads(tc.function.arguments),
                    "id": tc.id
                }
                tool_calls.append(tc_data)
                print(f"  - tool: {tc.function.name}, args: {tc.function.arguments}")
        
        print("-" * 80)
        return AIMessage(content=content or "", tool_calls=tool_calls)
        
    except Exception as e:
        print(f"[ERROR] LiteLLM API call or processing failed: {e}")
        print("-" * 80)
        raise
