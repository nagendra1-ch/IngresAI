import os
import sys

# Add parent directory to path to import app config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import google.generativeai as genai
from app.config import settings

if not settings.GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY is not configured in .env file.")
    sys.exit(1)

genai.configure(api_key=settings.GEMINI_API_KEY)

try:
    print("Listing available models:")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"Name: {m.name}, Display: {m.display_name}")
except Exception as e:
    print("Error listing models:", e)
