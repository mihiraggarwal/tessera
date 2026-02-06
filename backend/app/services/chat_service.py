"""
Chat service - LangChain agent with Python REPL for spatial queries.
Supports multiple AI providers: OpenAI and Google Gemini.

This implementation uses a sandboxed Python execution environment
allowing the LLM to write arbitrary queries against the DCEL,
with an agentic retry loop for self-correction.
"""
from typing import List, Dict, Optional, Any
from datetime import datetime
from difflib import get_close_matches

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import tool
from langchain_core.messages import HumanMessage, AIMessage

from app.services.dcel import get_current_dcel
from app.services.python_executor import get_executor
from app.services.helper_functions import create_helper_functions


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


# =============================================================================
# REPL-BASED TOOLS (4 core tools)
# =============================================================================

@tool
def execute_python(code: str) -> dict:
    """
    Execute Python code to query and analyze facility data.
    
    AVAILABLE IN CODE:
    - dcel: DCEL object with all facility faces (dcel.faces is the list)
    - np, pd, math: NumPy, Pandas, math libraries
    - Helper functions: safe_filter_by_state(), safe_get_property(), get_stats()
    - Metadata: unique_states, unique_districts, total_facilities
    
    RULES:
    - Use print() to output results
    - Use helper functions for state/district lookups (handles fuzzy matching)
    - Handle missing data with safe_get_property(f, 'field', default)
    
    Args:
        code: Python code to execute (30s timeout)
    
    Returns:
        {success: bool, output: str} or {success: false, error: str, hint: str}
    
    Example:
        facilities = safe_filter_by_state('Maharashtra')
        print(f"Count: {len(facilities)}")
    """
    print(f"[TOOL DEBUG] execute_python called with code:\n{code[:200]}...")
    
    executor = get_executor()
    result = executor.execute(code)
    
    print(f"[TOOL DEBUG] execute_python result: {str(result)[:300]}...")
    return result


@tool
def get_available_values(field: str) -> dict:
    """
    Get all unique values for a field in the dataset.
    Use when you get 'not found' errors to see what values exist.
    
    Args:
        field: Property name like 'state', 'district', 'type'
    
    Returns:
        {field: str, values: list, count: int}
    
    Example: get_available_values('state') -> all state names
    """
    print(f"[TOOL DEBUG] get_available_values called for field: {field}")
    
    dcel = get_current_dcel()
    if not dcel:
        return {"error": "No DCEL available. Upload facility data first."}
    
    values = set()
    for face in dcel.faces:
        props = face.properties or {}
        
        # For state/district, try population_breakdown first
        if field in ['state', 'district']:
            breakdown = props.get('population_breakdown', [])
            for region in breakdown:
                val = region.get(field)
                if val:
                    values.add(val)
            # Also try direct property
            val = props.get(field)
            if val:
                values.add(val)
        else:
            val = props.get(field)
            if val:
                values.add(val)
    
    sorted_values = sorted(list(values))
    
    result = {
        "field": field,
        "count": len(sorted_values),
        "values": sorted_values[:50],  # Limit to 50 to avoid huge responses
        "truncated": len(sorted_values) > 50
    }
    
    print(f"[TOOL DEBUG] get_available_values found {len(sorted_values)} unique values")
    return result


