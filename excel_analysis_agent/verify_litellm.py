import asyncio
import unittest
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from my_agent.core.llm_client import litellm_completion, convert_message_to_dict
import json

class TestLiteLLMIntegration(unittest.TestCase):

    def test_convert_message_to_dict(self):
        # Test HumanMessage
        msg = HumanMessage(content="Hello")
        d = convert_message_to_dict(msg)
        self.assertEqual(d["role"], "user")
        self.assertEqual(d["content"], "Hello")

        # Test SystemMessage
        msg = SystemMessage(content="You are a bot")
        d = convert_message_to_dict(msg)
        self.assertEqual(d["role"], "system")
        self.assertEqual(d["content"], "You are a bot")

        # Test AIMessage with tool calls
        msg = AIMessage(content="I will use a tool", tool_calls=[{"name": "test_tool", "args": {"a": 1}, "id": "123"}])
        d = convert_message_to_dict(msg)
        self.assertEqual(d["role"], "assistant")
        self.assertEqual(len(d["tool_calls"]), 1)
        self.assertEqual(d["tool_calls"][0]["function"]["name"], "test_tool")

    @patch("litellm.acompletion")
    async def test_litellm_completion(self, mock_acompletion):
        # Mock response
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Response from LLM"
        mock_choice.message.tool_calls = None
        mock_response.choices = [mock_choice]
        mock_acompletion.return_value = mock_response

        messages = [HumanMessage(content="Hi")]
        response = await litellm_completion(messages)

        self.assertIsInstance(response, AIMessage)
        self.assertEqual(response.content, "Response from LLM")
        
        # Verify call arguments
        mock_acompletion.assert_called_once()
        args, kwargs = mock_acompletion.call_args
        self.assertEqual(kwargs["model"], "sub_chat")
        self.assertEqual(kwargs["base_url"], "https://backend.v3.codemateai.dev/v2")
        self.assertEqual(kwargs["api_key"], "97cf2e7c-8738-4495-9c82-ec01f30b9836")

    @patch("litellm.acompletion")
    async def test_structured_output(self, mock_acompletion):
        from pydantic import BaseModel
        class Output(BaseModel):
            val: int

        # Mock response with JSON
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = '{"val": 42}'
        mock_choice.message.tool_calls = None
        mock_response.choices = [mock_choice]
        mock_acompletion.return_value = mock_response

        messages = [HumanMessage(content="Give me 42")]
        response = await litellm_completion(messages, response_format=Output)

        self.assertIsInstance(response, Output)
        self.assertEqual(response.val, 42)

async def run_tests():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestLiteLLMIntegration)
    # Since we have async tests, we need to run them differently or use a library like pytest-asyncio
    # For simplicity, I'll just manually run a few key checks
    test = TestLiteLLMIntegration()
    test.test_convert_message_to_dict()
    await test.test_litellm_completion()
    await test.test_structured_output()
    print("Basic verification tests passed!")

if __name__ == "__main__":
    asyncio.run(run_tests())
