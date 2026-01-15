
import os
import google.generativeai as genai
from typing import List, Dict, Any, Optional

class GeminiService:
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("Warning: GOOGLE_API_KEY not found in environment variables")
        else:
            genai.configure(api_key=api_key)
            # Use Gemini Flash Latest (stable free tier)
            self.model = genai.GenerativeModel('gemini-flash-latest')

    def get_chat_response(self, messages: List[Dict[str, str]], context: Optional[Dict[str, Any]] = None) -> str:
        """
        Get a response from Gemini based on chat history and optional context.
        """
        try:
            # Construct the prompt
            system_instruction = (
                "You are an AI assistant for the Voronoi Health Facility Locator application. "
                "Your goal is to help users understand the map, analyze facility coverage, and suggest improvements.\n\n"
            )

            if context:
                system_instruction += "Here is the current operational context of the map:\n"
                
                if 'facilities' in context:
                    facilities = context['facilities']
                    system_instruction += f"- Number of facilities: {len(facilities)}\n"
                    # Add more summary stats if needed, but avoid dumping massive JSON
                
                if 'largest_cell' in context and context['largest_cell']:
                    lc = context['largest_cell']
                    system_instruction += f"- Largest Voronoi cell: {lc.get('name', 'Unknown')} (Area: {lc.get('area_sq_km', 0):.2f} sq km)\n"
                
                if 'most_populated_cell' in context and context['most_populated_cell']:
                    mp = context['most_populated_cell']
                    system_instruction += f"- Most populated cell: {mp.get('name', 'Unknown')} (Population: {mp.get('population', 0):,.0f}, Density: {mp.get('density', 0):.0f}/km²)\n"

                if 'selected_facility' in context and context['selected_facility']:
                    sf = context['selected_facility']
                    system_instruction += f"- User selected facility: {sf.get('name', 'Unknown')}\n"
                
                system_instruction += "\nUse this information to answer the user's questions accurately.\n"

            # Reformat messages for Gemini (it expects 'role' and 'parts')
            # History needs to be a list of Content objects or similar structure
            # For simplicity in this `generate_content` call, we can append history to the prompt 
            # or use start_chat if we want to maintain session properly.
            # Here we'll construct a single prompt string for a stateless request or use the chat object.
            
            if not self.model:
                 return "Error: AI Service not initialized (API Key missing)."

            # Simple approach: Construct a full prompt string
            full_prompt = system_instruction + "\n\nChat History:\n"
            print(f"DEBUG SYSTEM PROMPT:\n{system_instruction}") # Debug print
            for msg in messages:
                role = "User" if msg.get('role') == 'user' else "Assistant"
                content = msg.get('content', '')
                full_prompt += f"{role}: {content}\n"
            
            full_prompt += "Assistant: "

            response = self.model.generate_content(full_prompt)
            return response.text
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error calling Gemini: {e}")
            # Check for common errors
            err_str = str(e)
            if "429" in err_str:
                return "The AI service is currently busy (Rate Limit Exceeded). Please try again in a moment."
            if "404" in err_str:
                return "The AI model is currently unavailable. Please check the backend configuration."
            return f"I encountered an error connecting to the AI: {e}"
