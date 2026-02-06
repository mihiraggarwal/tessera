"""
Chat service - LangChain agent with tools for spatial queries.
Supports multiple AI providers: OpenAI and Google Gemini.
"""
from typing import List, Dict, Optional, Any
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from app.services.dcel import get_current_dcel


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
    print(f"[TOOL DEBUG] query_point_facility called with lat={lat}, lng={lng}")
    dcel = get_current_dcel()
    if not dcel:
        return {"error": "No Voronoi diagram available. Please load facilities and compute Voronoi first."}
        
    face = dcel.point_query(lat, lng)
    if not face:
        return {"found": False}
        
    props = face.properties or {}
    
    # Optimization: Prune 'properties'
    clean_props = {k: v for k, v in props.items() if isinstance(v, (str, int, float)) and len(str(v)) < 100}

    result = {
        "found": True,
        "facility_id": face.facility_id,
        "facility_name": face.facility_name,
        "population": props.get('population'),
        "area_km2": props.get('area_sq_km'),
        "properties": clean_props
    }
    
    print(f"[TOOL DEBUG] query_point_facility response: {result}")
    return result


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
    # Convert to int in case LLM passes float
    top_n_int = int(top_n) if top_n else 10
    print(f"[TOOL DEBUG] get_top_facilities called with top_n={top_n_int}, state={state}")
    
    dcel = get_current_dcel()
    if not dcel:
        return {"error": "No Voronoi diagram available. Please load facilities and compute Voronoi first."}

    facilities = dcel.get_facilities_by_population(top_n=min(top_n_int, 100), state=state)
    
    # Optimization and formatting
    optimized_result = []
    for item in facilities:
        clean_item = {
            "name": item.get("name"),
            "population": item.get("population"),
            "id": item.get("facility_id")
        }
        
        # Filter properties
        props = item.get("properties", {})
        clean_props = {k: v for k, v in props.items() if isinstance(v, (str, int, float)) and len(str(v)) < 100}
        if clean_props:
            clean_item["details"] = clean_props
            
        optimized_result.append(clean_item)
        
    print(f"[TOOL DEBUG] get_top_facilities response (optimized): {str(optimized_result)[:500]}...")
    return optimized_result


@tool
def get_facility_neighbors(facility_id: str) -> dict:
    """
    Find facilities adjacent to a given facility (sharing a border).
    
    Args:
        facility_id: ID of the facility to find neighbors for
    
    Returns:
        List of adjacent facilities and their basic info
    """
    dcel = get_current_dcel()
    if not dcel:
        return {"error": "No Voronoi diagram available."}
        
    face = dcel.get_face_by_facility_id(facility_id)
    if not face:
        return {"error": f"Facility '{facility_id}' not found"}
        
    adjacent_ids = dcel.get_adjacent_facilities(facility_id)
    
    adjacent_info = []
    for adj_id in adjacent_ids:
        adj_face = dcel.get_face_by_facility_id(adj_id)
        if adj_face:
            adjacent_info.append({
                "facility_id": adj_face.facility_id,
                "facility_name": adj_face.facility_name
            })
            
    return {
        "facility_id": facility_id,
        "facility_name": face.facility_name,
        "adjacent_count": len(adjacent_info),
        "adjacent_facilities": adjacent_info
    }


@tool
def get_dcel_summary() -> dict:
    """
    Get summary of the current spatial index including number of facilities and basic stats.
    
    Returns:
        Summary of the current DCEL structure
    """
    print("[TOOL DEBUG] get_dcel_summary called")
    dcel = get_current_dcel()
    
    if dcel is None:
        return {
            "available": False,
            "message": "No Voronoi diagram has been computed yet."
        }
    
    result = {
        "available": True,
        "data": dcel.to_dict()
    }
    print(f"[TOOL DEBUG] get_dcel_summary response: {str(result)[:200]}...")
    return result


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
    print(f"[TOOL DEBUG] find_facilities called with bounds={min_lat},{min_lng} to {max_lat},{max_lng}")
    dcel = get_current_dcel()
    if not dcel:
        return {"error": "No Voronoi diagram available."}
        
    faces = dcel.range_query(min_lat, min_lng, max_lat, max_lng)
    
    facilities = [
        {
            "facility_id": face.facility_id,
            "facility_name": face.facility_name,
            "population": face.properties.get('population') if face.properties else None,
            "area_km2": face.properties.get('area_sq_km') if face.properties else None
        }
        for face in faces
    ]
    
    return {
        "count": len(facilities),
        "facilities": facilities
    }


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


def create_chat_agent(api_key: str, provider: str = "openai") -> AgentExecutor:
    """
    Create a LangChain agent with spatial query tools.
    
    Args:
        api_key: API key for the chosen provider
        provider: AI provider ('openai' or 'gemini')
    
    Returns:
        AgentExecutor configured with the appropriate LLM
    """
    # Create LLM based on provider
    if provider.lower() == "gemini":
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0
        )
    else:  # default to openai
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
    
    agent = create_tool_calling_agent(llm, tools, prompt)
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
    api_key: str,
    provider: str = "openai"
) -> str:
    """
    Process a chat message and return the AI response.
    
    Args:
        session_id: Unique session identifier
        message: User's message
        api_key: API key for the chosen provider
        provider: AI provider ('openai' or 'gemini')
        
    Returns:
        AI assistant's response
    """
    # Get conversation history
    history = get_conversation_history(session_id)
    
    # Add user message to history
    add_to_conversation(session_id, "user", message)
    
    try:
        # Create agent and invoke
        # Create LLM based on provider
        if provider.lower() == "gemini":
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                google_api_key=api_key,
                temperature=0,
                timeout=120.0  # Increase timeout for complex tool chains
            )
        else:  # default to openai
            llm = ChatOpenAI(
                model="gpt-4",
                api_key=api_key,
                temperature=0,
                timeout=120.0
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
        
        agent = create_tool_calling_agent(llm, tools, prompt)
        agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

        print(f"[CHAT DEBUG] Processing message: {message[:100]}...")
        print(f"[CHAT DEBUG] Provider: {provider}")
        
        result = agent_executor.invoke({
            "input": message,
            "chat_history": convert_history_to_messages(history)
        })
        
        response = result.get("output", "I couldn't process that request.")
        print(f"[CHAT DEBUG] Response received: {response[:200]}...")
        
        # Add assistant response to history
        add_to_conversation(session_id, "assistant", response)
        
        return response
        
    except Exception as e:
        print(f"[CHAT DEBUG] ERROR: {str(e)}")
        error_msg = f"Error processing request: {str(e)}"
        add_to_conversation(session_id, "assistant", error_msg)
        return error_msg
