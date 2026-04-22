import os
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Union
from typing_extensions import Literal

from cerebrum.utils.communication import Query, Response, get, send_request

from cerebrum.config.config_manager import config

aios_kernel_url = config.get_kernel_url()

import requests


def _kernel_required(require_kernel: bool | None = None) -> bool:
    if require_kernel is not None:
        return require_kernel
    return os.getenv("AIOS_REQUIRE_KERNEL", "").lower() in {"1", "true", "yes", "on"}


def _resolve_model_name(llms: List[Dict[str, Any]] | None = None) -> str:
    if llms:
        first = llms[0] or {}
        if first.get("name"):
            return str(first["name"])
    return os.getenv("AIOS_LLM_MODEL", "qwen3-max")


def _direct_openai_chat(
    *,
    agent_name: str,
    messages: List[Dict[str, Any]],
    llms: List[Dict[str, Any]] | None = None,
    response_format: Dict[str, Dict] | None = None,
) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("AIOS_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    if not api_key or not base_url:
        raise RuntimeError("Direct LLM fallback is not configured")

    url = base_url.rstrip("/") + "/chat/completions"
    payload: Dict[str, Any] = {
        "model": _resolve_model_name(llms),
        "messages": messages,
        "temperature": 0.7,
    }
    if response_format:
        payload["response_format"] = response_format

    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=180,
    )
    response.raise_for_status()
    data = response.json()
    content = (((data.get("choices") or [{}])[0]).get("message") or {}).get("content", "")
    return {
        "response": {
            "response_class": "llm",
            "response_message": content,
            "tool_calls": None,
            "finished": True,
            "error": None,
            "status_code": 200,
            "agent_name": agent_name,
            "backend": "openai-direct",
        }
    }

def list_available_llms():
    """
    List all available LLMs.
    """
    return get(aios_kernel_url, "/core/llms/list", timeout=30)

class LLMQuery(Query):
    """
    Query class for LLM operations.
    
    This class represents the input structure for performing various LLM actions
    such as chatting, using tools, or operating on files.
    
    Attributes:
        query_class: Identifier for LLM queries, always set to "llm"
        llms: Optional list of LLM configurations with format:
            [
                {
                    "name": str,           # Name of the LLM (e.g., "gpt-4")
                    "temperature": float,  # Sampling temperature (0.0-2.0)
                    "max_tokens": int,     # Maximum tokens to generate
                    "top_p": float,        # Nucleus sampling parameter (0.0-1.0)
                    "frequency_penalty": float,  # Frequency penalty (-2.0-2.0)
                    "presence_penalty": float    # Presence penalty (-2.0-2.0)
                }
            ]
        messages: List of message dictionaries with format:
            [
                {
                    "role": str,      # One of ["system", "user", "assistant"]
                    "content": str,   # The message content
                    "name": str,      # Optional name for the message sender
                    "function_call": dict,  # Optional function call details
                    "tool_calls": list     # Optional tool call details
                }
            ]
        tools: Optional list of available tools with format:
            [
                {
                    "name": str,        # Tool identifier
                    "description": str, # Tool description
                    "parameters": {     # Tool parameters schema
                        "type": "object",
                        "properties": {
                            "param1": {"type": "string"},
                            "param2": {"type": "number"}
                        },
                        "required": ["param1"]
                    }
                }
            ]
        action_type: Type of action to perform, one of:
            - "chat": Simple conversation
            - "tool_use": Using external tools
            - "operate_file": File operations
        message_return_type: Desired format of the response
        response_format: Specific JSON format of the response, e.g., 
            {
                "type": "json_schema", 
                "json_schema": {
                    "name": "response",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "keywords": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                }
                            },
                            "context": {
                                "type": "string"
                            },
                            "tags": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                }
                            }
                        },
                        "required": ["keywords", "context", "tags"],
                        "additionalProperties": false
                    },
                    "strict": true
                }
            }
    
    Examples:
        ```python
        # Simple chat query
        query = LLMQuery(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant."
                },
                {
                    "role": "user",
                    "content": "What is Python?"
                }
            ],
            action_type="chat"
        )
        
        # Tool use query with specific LLM configuration
        query = LLMQuery(
            llms=[{
                "name": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 500
            }],
            messages=[
                {
                    "role": "user",
                    "content": "Calculate 2 + 2"
                }
            ],
            tools=[{
                "name": "calculator",
                "description": "Performs basic arithmetic operations",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["add", "subtract", "multiply", "divide"]
                        },
                        "numbers": {
                            "type": "array",
                            "items": {"type": "number"}
                        }
                    },
                    "required": ["operation", "numbers"]
                }
            }],
            action_type="tool_use"
        )
        ```
    """
    query_class: str = "llm"
    llms: Optional[List[Dict[str, Any]]] = Field(default=None)
    messages: List[Dict[str, Union[str, Any]]]
    tools: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    action_type: Literal["chat", "chat_with_json_output", "chat_with_tool_call_output", "call_tool", "operate_file"] = Field(default="chat")
    temperature: float = Field(default=1.0)
    max_new_tokens: int = Field(default=2000)
    message_return_type: Literal["text", "json"] = Field(default="text")
    response_format: Optional[Dict[str, Any]] = Field(default=None)

    class Config:
        arbitrary_types_allowed = True

