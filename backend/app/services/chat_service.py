"""
Chat service - LangChain agent with tools for spatial queries.
"""
from typing import List, Dict, Optional, Any
from datetime import datetime
import httpx

from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import tool
from langchain_core.messages import HumanMessage, AIMessage


# In-memory conversation storage
_conversations: Dict[str, List[Dict]] = {}


def get_conversation_history(session_id: str) -> List[Dict]:
    """Get conversation history for a session."""
    return _conversations.get(session_id, [])


def add_to_conversation(session_id: str, role: str, content: str) -> None:
    """Add a message to conversation history."""
    if session_id not in _conversations:
        _conversations[session_id] = []
    
    _conversations[session_id].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    })


def clear_conversation(session_id: str) -> None:
    """Clear conversation history for a session."""
    if session_id in _conversations:
        del _conversations[session_id]


# Tool definitions that wrap existing API endpoints
BASE_URL = "http://localhost:8000"


@tool
def query_point_facility(lat: float, lng: float) -> dict:
    """
    Find which facility serves a given location based on Voronoi cells.
    
    Args:
        lat: Latitude of the location to query
        lng: Longitude of the location to query
    
    Returns:
        Information about the facility serving this location
    """
    with httpx.Client() as client:
        response = client.post(
            f"{BASE_URL}/api/dcel/query-point",
            json={"lat": lat, "lng": lng}
        )
        return response.json()


@tool
def get_top_facilities_by_population(top_n: int = 10, state: str = None) -> dict:
    """
    Get facilities ranked by population served.
    
    Args:
        top_n: Number of top facilities to return (default 10, max 100)
        state: Optional state name to filter results (e.g., 'Maharashtra', 'Delhi')
    
    Returns:
        List of facilities ranked by population served
    """
    with httpx.Client() as client:
        response = client.post(
            f"{BASE_URL}/api/dcel/top-by-population",
            json={"top_n": min(top_n, 100), "state": state}
        )
        return response.json()


@tool
def get_facility_neighbors(facility_id: str) -> dict:
    """
    Find facilities adjacent to a given facility (sharing a border).
    
    Args:
        facility_id: The ID of the facility to find neighbors for
    
    Returns:
        List of adjacent facilities
    """
    with httpx.Client() as client:
        response = client.get(f"{BASE_URL}/api/dcel/adjacent/{facility_id}")
        return response.json()


@tool
def get_dcel_summary() -> dict:
    """
    Get summary of the current spatial index including number of facilities and basic stats.
    
    Returns:
        Summary of the current DCEL structure
    """
    with httpx.Client() as client:
        response = client.get(f"{BASE_URL}/api/dcel/summary")
        return response.json()


@tool
def find_facilities_in_area(min_lat: float, min_lng: float, max_lat: float, max_lng: float) -> dict:
    """
    Find all facilities whose service areas intersect a bounding box region.
    
    Args:
        min_lat: South boundary latitude
        min_lng: West boundary longitude
        max_lat: North boundary latitude
        max_lng: East boundary longitude
    
    Returns:
        List of facilities in the specified region
    """
    with httpx.Client() as client:
        response = client.post(
            f"{BASE_URL}/api/dcel/range-query",
            json={
                "min_lat": min_lat,
                "min_lng": min_lng,
                "max_lat": max_lat,
                "max_lng": max_lng
            }
        )
        return response.json()


SYSTEM_PROMPT = """You are a spatial analytics assistant for Tessera, a platform that helps policymakers and urban planners optimize facility placement using Voronoi diagrams.

You help users analyze facility placement and coverage. You have access to tools for:
- Finding which facility serves a specific location
- Getting top facilities ranked by population served
- Finding adjacent/neighboring facilities
- Querying facilities within geographic regions
- Getting summary statistics

When answering questions:
1. Use your tools to query actual data - never make up numbers
2. Explain spatial concepts in simple terms for non-technical policymakers
3. Always include relevant numbers with units (population counts, km, etc.)
4. Be concise but informative

Current context: You are working with facility data in India. Common states include Maharashtra, Delhi, Karnataka, Tamil Nadu, Kerala, Gujarat, Uttar Pradesh, West Bengal, etc.

If the user asks about data that hasn't been loaded yet (no Voronoi diagram computed), politely explain they need to upload facility data first."""


def create_chat_agent(api_key: str) -> AgentExecutor:
    """Create a LangChain agent with spatial query tools."""
    llm = ChatOpenAI(
        model="gpt-4",
        api_key=api_key,
        temperature=0
    )
    
    tools = [
        query_point_facility,
        get_top_facilities_by_population,
        get_facility_neighbors,
        get_dcel_summary,
        find_facilities_in_area
    ]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad")
    ])
    
    agent = create_openai_functions_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True)


def convert_history_to_messages(history: List[Dict]) -> List[Any]:
    """Convert conversation history to LangChain message format."""
    messages = []
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))
    return messages


async def process_chat_message(
    session_id: str,
    message: str,
    api_key: str
) -> str:
    """
    Process a chat message and return the AI response.
    
    Args:
        session_id: Unique session identifier
        message: User's message
        api_key: OpenAI API key
        
    Returns:
        AI assistant's response
    """
    # Get conversation history
    history = get_conversation_history(session_id)
    
    # Add user message to history
    add_to_conversation(session_id, "user", message)
    
    try:
        # Create agent and invoke
        agent = create_chat_agent(api_key)
        
        result = agent.invoke({
            "input": message,
            "chat_history": convert_history_to_messages(history)
        })
        
        response = result.get("output", "I couldn't process that request.")
        
        # Add assistant response to history
        add_to_conversation(session_id, "assistant", response)
        
        return response
        
    except Exception as e:
        error_msg = f"Error processing request: {str(e)}"
        add_to_conversation(session_id, "assistant", error_msg)
        return error_msg