@tool
def fuzzy_search(query: str, field: str = "state") -> dict:
    """
    Find closest matches for a query string.
    Use when user input might have typos or use alternate names (e.g., 'Bombay' for 'Mumbai').
    
    Args:
        query: Search term (e.g., 'Dilli', 'Bombay', 'Maharastra')
        field: Field to search in ('state', 'district', 'name')
    
    Returns:
        {query: str, matches: list[str], best_match: str}
    
    Example: fuzzy_search('Dilli', 'state') -> matches: ['Delhi']
    """
    print(f"[TOOL DEBUG] fuzzy_search called for '{query}' in field '{field}'")
    
    dcel = get_current_dcel()
    if not dcel:
        return {"error": "No DCEL available. Upload facility data first."}
    
    # Get all unique values for the field
    all_values = set()
    for face in dcel.faces:
        if field == 'name':
            val = face.facility_name
            if val:
                all_values.add(val)
        elif field in ['state', 'district']:
            # Try population_breakdown first
            props = face.properties or {}
            breakdown = props.get('population_breakdown', [])
            for region in breakdown:
                val = region.get(field)
                if val:
                    all_values.add(val)
            # Also try direct property
            val = props.get(field)
            if val:
                all_values.add(val)
        else:
            props = face.properties or {}
            val = props.get(field)
            if val:
                all_values.add(val)
    
    unique_values = list(all_values)
    
    # Find close matches
    matches = get_close_matches(query, unique_values, n=5, cutoff=0.3)
    
    result = {
        "query": query,
        "field": field,
        "matches": matches,
        "best_match": matches[0] if matches else None,
        "confidence": "high" if matches and matches[0].lower() == query.lower() else "medium" if matches else "none"
    }
    
    print(f"[TOOL DEBUG] fuzzy_search found matches: {matches}")
    return result


@tool
def inspect_sample(state: str = None, limit: int = 3) -> dict:
    """
    Get sample facilities to understand data structure.
    Use when debugging to see what properties are available.
    
    Args:
        state: Optional state filter (e.g., 'Delhi')
        limit: Number of samples to return (default 3, max 10)
    
    Returns:
        {total: int, samples: list[dict with facility properties]}
    """
    print(f"[TOOL DEBUG] inspect_sample called with state={state}, limit={limit}")
    
    dcel = get_current_dcel()
    if not dcel:
        return {"error": "No DCEL available. Upload facility data first."}
    
    facilities = dcel.faces
    
    # Filter by state if provided
    if state:
        state_lower = state.lower()
        facilities = [
            f for f in facilities
            if (f.properties or {}).get('state', '').lower() == state_lower
        ]
        
        # Try fuzzy match if exact match returns nothing
        if not facilities:
            all_states = set(
                (f.properties or {}).get('state', '') 
                for f in dcel.faces
            )
            matches = get_close_matches(state, list(all_states), n=1, cutoff=0.6)
            if matches:
                matched_state = matches[0]
                facilities = [
                    f for f in dcel.faces
                    if (f.properties or {}).get('state', '') == matched_state
                ]
    
    limit = min(limit, 10)  # Cap at 10
    samples = facilities[:limit]
    
    result = {
        "total_matching": len(facilities),
        "samples": [
            {
                "facility_id": f.facility_id,
                "facility_name": f.facility_name,
                "properties": {
                    k: v for k, v in (f.properties or {}).items()
                    if isinstance(v, (str, int, float)) and len(str(v)) < 100
                }
            }
            for f in samples
        ]
    }
    
    print(f"[TOOL DEBUG] inspect_sample returning {len(samples)} samples from {len(facilities)} matching")
    return result


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

