"""
Copilot router - Natural language interface for map operations
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


router = APIRouter()


class CopilotQuery(BaseModel):
    """Request for copilot query"""
    query: str
    context: Optional[Dict[str, Any]] = None  # Current map state


class FunctionCall(BaseModel):
    """Parsed function call from AI"""
    name: str
    arguments: Dict[str, Any]


class CopilotResponse(BaseModel):
    """Response from copilot"""
    success: bool
    query: str
    response_text: Optional[str] = None
    function_call: Optional[FunctionCall] = None
    error: Optional[str] = None


class SummaryRequest(BaseModel):
    """Request to generate summary"""
    data: Dict[str, Any]


class SummaryResponse(BaseModel):
    """Generated summary"""
    success: bool
    summary: str
    error: Optional[str] = None


class QuestionRequest(BaseModel):
    """Request to answer a question"""
    question: str
    data: Dict[str, Any]


class QuestionResponse(BaseModel):
    """Answer to a question"""
    success: bool
    answer: str
    error: Optional[str] = None


@router.get("/status")
async def copilot_status():
    """Check if Azure OpenAI is configured for the copilot."""
    from app.services.copilot_service import copilot_service
    return {
        "configured": copilot_service.is_configured,
        "message": "Azure OpenAI is configured" if copilot_service.is_configured 
                   else "Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY in .env"
    }


@router.post("/query", response_model=CopilotResponse)
async def process_query(request: CopilotQuery):
    """
    Process a natural language query about the map.
    
    The copilot will parse the query and return either:
    - A function call (action to perform)
    - A text response (answer or clarification)
    
    Example queries:
    - "Compute Voronoi diagram for Karnataka and highlight the 3 worst-covered areas"
    - "What's the total population served by these facilities?"
    - "Navigate to the facility with the highest coverage"
    """
    from app.services.copilot_service import copilot_service
    
    if not copilot_service.is_configured:
        raise HTTPException(
            status_code=503,
            detail="Azure OpenAI is not configured. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY."
        )
    
    try:
        result = copilot_service.parse_query(request.query, request.context)
        
        return CopilotResponse(
            success=True,
            query=result["query"],
            response_text=result["response_text"],
            function_call=FunctionCall(**result["function_call"]) if result["function_call"] else None
        )
        
    except Exception as e:
        return CopilotResponse(
            success=False,
            query=request.query,
            error=str(e)
        )


@router.post("/summarize", response_model=SummaryResponse)
async def generate_summary(request: SummaryRequest):
    """
    Generate a natural language summary of analysis results.
    
    Pass in Voronoi/population analysis results and get a human-readable summary.
    """
    from app.services.copilot_service import copilot_service
    
    if not copilot_service.is_configured:
        raise HTTPException(
            status_code=503,
            detail="Azure OpenAI is not configured."
        )
    
    try:
        summary = copilot_service.generate_summary(request.data)
        return SummaryResponse(success=True, summary=summary)
    except Exception as e:
        return SummaryResponse(success=False, summary="", error=str(e))


@router.post("/answer", response_model=QuestionResponse)
async def answer_question(request: QuestionRequest):
    """
    Answer a question about the current map data.
    """
    from app.services.copilot_service import copilot_service
    
    if not copilot_service.is_configured:
        raise HTTPException(
            status_code=503,
            detail="Azure OpenAI is not configured."
        )
    
    try:
        answer = copilot_service.answer_question(request.question, request.data)
        return QuestionResponse(success=True, answer=answer)
    except Exception as e:
        return QuestionResponse(success=False, answer="", error=str(e))
