"""
Chat router - API endpoints for AI chatbot.
"""
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.chat_service import (
    process_chat_message,
    get_conversation_history,
    clear_conversation
)

router = APIRouter()


class ChatMessageRequest(BaseModel):
    """Request to send a chat message."""
    session_id: str
    message: str
    api_key: str  # User's AI provider API key
    provider: str = "openai"  # AI provider: 'openai' or 'gemini'


class ChatMessageResponse(BaseModel):
    """Response from chat endpoint."""
    response: str
    session_id: str
    timestamp: str
    data: Optional[dict] = None  # Optional structured data (e.g., facilities)
    tools_used: Optional[list] = []  # Backend functions used
    tool_calls: Optional[list] = []  # Detailed tool calls with inputs


class ConversationHistoryResponse(BaseModel):
    """Response with conversation history."""
    session_id: str
    messages: list
    count: int


@router.post("/message", response_model=ChatMessageResponse)
async def send_message(request: ChatMessageRequest):
    """
    Send a message to the AI assistant and get a response.
    
    The assistant can query spatial data about facilities and their
    service areas using the current Voronoi diagram.
    
    Supports OpenAI (GPT-4) and Google Gemini providers.
    """
    if not request.api_key:
        raise HTTPException(
            status_code=400,
            detail="API key is required"
        )
    
    if not request.message.strip():
        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty"
        )
    
    try:
        result = await process_chat_message(
            session_id=request.session_id,
            message=request.message,
            api_key=request.api_key,
            provider=request.provider
        )
        
        return ChatMessageResponse(
            response=result["response"],
            session_id=request.session_id,
            timestamp=datetime.now().isoformat(),
            data=result["data"],
            tools_used=result.get("tools_used", []),
            tool_calls=result.get("tool_calls", [])
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Chat processing error: {str(e)}"
        )


@router.get("/history/{session_id}", response_model=ConversationHistoryResponse)
async def get_history(session_id: str):
    """
    Get the conversation history for a session.
    """
    history = get_conversation_history(session_id)
    
    return ConversationHistoryResponse(
        session_id=session_id,
        messages=history,
        count=len(history)
    )


@router.delete("/clear/{session_id}")
async def clear_history(session_id: str):
    """
    Clear the conversation history for a session.
    """
    clear_conversation(session_id)
    
    return {
        "status": "cleared",
        "session_id": session_id
    }


@router.post("/new")
async def new_conversation():
    """
    Start a new conversation session.
    Returns a new session ID.
    """
    import uuid
    session_id = str(uuid.uuid4())
    
    return {
        "session_id": session_id,
        "created_at": datetime.now().isoformat()
    }