def get_system_prompt() -> str:
    """Generate system prompt with dynamic data."""
    dcel = get_current_dcel()
    
    if dcel:
        helpers = create_helper_functions(dcel)
        unique_states = helpers['unique_states'][:15]
        total_facilities = helpers['total_facilities']
    else:
        unique_states = []
        total_facilities = 0
    
    # Build prompt without any curly braces in code examples to avoid template issues
    prompt = """You are Tessera's spatial analytics assistant helping policymakers optimize facility placement across India.

## YOUR ROLE
Analyze facility coverage data to answer questions about:
- Facility distribution and coverage gaps
- Population served by facilities
- Optimal locations for new facilities
- State/district-level statistics and comparisons

## CAPABILITIES
You can execute Python code against a DCEL containing """ + str(total_facilities) + """ facility Voronoi cells.

## DATA STRUCTURE
Each facility in dcel.faces has:
- facility_id, facility_name: Identifiers
- properties: Dict with state, district, population, area_sq_km, centroid_lat, centroid_lng

## AVAILABLE IN CODE
- dcel: DCEL object with all facility faces
- dcel.faces: List of Face objects  
- Available states: """ + str(unique_states) + """
- safe_filter_by_state(name): Fuzzy-match filter by state
- safe_get_property(f, prop, default): Null-safe property access
- get_stats(facilities): Returns dict with count, total_population, avg_population
- Libraries: np (numpy), pd (pandas), math

## QUERY PATTERNS

Count facilities:
  facilities = safe_filter_by_state('Maharashtra')
  count = len(facilities)
  print("Facilities in Maharashtra: " + str(count))

Calculate average population:
  facilities = safe_filter_by_state('Delhi')
  pops = [safe_get_property(f, 'population', 0) for f in facilities]
  pops = [p for p in pops if p > 0]
  avg = sum(pops) / len(pops) if pops else 0
  print("Average population: " + str(int(avg)))

Find coverage gaps:
  sorted_by_area = sorted(dcel.faces, key=lambda f: safe_get_property(f, 'area_sq_km', 0), reverse=True)
  for f in sorted_by_area[:5]:
      name = f.facility_name
      area = safe_get_property(f, 'area_sq_km', 0)
      print(name + ": " + str(int(area)) + " km2")

## IMPORTANT
- NEVER use f-strings or curly braces in print statements
- Always use string concatenation: "text " + str(variable)
- Use safe_get_property for all property access
- Use print() to show results

## ERROR HANDLING
If code fails, use get_available_values() or fuzzy_search() to debug, then retry.
You have up to 3 attempts!
"""
    return prompt


# =============================================================================
# AGENT CREATION AND PROCESSING
# =============================================================================

def create_chat_agent(api_key: str, provider: str = "openai") -> AgentExecutor:
    """
    Create a LangChain agent with Python REPL tools.
    
    Args:
        api_key: API key for the chosen provider
        provider: AI provider ('openai' or 'gemini')
    
    Returns:
        AgentExecutor configured with the appropriate LLM
    """
    # Create LLM based on provider
    if provider.lower() == "gemini":
        llm = ChatGoogleGenerativeAI(
            model="gemini-3-flash-preview",
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
        execute_python,
        get_available_values,
        fuzzy_search,
        inspect_sample
    ]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", get_system_prompt()),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad")
    ])
    
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(
        agent=agent, 
        tools=tools, 
        verbose=True,
        max_iterations=10,
        handle_parsing_errors=True
    )


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
        # Create LLM based on provider
        if provider.lower() == "gemini":
            llm = ChatGoogleGenerativeAI(
                model="gemini-3-flash-preview",
                google_api_key=api_key,
                temperature=0,
                timeout=120.0
            )
        else:  # default to openai
            llm = ChatOpenAI(
                model="gpt-4",
                api_key=api_key,
                temperature=0,
                timeout=120.0
            )
        
        tools = [
            execute_python,
            get_available_values,
            fuzzy_search,
            inspect_sample
        ]
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", get_system_prompt()),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
        
        agent = create_tool_calling_agent(llm, tools, prompt)
        agent_executor = AgentExecutor(
            agent=agent, 
            tools=tools, 
            verbose=True,
            max_iterations=10,
            handle_parsing_errors=True
        )

        print(f"[CHAT DEBUG] Processing message: {message[:100]}...")
        print(f"[CHAT DEBUG] Provider: {provider}")
        
        result = agent_executor.invoke({
            "input": message,
            "chat_history": convert_history_to_messages(history)
        })
        
        response = result.get("output", "I couldn't process that request.")
        
        # Handle case where response is a list
        if isinstance(response, list):
            text_parts = []
            for item in response:
                if isinstance(item, dict) and 'text' in item:
                    text_parts.append(item['text'])
                elif isinstance(item, str):
                    text_parts.append(item)
            response = "".join(text_parts)
            
        print(f"[CHAT DEBUG] Response received: {str(response)[:200]}...")
        
        # Add assistant response to history
        add_to_conversation(session_id, "assistant", response)
        
        return response
        
    except Exception as e:
        print(f"[CHAT DEBUG] ERROR: {str(e)}")
        error_msg = f"Error processing request: {str(e)}"
        add_to_conversation(session_id, "assistant", error_msg)
        return error_msg
