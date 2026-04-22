from pydantic import BaseModel, Field
from typing_extensions import Literal

import ipaddress
from urllib.parse import urlparse

import requests
from typing import Dict, Any, List

from cerebrum.config.config_manager import config

aios_kernel_url = config.get_kernel_url()

class Query(BaseModel):
    """
    Base class for all query types in the AIOS system.
    
    This class serves as the foundation for specialized query classes like LLMQuery,
    MemoryQuery, StorageQuery, and ToolQuery. It defines the minimum structure required
    for a valid query within the AIOS ecosystem.
    
    Attributes:
        query_class: Identifier for the query type, must be one of 
                     ["llm", "memory", "storage", "tool"]
    """
    query_class: Literal["llm", "memory", "storage", "tool"]
    
class Response(BaseModel):
    """
    Base class for all response types in the AIOS system.
    
    This class serves as the foundation for specialized response classes like LLMResponse,
    MemoryResponse, StorageResponse, and ToolResponse. It defines the minimum structure
    required for a valid response within the AIOS ecosystem.
    
    Attributes:
        response_class: Identifier for the response type, must be one of 
                        ["llm", "memory", "storage", "tool"]
    """
    response_class: Literal["llm", "memory", "storage", "tool"]


def _should_bypass_proxy(base_url: str) -> bool:
    hostname = urlparse(base_url).hostname
    if not hostname:
        return False

    normalized = hostname.strip("[]").lower()
    if normalized in {"localhost", "127.0.0.1", "::1"}:
        return True

    try:
        ip_addr = ipaddress.ip_address(normalized)
    except ValueError:
        return normalized.endswith(".local")

    return bool(ip_addr.is_loopback or ip_addr.is_private or ip_addr.is_link_local)


def _session_for_url(base_url: str) -> requests.Session:
    session = requests.Session()
    if _should_bypass_proxy(base_url):
        session.trust_env = False
    return session


def post(
    base_url: str,
    endpoint: str,
    data: Dict[str, Any],
    timeout: float | tuple[float, float] | None = None,
) -> Dict[str, Any]:
    """
    Send a POST request to the specified API endpoint.
    
    Args:
        base_url: Base URL of the API server
        endpoint: API endpoint path
        data: JSON-serializable dictionary to be sent in the request body
        
    Returns:
        Parsed JSON response as a dictionary
        
    Raises:
        requests.exceptions.HTTPError: If the request fails
    """
    with _session_for_url(base_url) as session:
        response = session.post(f"{base_url}{endpoint}", json=data, timeout=timeout)
        response.raise_for_status()
        return response.json()


def get(
    base_url: str,
    endpoint: str,
    params: Dict[str, Any] | None = None,
    timeout: float | tuple[float, float] | None = None,
) -> Dict[str, Any]:
    with _session_for_url(base_url) as session:
        response = session.get(f"{base_url}{endpoint}", params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()

def send_request(
    agent_name: str,
    query: Query,
    base_url: str = aios_kernel_url,
    timeout: float | tuple[float, float] | None = None,
):
    """
    Send a query to the AIOS kernel on behalf of an agent.
    
    Args:
        agent_name: Name of the agent making the request
        query: Query object containing the request details
        base_url: Base URL of the AIOS kernel
        
    Returns:
        Parsed JSON response from the AIOS kernel
    """
    query_type = query.query_class
    result = post(
        base_url,
        "/query",
        {
            'query_type': query_type,
            'agent_name': agent_name,
            'query_data': query.model_dump(),
        },
        timeout=timeout,
    )

    return result
