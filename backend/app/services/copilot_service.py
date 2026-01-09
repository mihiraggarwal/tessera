"""
Map Copilot Service - Natural language interface for map operations using Azure OpenAI
"""
import os
import json
from typing import Optional, Dict, Any, List
from openai import AzureOpenAI


# Function definitions for Azure OpenAI function calling
COPILOT_FUNCTIONS = [
    {
        "name": "compute_voronoi",
        "description": "Compute Voronoi service areas for facilities and analyze population coverage",
        "parameters": {
            "type": "object",
            "properties": {
                "state_filter": {
                    "type": "string",
                    "description": "Filter to a specific state (e.g., 'Karnataka', 'Tamil Nadu'). If null, uses all of India."
                },
                "highlight_metric": {
                    "type": "string",
                    "enum": ["highest_population", "lowest_population", "highest_density", "lowest_density"],
                    "description": "Which metric to use for highlighting cells"
                },
                "highlight_count": {
                    "type": "integer",
                    "description": "Number of cells to highlight (default 3)"
                },
                "include_summary": {
                    "type": "boolean",
                    "description": "Whether to generate a text summary of the results"
                }
            },
            "required": []
        }
    },
    {
        "name": "analyze_coverage",
        "description": "Analyze population coverage gaps and identify underserved areas",
        "parameters": {
            "type": "object",
            "properties": {
                "population_threshold": {
                    "type": "integer",
                    "description": "Population threshold to consider an area underserved (e.g., >500000)"
                },
                "area_threshold": {
                    "type": "number",
                    "description": "Area threshold in sq km to consider an area underserved"
                }
            },
            "required": []
        }
    },
    {
        "name": "navigate_to_location",
        "description": "Navigate the map to a specific location or facility",
        "parameters": {
            "type": "object",
            "properties": {
                "location_name": {
                    "type": "string",
                    "description": "Name of the location, facility, or region to navigate to"
                },
                "zoom_level": {
                    "type": "integer",
                    "description": "Zoom level (1-18, higher = more zoomed in)"
                }
            },
            "required": ["location_name"]
        }
    }
]


class CopilotService:
    """Service for processing natural language map queries using Azure OpenAI."""
    
    def __init__(self):
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.key = os.getenv("AZURE_OPENAI_KEY")
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
        self._client: Optional[AzureOpenAI] = None
    
    @property
    def is_configured(self) -> bool:
        """Check if Azure OpenAI credentials are configured."""
        return bool(self.endpoint and self.key)
    
    @property
    def client(self) -> AzureOpenAI:
        """Lazily create the Azure OpenAI client."""
        if not self._client:
            if not self.is_configured:
                raise ValueError("Azure OpenAI is not configured. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY.")
            self._client = AzureOpenAI(
                azure_endpoint=self.endpoint,
                api_key=self.key,
                api_version="2024-02-15-preview"
            )
        return self._client
    
    def parse_query(self, user_query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Parse a natural language query into structured actions.
        
        Args:
            user_query: The user's natural language question/command
            context: Optional context about current map state (facilities loaded, etc.)
            
        Returns:
            Dictionary with parsed intent and parameters
        """
        system_prompt = """You are a helpful map analysis assistant for a Voronoi population mapping application.
The application computes Voronoi diagrams (service areas) for healthcare facilities and calculates population coverage.

Your job is to understand user requests and call the appropriate functions.

Current context:
- The user can load facility data (hospitals, health centers)
- The system computes Voronoi cells showing each facility's service area
- Population data is overlaid to show how many people each facility serves
- Users can filter by state and analyze coverage gaps

Be helpful and precise. If the user's request is unclear, ask for clarification."""

        if context:
            system_prompt += f"\n\nCurrent state: {json.dumps(context)}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ]
        
        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=messages,
            functions=COPILOT_FUNCTIONS,
            function_call="auto",
            max_tokens=500
        )
        
        message = response.choices[0].message
        
        result = {
            "query": user_query,
            "has_function_call": message.function_call is not None,
            "response_text": message.content,
            "function_call": None
        }
        
        if message.function_call:
            result["function_call"] = {
                "name": message.function_call.name,
                "arguments": json.loads(message.function_call.arguments)
            }
        
        return result
    
    def generate_summary(self, analysis_results: Dict[str, Any]) -> str:
        """
        Generate a natural language summary of analysis results.
        
        Args:
            analysis_results: Dictionary containing Voronoi/population analysis results
            
        Returns:
            Human-readable summary
        """
        prompt = f"""Based on the following analysis results, write a brief, clear summary for the user:

Results:
{json.dumps(analysis_results, indent=2)}

Write 2-3 sentences highlighting the key insights. Be specific with numbers."""

        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": "You are a data analyst summarizing geographic analysis results."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200
        )
        
        return response.choices[0].message.content
    
    def answer_question(self, question: str, data: Dict[str, Any]) -> str:
        """
        Answer a question about the current map data.
        
        Args:
            question: User's question
            data: Current map/analysis data to reason about
            
        Returns:
            Natural language answer
        """
        prompt = f"""Based on the following map data, answer the user's question:

Data:
{json.dumps(data, indent=2)}

Question: {question}

Provide a clear, accurate answer based only on the data provided."""

        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": "You are a helpful assistant answering questions about geographic and population data."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300
        )
        
        return response.choices[0].message.content


# Singleton instance
copilot_service = CopilotService()