class LLMResponse(Response):
    """
    Response class for LLM operations.
    
    This class represents the output structure after performing LLM actions.
    
    Attributes:
        response_class: Identifier for LLM responses, always "llm"
        response_message: Generated response text
        tool_calls: List of tool calls made during processing, format:
            [
                {
                    "name": str,        # Tool name
                    "parameters": dict,  # Parameters used
                }
            ]
        finished: Whether processing completed successfully
        error: Error message if any
        status_code: HTTP status code
        
    Examples:
        ```python
        # Successful chat response
        response = LLMResponse(
            response_message="Python is a high-level programming language...",
            finished=True,
            status_code=200
        )
        
        # Tool use response with calculator
        response = LLMResponse(
            response_message=None,
            tool_calls=[{
                "name": "calculator",
                "parameters": {
                    "operation": "add",
                    "numbers": [2, 2]
                },
            }],
            finished=True,
            status_code=200
        )
        ```
    """
    response_class: str = "llm"
    response_message: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    finished: bool = False
    error: Optional[str] = None
    status_code: int = 200

    class Config:
        arbitrary_types_allowed = True

def llm_chat(
        agent_name: str, 
        messages: List[Dict[str, Any]], 
        base_url: str = aios_kernel_url,
        llms: List[Dict[str, Any]] = None,
        require_kernel: bool | None = None,
    ) -> LLMResponse:
    """
    Perform a chat interaction with the LLM.
    
    Args:
        agent_name: Name of the agent making the request
        messages: List of message dictionaries with format:
            [
                {
                    "role": "system"|"user"|"assistant",
                    "content": str,
                    "name": str  # Optional
                }
            ]
        base_url: API base URL
        llms: Optional list of LLM configurations
        
    Returns:
        LLMResponse containing the generated response
        
    Examples:
        ```python
        response = llm_chat(
            "agent1",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant."
                },
                {
                    "role": "user",
                    "content": "Explain quantum computing."
                }
            ],
            llms=[{
                "name": "gpt-4o-mini",
                "backend": "openai"
            }]
        )
        ```
    """
    query = LLMQuery(
        llms=llms,
        messages=messages,
        tools=None,
        action_type="chat"
    )
    try:
        return send_request(agent_name, query, base_url)
    except requests.RequestException:
        if _kernel_required(require_kernel):
            raise
        return _direct_openai_chat(
            agent_name=agent_name,
            messages=messages,
            llms=llms,
        )

def llm_chat_with_json_output(
        agent_name: str, 
        messages: List[Dict[str, Any]], 
        base_url: str = aios_kernel_url,
        llms: List[Dict[str, Any]] = None,
        response_format: Dict[str, Dict] = None,
        require_kernel: bool | None = None,
    ) -> LLMResponse:
    """
    Perform a chat interaction with the LLM and return a JSON-formatted output.
    
    Args:
        agent_name: Name of the agent making the request
        messages: List of message dictionaries with format:
            [
                {
                    "role": "system"|"user"|"assistant",
                    "content": str,
                    "name": str  # Optional
                }
            ]
        base_url: API base URL
        llms: Optional list of LLM configurations
        response_format: JSON schema specifying the required output format
        
    Returns:
        LLMResponse containing the generated JSON response
        
    Examples:
        ```python
        response = llm_chat_with_json_output(
            "agent1",
            messages=[
                {
                    "role": "system",
                    "content": "Extract keywords from the user query."
                },
                {
                    "role": "user",
                    "content": "Analyze the impact of climate change on biodiversity."
                }
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "keywords",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "keywords": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        }
                    }
                }
            }
        )
        ```
    """
    query = LLMQuery(
        llms=llms,
        messages=messages,
        message_return_type="json",
        action_type="chat_with_json_output",
        response_format=response_format
    )
    try:
        return send_request(agent_name, query, base_url)
    except requests.RequestException:
        if _kernel_required(require_kernel):
            raise
        return _direct_openai_chat(
            agent_name=agent_name,
            messages=messages,
            llms=llms,
            response_format=response_format,
        )

