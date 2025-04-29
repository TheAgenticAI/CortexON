# Standard library imports
import json
import os
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Third-party imports
import aiohttp
from dotenv import load_dotenv
from fastapi import WebSocket
import logfire
from pydantic_ai.messages import (
    ArgsJson,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

# Local application imports
from utils.stream_response_format import StreamResponse

load_dotenv()


TIMEOUT = 9999999999999999999999999999999999999999999

class WebSurfer:
    def __init__(self, api_url: str = "http://localhost:8000/api/v1/web/stream", model_preference: str = "Anthropic"):
        self.api_url = api_url
        self.name = "Web Surfer Agent"
        self.description = "An agent that is a websurfer and a webscraper that  can access any web-page to extract information or perform actions."
        self.websocket: Optional[WebSocket] = None
        self.stream_output: Optional[StreamResponse] = None
        self.model_preference = model_preference

    async def _make_api_call(self, instruction: str) -> Tuple[int, List[Dict[str, Any]]]:
        session_timeout = aiohttp.ClientTimeout(total=None, sock_connect=TIMEOUT, sock_read=TIMEOUT)
        async with aiohttp.ClientSession(timeout=session_timeout) as session:
            final_json_response = []
            try:
                payload = {
                    "cmd": instruction, 
                    "critique_disabled": False,
                    "model_preference": self.model_preference
                }
                logfire.info(f"Making API call with model_preference: {self.model_preference}")
                async with session.post(self.api_url, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"API call failed with status {response.status}: {error_text}")
                    if response.content_type == "text/event-stream":
                        async for line in response.content:
                            line = line.decode("utf-8").strip()
                            if line:
                                line = line[5:].strip()
                                event_data = json.loads(line)
                                if self.stream_output and self.websocket:
                                    self.stream_output.steps.append(event_data["message"])
                                    # Only update live_url if it exists and is not None
                                    if "live_url" in event_data and event_data["live_url"] is not None:
                                        self.stream_output.live_url = event_data["live_url"]
                                    # Send the update with the preserved or updated live_url
                                    await self.websocket.send_text(json.dumps(asdict(self.stream_output)))
                                    logfire.debug(f"WebSocket message sent: {self.stream_output}")
                                final_json_response.append(event_data)
                    else:
                        return await response.json()
                    return 200, final_json_response
            except Exception as e:
                print(f"Error making API call: {str(e)}")
                raise e

    async def generate_reply(
        self, instruction: str, websocket: WebSocket, stream_output: StreamResponse
    ) -> Tuple[bool, str, List]:
        """Generate a reply based on the instruction by making an API call"""
        try:
            # Make API call to get web content
            logfire.debug(f"Inside generate_reply function!!!")
            logfire.debug(f"Instruction: {instruction}")
            self.websocket = websocket
            self.stream_output = stream_output
            status_code, api_response = await self._make_api_call(instruction)

            # Check if the API call was successful

            if status_code != 200:
                logfire.debug(f"API returned error status: {api_response[0].get('message', '')}")
                raise Exception(
                    f"API returned error status: {api_response[0].get('message', '')}"
                )
                

            # Generate unique tool call ID and timestamp
            logfire.debug(f"Generating tool call ID and timestamp")
            tool_call_id = f"call_{uuid.uuid4().hex[:24]}"
            current_time = datetime.utcnow()

            # Create properly structured pydantic-ai message objects
            request = ModelRequest([UserPromptPart(content=instruction)])
            final_json: Dict[str, Any] = next(
                (item for item in api_response if item.get("type") == "final"), {}
            )
            args_data: Optional[dict] = None
            print(f"Final JSON: {final_json['live_url']}")
            if final_json:
                args_data = {
                    "terminated": True,
                    "dependencies": [],
                    "content": final_json["message"],
                }

            response = ModelResponse(
                [
                    ToolCallPart(
                        tool_name="final_result",
                        tool_call_id=tool_call_id,
                        args=ArgsJson(args_json=json.dumps(args_data)),
                    )
                ],
                timestamp=current_time,
            )

            tool_return = ModelRequest(
                [
                    ToolReturnPart(
                        tool_name="final_result",
                        tool_call_id=tool_call_id,
                        content="Web search completed.",
                    )
                ]
            )

            messages = [request, response, tool_return]
            return True, final_json["message"], messages

        except Exception as e:
            error_message = f"Failed to generate web surfer reply: {str(e)}"
            print(error_message)

            # Create error message as a proper ModelResponse
            error_response = ModelResponse(
                [
                    ToolCallPart(
                        tool_name="error",
                        tool_call_id=f"error_{uuid.uuid4().hex[:12]}",
                        args=ArgsJson(args_json=json.dumps({"error": error_message})),
                    )
                ],
                timestamp=datetime.utcnow(),
            )

            return False, error_message, [error_response]