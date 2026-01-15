
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.services.gemini_service import GeminiService

router = APIRouter()
gemini_service = GeminiService()

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    context: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    response: str

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat with the AI assistant about the map and facilities.
    """
    if not request.messages:
        raise HTTPException(status_code=400, detail="Messages list cannot be empty")
    
    # Convert Pydantic models to dicts
    messages_dict = [{"role": m.role, "content": m.content} for m in request.messages]
    
    response_text = gemini_service.get_chat_response(messages_dict, request.context)
    
    return ChatResponse(response=response_text)