def llm_chat_with_tool_call_output(
        agent_name: str, 
        messages: List[Dict[str, Any]], 
        tools: List[Dict[str, Any]],
        base_url: str = aios_kernel_url,
        llms: List[Dict[str, Any]] = None
    ) -> LLMResponse:
    """
    Perform a chat interaction with the LLM and return a tool call output.
    
    Args:
        agent_name: Name of the agent making the request
        messages: List of message dictionaries with format:
            [
                {
                    "role": "system"|"user"|"assistant",
                    "content": str
                }
            ]
        tools: List of available tools with format:
            [
                {
                    "name": str,  # Tool identifier
                    "description": str,  # Tool description
                    "parameters": {  # JSON Schema for parameters
                        "type": "object",
                        "properties": {...},
                        "required": [...]
                    }
                }
            ]
        base_url: API base URL
        llms: Optional list of LLM configurations with format:
            [
                {
                    "name": str,  # e.g., "gpt-4o-mini"
                    "backend": str  # e.g., "openai"
                }
            ]
        
    Returns:
        LLMResponse containing tool calls and results
        
    Examples:
        ```python
        # Calculator tool example
        response = llm_call_tool(
            "agent1",
            messages=[{
                "role": "user",
                "content": "search core idea of AIOS paper"
            }],
            tools=[{
                "name": "demo_author/arxiv", 
                "description": "Query articles or topics in arxiv", 
                "parameters": {
                    "type": "object", 
                    "properties": {
                        "query": {
                            "type": "string", 
                            "description": "Input query that describes what to search in arxiv"
                        }
                    }, 
                    "required": ["query"]
                }
            }],
            llms=[{
                "name": "gpt-4o-mini",
                "backend": "openai"
            }]
        )
        ```
    """
    query = LLMQuery(
        llms=llms,
        messages=messages,
        tools=tools,
        action_type="chat_with_tool_call_output"
    )
    return send_request(agent_name, query, base_url)


def llm_call_tool(
        agent_name: str, 
        messages: List[Dict[str, Any]], 
        tools: List[Dict[str, Any]], 
        base_url: str = aios_kernel_url,
        llms: List[Dict[str, Any]] = None
    ) -> LLMResponse:
    """
    Use LLM to call tools based on user input.
    
    Args:
        agent_name: Name of the agent making the request
        messages: List of message dictionaries with format:
            [
                {
                    "role": "system"|"user"|"assistant",
                    "content": str
                }
            ]
        tools: List of available tools with format:
            [
                {
                    "name": str,  # Tool identifier
                    "description": str,  # Tool description
                    "parameters": {  # JSON Schema for parameters
                        "type": "object",
                        "properties": {...},
                        "required": [...]
                    }
                }
            ]
        base_url: API base URL
        llms: Optional list of LLM configurations with format:
            [
                {
                    "name": str,  # e.g., "gpt-4o-mini"
                    "backend": str  # e.g., "openai"
                }
            ]
        
    Returns:
        LLMResponse containing tool calls and results
        
    Examples:
        ```python
        # Calculator tool example
        response = llm_call_tool(
            "agent1",
            messages=[{
                "role": "user",
                "content": "search core idea of AIOS paper"
            }],
            tools=[{
                "name": "demo_author/arxiv", 
                "description": "Query articles or topics in arxiv", 
                "parameters": {
                    "type": "object", 
                    "properties": {
                        "query": {
                            "type": "string", 
                            "description": "Input query that describes what to search in arxiv"
                        }
                    }, 
                    "required": ["query"]
                }
            }],
            llms=[{
                "name": "gpt-4o-mini",
                "backend": "openai"
            }]
        )
        ```
    """
    query = LLMQuery(
        llms=llms,
        messages=messages,
        tools=tools,
        action_type="call_tool"
    )
    return send_request(agent_name, query, base_url)

def llm_operate_file(
        agent_name: str, 
        messages: List[Dict[str, Any]], 
        tools: List[Dict[str, Any]] = None, 
        base_url: str = aios_kernel_url,
        llms: List[Dict[str, Any]] = None
    ) -> LLMResponse:
    """
    Use LLM to perform file operations.
    
    Args:
        agent_name: Name of the agent making the request
        messages: List of message dictionaries with format:
            [
                {
                    "role": "system"|"user"|"assistant",
                    "content": str,
                }
            ]
        tools: a list of tools, default as None in this API
        base_url: API base URL
        llms: Optional list of LLM configurations
        
    Returns:
        LLMResponse containing file operation results
        
    Examples:
        ```python
        # Create a Python script
        response = llm_operate_file(
            "terminal",
            messages=[{
                "role": "user",
                "content": "Write this is AIOS into the aios.txt"
            }],
        ),
        llms: Optional list of LLM configurations with format:
        [
            {
                "name": str,  # e.g., "gpt-4o-mini"
                "backend": str  # e.g., "openai"
            }
        ]
        ```
    """
    query = LLMQuery(
        llms=llms,
        messages=messages,
        tools=tools,
        action_type="operate_file"
    )
    return send_request(agent_name, query, base_url)
