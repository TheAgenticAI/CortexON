from datetime import datetime, timezone
from typing import List, Dict, Any, Union
from dataclasses import dataclass
from openai.types.chat import ChatCompletionMessageParam
import uuid
import json
import os
import re


from core.utils.logger import Logger
logger = Logger()

def extract_explainer_data(explainer_response):
    """
    Extracts the expected field information from the explainer agent's response.
    The response should include a JSON object (possibly wrapped in markdown or extra text)
    with the key "expected_field_info". This function extracts that value.
    """
    try:
        # Get the last message from the response
        last_message = explainer_response.new_messages()[-1]
        text_content = last_message.parts[0].content
        logger.info(f"Raw explainer text content: {text_content}")

        # Remove markdown formatting (e.g. backticks) if present.
        text_content = text_content.strip().strip("`")
        
        # Use a regular expression to extract the JSON object.
        json_match = re.search(r'\{.*\}', text_content, re.DOTALL)
        if not json_match:
            raise ValueError("No JSON object found in explainer response.")
        json_str = json_match.group(0)
        logger.info(f"Extracted JSON string from explainer: {json_str}")
        
        # Normalize whitespace and optionally decode unicode escapes.
        json_str = re.sub(r'\s+', ' ', json_str)
        try:
            parsed = json.loads(json_str)
        except Exception:
            # Try decoding unicode escapes if initial parse fails.
            json_str = json_str.encode('utf-8').decode('unicode_escape')
            parsed = json.loads(json_str)
        
        if not isinstance(parsed, dict) or "expected_field_info" not in parsed:
            raise ValueError("Key 'expected_field_info' not found in explainer response JSON.")
        
        return parsed["expected_field_info"]
    
    except Exception as e:
        logger.error(f"Error extracting explainer data: {str(e)}", exc_info=True)
        raise



import json
import re
import logging

logger = logging.getLogger(__name__)

def extract_plan_data(planner_response):
    """
    Extract plan and next_step from a planner response where the JSON is embedded
    in one of the message parts (typically a tool call).
    """
    try:
        messages = planner_response.new_messages()
        logger.info(f"Processing planner response message (extract_plan_data): {messages}")
        logger.info(f"Total message length: {len(str(messages))} chars")
        plan_message = None

        # Look for a part with a valid JSON structure (e.g. tool-call)
        for msg in messages:
            for part in msg.parts:
                if getattr(part, 'part_kind', '') == 'tool-call':
                    plan_message = part
                    break
            if plan_message:
                break

        logger.info(f"Found plan_message: {plan_message}")

        if not plan_message:
            raise ValueError("No JSON object found in response")

        # Prefer the args field if available; otherwise, use the content
        if hasattr(plan_message, 'args') and plan_message.args:
            json_str = json.dumps(plan_message.args.args_dict)  # assuming args_dict holds the JSON data
        else:
            json_str = plan_message.content

        logger.info(f"Extracted JSON string: {json_str}")

        # Clean the JSON string by collapsing whitespace and replacing newlines
        json_str = re.sub(r'\s+', ' ', json_str)
        json_str = json_str.replace('\n', '\\n')
        logger.info(f"Cleaned JSON string: {json_str}")

        try:
            plan_data = json.loads(json_str)
            logger.info(f"Successfully parsed JSON: {plan_data}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON: {e}")

        # Check for required fields
        if 'plan' not in plan_data or 'next_step' not in plan_data:
            raise ValueError(f"Missing required fields in response. Got: {list(plan_data.keys())}")

        return {
            'plan': plan_data.plan,
            'next_step': plan_data.next_step
        }
    except Exception as e:
        logger.error(f"Error in extract_plan_data: {str(e)}")
        raise


