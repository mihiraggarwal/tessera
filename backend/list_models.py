
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
# Also check parent dir
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("No API Key found")
else:
    genai.configure(api_key=api_key)
    print(f"Using Key: {api_key[:5]}...")
    try:
        print("Available models:")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(m.name)
    except Exception as e:
        print(f"Error: {e}")