def extract_plan_data_NCPA(planner_response):
    """
    Extract plan and next_step from a planner response that may return a structured result.
    First, if the response has a 'data' attribute, use that. Otherwise, fallback to parsing
    the JSON from the last message's content.
    """
    try:
        messages = planner_response.new_messages()
        last_message = messages[-1]
        logger.info(f"Processing planner response (NCPA): {len(str(last_message))} chars")

        # If the response has a structured data attribute, use it directly.
        if hasattr(planner_response, 'data'):
            plan_data = {
                'plan': planner_response.data.plan,
                'next_step': planner_response.data.next_step
            }
            logger.info(f"Extracted structured data: {plan_data}")
            return plan_data

        # Otherwise, try to extract the JSON from the last message content.
        text_content = last_message.parts[0].content
        logger.info(f"Raw text content: {text_content}")

        json_match = re.search(r'\{.*\}', text_content, re.DOTALL)
        if not json_match:
            logger.error(f"Failed to find JSON object in text: {text_content}")
            raise ValueError("No JSON object found in response")

        json_str = json_match.group(0)
        logger.info(f"Extracted JSON string: {json_str}")

        # Clean the JSON string
        json_str = re.sub(r'\s+', ' ', json_str)
        json_str = json_str.replace('\n', '\\n')
        logger.info(f"Cleaned JSON string: {json_str}")

        try:
            plan_data = json.loads(json_str)
        except json.JSONDecodeError as e:
            # Try more aggressive cleaning if initial parsing fails.
            json_str = json_str.replace('"', '\\"').replace('\\n', ' ')
            try:
                plan_data = json.loads(json_str)
                logger.info(f"Parsed JSON after aggressive cleaning: {plan_data}")
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error after cleaning: {e}. Fixed string was: {json_str}")
                raise ValueError(f"Failed to parse JSON: {e}")

        if 'plan' not in plan_data or 'next_step' not in plan_data:
            logger.error(f"Missing required fields in plan_data: {plan_data}")
            raise ValueError(f"Missing required fields in response. Got: {list(plan_data.keys())}")

        return {
            'plan': plan_data.plan,
            'next_step': plan_data.next_step
        }
    except Exception as e:
        logger.error(f"Unexpected error in extract_plan_data_NCPA: {str(e)}")
        print(f"Error Type: {type(e)}")
        raise


def fix_json_string(json_str):
    """
    Walks through json_str character-by-character and, if inside a JSON string,
    escapes any double quote that does not appear to be a legitimate terminator.
    
    Heuristic:
      - When inside a string (after an unescaped double quote),
      - If we encounter a double quote (") that is not preceded by a backslash,
      - Look ahead to see if the next non-space character is a proper terminator (comma, }
        or ]). If not, assume it is an embedded quote that needs escaping.
    
    Note: This approach is heuristic and may need refinement for very tricky inputs.
    """
    result = []
    in_string = False
    escaped = False
    length = len(json_str)
    i = 0
    while i < length:
        char = json_str[i]
        if in_string:
            if escaped:
                # Whatever follows a backslash is added as is.
                result.append(char)
                escaped = False
            else:
                if char == '\\':
                    result.append(char)
                    escaped = True
                elif char == '"':
                    # We hit a double quote inside a string.
                    # Look ahead to decide if this is really the end of the string.
                    j = i + 1
                    # Skip any whitespace
                    while j < length and json_str[j].isspace():
                        j += 1
                    # If the next non-space character is a comma, a closing brace or bracket,
                    # then we assume this quote is the proper end of the string.
                    if j < length and json_str[j] in [',', '}', ']']:
                        in_string = False
                        result.append(char)
                    else:
                        # Otherwise, it is likely an unescaped inner quote.
                        result.append('\\' + char)
                else:
                    result.append(char)
        else:
            # Outside a string.
            if char == '"':
                in_string = True
            result.append(char)
        i += 1
    return ''.join(result)


def extract_critique_data(critique_response):
    """
    Extracts and returns a dict with keys 'feedback', 'terminate', and 'final_response'
    from the JSON text in the critique_response. It first attempts to parse the JSON
    normally; if that fails due to delimiter/escape errors, it will auto-correct the JSON
    string and try again.
    """
    try:
        # Get the last message (which contains the response)
        last_message = critique_response.new_messages()[-1]
        logger.info(f"Processing critique response message: {len(str(last_message))} chars")
       
        # Get the content from the first part
        text_content = last_message.parts[0].content
        logger.info(f"Raw text content: {text_content}")
       
        # Extract the JSON substring (assumes the JSON is wrapped in { ... })
        json_match = re.search(r'\{.*\}', text_content, re.DOTALL)
        if not json_match:
            logger.error(f"Failed to find JSON object in text: {text_content}")
            raise ValueError("No JSON object found in response")
       
        json_str = json_match.group(0)
        logger.info(f"Extracted JSON string: {json_str}")
       
        # Normalize/clean the JSON string (e.g. collapse extra whitespace)
        json_str = re.sub(r'\s+', ' ', json_str)
        logger.info(f"Cleaned JSON string: {json_str}")
       
        # First, try to parse the JSON as-is.
        try:
            critique_data = json.loads(json_str)
            logger.info(f"Successfully parsed JSON: {critique_data}")
        except json.JSONDecodeError as e:
            logger.error(f"Initial JSON decode error: {e}. Attempting to auto-correct the JSON string.")
            # Try to fix the JSON by escaping unescaped inner quotes.
            fixed_json_str = fix_json_string(json_str)
            logger.info(f"Fixed JSON string: {fixed_json_str}")
            try:
                critique_data = json.loads(fixed_json_str)
                logger.info(f"Successfully parsed JSON after fixing: {critique_data}")
            except json.JSONDecodeError as e2:
                logger.error(f"JSON decode error after fixing: {e2}. Fixed string was: {fixed_json_str}")
                raise ValueError(f"Failed to parse JSON even after auto-correction: {e2}")
       
        # Validate that all required fields are present.
        required_fields = ['feedback', 'terminate', 'final_response']
        missing_fields = [field for field in required_fields if field not in critique_data]
        if missing_fields:
            logger.error(f"Missing required fields in critique_data: {critique_data}")
            raise ValueError(f"Missing required fields in response: {missing_fields}")
       
        return {
            'feedback': critique_data.feedback,
            'terminate': critique_data.terminate,
            'final_response': critique_data.final_response
        }
       
    except Exception as e:
        logger.error(f"Unexpected error in extract_critique_data: {str(e)}")
        raise






@dataclass
class AgentConversationHandler:
    """Handles conversion and storage of agent conversations in OpenAI format"""
    
    def __init__(self):
        self.conversation_history: List[ChatCompletionMessageParam] = []

    def _extract_tool_call(self, response_part: Any) -> Dict[str, Any]:
        """Extract tool call information from a response part"""
        tool_call_id = getattr(response_part, 'tool_call_id', str(uuid.uuid4()))
        tool_name = getattr(response_part, 'tool_name', '')
        args = {}
        
        if hasattr(response_part, 'args'):
            # First try to use args_dict if available and non-empty
            if hasattr(response_part.args, 'args_dict') and response_part.args.args_dict:
                args = response_part.args.args_dict
            # Otherwise try args_json if available
            elif hasattr(response_part.args, 'args_json') and response_part.args.args_json:
                try:
                    args = json.loads(response_part.args.args_json)
                except json.JSONDecodeError:
                    args = {'raw_args': response_part.args.args_json}
            else:
                # Fallback: capture a string representation
                args = {'raw_args': str(response_part.args)}
        
        return {
            'id': tool_call_id,
            'type': 'function',
            'function': {
                'name': tool_name,
                'arguments': json.dumps(args)
            }
        }


    def _format_content(self, content: Any) -> str:
        """Format content into a string, handling various input types"""
        if isinstance(content, str):
            return content
        elif isinstance(content, dict):
            return json.dumps(content, indent=2)
        elif content is None:
            return ""
        else:
            try:
                return json.dumps(content, indent=2)
            except:
                return str(content)
            

    def _extract_from_model_request(self, messages: List[Any]) -> List[Dict[str, Any]]:
        """Extract message components from a list of model request/response messages"""
        extracted = []
        
        for msg in messages:
            if not hasattr(msg, 'parts'):
                continue

            for part in msg.parts:
                part_kind = getattr(part, 'part_kind', '')

                # Handle user prompts (from initial agent input)
                if part_kind == 'user-prompt':
                    extracted.append({
                        'role': 'user',
                        'content': getattr(part, 'content', '')
                    })
                    
                # Handle assistant text responses
                elif part_kind == 'text':
                    extracted.append({
                        'role': 'assistant',
                        'content': getattr(part, 'content', ''),
                        'name': 'browser_nav_agent'
                    })
                    
                # Handle tool calls
                elif part_kind == 'tool-call':
                    extracted.append({
                        'role': 'assistant',
                        'content': None,
                        'tool_calls': [self._extract_tool_call(part)]
                    })
                    
                # Handle tool responses
                elif part_kind == 'tool-return':
                    extracted.append({
                        'role': 'tool',
                        'tool_call_id': getattr(part, 'tool_call_id', ''),
                        'name': getattr(part, 'tool_name', ''),
                        'content': self._format_content(getattr(part, 'content', ''))
                    })

        return extracted

    def add_browser_nav_message(self, browser_messages: List[Any]) -> None:
        """Convert and store browser navigation agent messages"""
        messages = self._extract_from_model_request(browser_messages)
        self.conversation_history.extend(messages)

    def add_explainer_message(self, explainer_response: Any, prompt: str) -> None:
        """
        Process the explainer response and add it to the conversation history.
        This method appends the user's prompt and then adds an assistant message that contains
        the extracted expected field information (from the key "expected_field_info").
        """
        try:
            # Extract the final output from the explainer response.
            expected_field_info = explainer_response
        except Exception as e:
            logger.error(f"Error extracting explainer data: {str(e)}", exc_info=True)
            expected_field_info = ""
            raise e
            
        logger.info(f'Added user prompt in Explainer History')
        # Append the user's prompt.
        self.conversation_history.append({
            "role": "user",
            "content": prompt,
        })
        
        # Create a plain assistant message with the extracted output.
        assistant_text = expected_field_info
        logger.info(f"Assistant text: {assistant_text}")
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_text,
            "name": "explainer_agent",
        })


    def add_planner_message(self, planner_response: Any, prompt: str, NCPA: bool) -> None:
        # Append the user's prompt.
        self.conversation_history.append({
            "role": "user",
            "content": prompt,
        })
        # Directly use the structured output from the planner's result_type.
        plan_data = planner_response.data  # This is now an instance of PLANNER_AGENT_OP or NCPA_OP.
        # In all cases, 'plan' and 'next_step' are available.
        plan = plan_data.plan
        next_step = plan_data.next_step

        if NCPA:
            # In no-critique mode, the structured response includes additional fields.
            terminate = plan_data.terminate
            final_response = plan_data.final_response
            assistant_text = (
                f"Plan: {plan}\n"
                f"Next Step: {next_step}\n"
                f"Terminate: {terminate}\n"
                f"Final Response: {final_response}"
            )
        else:
            assistant_text = f"Plan: {plan}\nNext Step: {next_step}"

        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_text,
            "name": "planner_agent",
        })



    def add_critique_message(self, critique_response: Any, prompt: str) -> None:
        logger.debug(f"Inside add_critique_message function : {critique_response}")
        # Directly use the structured output (result_type is CritiqueOutput).
        critique_data = critique_response.data
        feedback = critique_data.feedback
        terminate = critique_data.terminate
        final_response = critique_data.final_response

        # Append the user's prompt.
        self.conversation_history.append({
            "role": "user",
            "content": prompt,
        })
        logger.debug(f"Appended user message in history: {prompt}")

        # Build the assistant message text.
        assistant_text = (
            f"Feedback: {feedback}\n"
            f"Terminate: {terminate}\n"
            f"Final Response: {final_response}"
        )
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_text,
            "name": "critique_agent",
        })
        logger.debug(f"Appended assistant message in history: {assistant_text}")
        logger.debug(f"Final look at Critique Agent's conversation history: {self.conversation_history}")




    def add_ss_analysis_message(self, ss_analysis_response: Any, step: str) -> None:
        """Convert and store ss analysis messages"""
        # Add user message with actual step info
        user_message = {
            'role': 'user',
            'content': f"Analyze screenshot changes for step: {step}",
            
        }
        self.conversation_history.append(user_message)
        
        # Convert SS content to string if it's not already
        content = self._format_content(ss_analysis_response)

        # Add assistant message with final_result tool call
        tool_call_id = str(uuid.uuid4())
        assistant_message = {
            'role': 'assistant',
            'content': None,
            'name': 'ss_analyzer',
            'tool_calls': [{
                'id': tool_call_id,
                'type': 'function',
                'function': {
                    'name': 'final_result',
                    'arguments': json.dumps({
                        'analysis': content
                    })
                }
            }]
        }
        self.conversation_history.append(assistant_message)
        
        # Add tool return response
        tool_message = {
            'role': 'tool',
            'tool_call_id': tool_call_id,
            'name': 'final_result',
            'content': 'Final result processed.'
        }
        self.conversation_history.append(tool_message)



    
    def get_full_conversation(self) -> List[ChatCompletionMessageParam]:
        """Get the full conversation history without duplicating messages"""
        return list(self.conversation_history)


    def _extract_from_raw_messages(self, raw_messages: list) -> list:
        """Process raw browser messages without DOM filtering"""
        extracted = []
        
        for msg in raw_messages:
            if not hasattr(msg, 'parts'):
                continue
                
            for part in msg.parts:
                # Handle tool calls
                if getattr(part, 'part_kind', '') == 'tool-call':
                    extracted.append({
                        'role': 'assistant',
                        'content': None,
                        'tool_calls': [self._extract_tool_call(part)]
                    })
                
                # Handle tool responses (including raw DOM)
                elif getattr(part, 'part_kind', '') == 'tool-return':
                    extracted.append({
                        'role': 'tool',
                        'tool_call_id': getattr(part, 'tool_call_id', ''),
                        'name': getattr(part, 'tool_name', ''),
                        'content': self._format_content(getattr(part, 'content', ''))
                    })
                
                # Handle text responses
                elif getattr(part, 'part_kind', '') == 'text':
                    extracted.append({
                        'role': 'assistant',
                        'content': getattr(part, 'content', ''),
                        'name': 'browser_nav_agent'
                    })
        
        return extracted
    

    def _is_filtered_browser_message(self, msg: dict) -> bool:
        """Check if message is a filtered browser agent message"""
        return (
            msg.get('name') == 'browser_nav_agent' or 
            any(tc['function']['name'] in {'get_dom_text', 'get_dom_fields'} 
                for tc in msg.get('tool_calls', []))
        )

    def add_ss_analysis_message(self, ss_analysis_response: Any) -> None:
        """Convert and store ss analysis messages"""
        tool_call_id = str(uuid.uuid4())
        
        assistant_message = {
            'role': 'assistant',
            'content': None,
            'tool_calls': [{
                'id': tool_call_id,
                'type': 'function',
                'function': {
                    'name': 'ss_analyzer',
                    'arguments': json.dumps({
                        'analysis_request': 'analyze_ss'
                    })
                }
            }]
        }
        self.conversation_history.append(assistant_message)

        # Convert SS content to string if it's not already
        content = self._format_content(ss_analysis_response)

        tool_message = {
            'role': 'tool',
            'tool_call_id': tool_call_id,
            'name': 'ss_analyzer',
            'content': content
        }
        self.conversation_history.append(tool_message)

    
    def add_user_message(self, command: str) -> None:
        """Add user input messages"""
        user_message = {
            'role': 'user',
            'content': command
        }
        self.conversation_history.append(user_message)

    def add_system_message(self, content: str) -> None:
        """Add system messages"""
        system_message = {
            'role': 'system',
            'content': content
        }
        self.conversation_history.append(system_message)

    def get_conversation_history(self) -> List[ChatCompletionMessageParam]:
        """Get the full conversation history in OpenAI format"""
        return self.conversation_history


# In openai_msg_parser.py (or wherever ConversationStorage is defined)
from datetime import datetime
import os
import json

class ConversationStorage:
    def __init__(self, base_dir: str = None, job_id: str = None, file_name: str = "conversation.json"):
        """
        Initialize ConversationStorage with base directory, job id, and the file name for saving.
        Creates the conversation.json file immediately upon initialization.
        """
        self.base_dir = base_dir or os.path.join(os.getcwd(), "temp")
        os.makedirs(self.base_dir, exist_ok=True)
        self.storage_dir = os.path.join(self.base_dir)
        self.job_id = job_id
        self.file_name = file_name
        os.makedirs(self.storage_dir, exist_ok=True)
        
        # Initialize the file path and create the file immediately
        self.current_filepath = self._get_filepath()
        self._initialize_file()
    
    def _get_filepath(self, prefix: str = "task") -> str:
        """
        Get the filepath for the conversation, creating the subdirectory if needed.
        """
        if self.job_id:
            dirname = f"{prefix}_{self.job_id}"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dirname = f"{prefix}_{timestamp}"
        
        directory = os.path.join(self.storage_dir, dirname)
        os.makedirs(directory, exist_ok=True)
        return os.path.join(directory, self.file_name)
    
    def _initialize_file(self):
        """
        Initialize the conversation.json file with an empty array if it doesn't exist.
        """
        if not os.path.exists(self.current_filepath):
            with open(self.current_filepath, 'w') as f:
                json.dump([], f, indent=2)
    
    def _read_existing_messages(self, filepath: str):
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    return json.load(f)
        except json.JSONDecodeError:
            return []
        return []
    
    def save_conversation(self, messages, prefix: str = "task") -> str:
        """
        Append conversation messages to the JSON file.
        """
        serializable_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                serializable_messages.append(msg)
            else:
                serializable_messages.append({
                    'role': msg.role,
                    'content': msg.content,
                    'name': getattr(msg, 'name', None)
                })
        
        existing_messages = self._read_existing_messages(self.current_filepath)
        last_message_index = len(existing_messages)
        new_messages = serializable_messages[last_message_index:]
        updated_messages = existing_messages + new_messages
        
        with open(self.current_filepath, 'w') as f:
            json.dump(updated_messages, f, indent=2)
            
        return self.current_filepath

    def reset_file(self):
        """Reset the current file path and create a new file for a new conversation."""
        self.current_filepath = self._get_filepath()
        self._initialize_file()
