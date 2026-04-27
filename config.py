# config.py (Refactored Version)
import os
from dotenv import load_dotenv

# This will load variables from a .env file into the environment
# It's great for local development.
load_dotenv()

# --- Orchestrator Config ---
CHARS_PER_CHUNK = 1024 
MIN_CHUNK_LENGTH = 150
FUZZY_MATCH_THRESHOLD = 95

# --- External AI Service URLs ---
# NOTE: Using os.getenv to read from environment variables.
# This makes the app configurable without changing code.
# Provide a default value for local testing if the env var isn't set.

#The API for raw question generation
#EXTERNAL_HF_URL = os.getenv("EXTERNAL_HF_URL", "http://45.198.14.8:8502/generate-qa")

# The API for Ollama (for polishing questions)
EXTERNAL_OLLAMA_URL = os.getenv("EXTERNAL_OLLAMA_URL", "http://45.198.14.8:11434/api/generate")

# Robustly ensure we have a clean base URL and a full generation URL
if EXTERNAL_OLLAMA_URL.endswith("/api/generate"):
    OLLAMA_BASE_URL = EXTERNAL_OLLAMA_URL.replace("/api/generate", "").rstrip("/")
else:
    OLLAMA_BASE_URL = EXTERNAL_OLLAMA_URL.rstrip("/")

# The specific Ollama model to use
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:latest")

# --- Mode ---
# If True, the system will use dummy fallbacks 
OFFLINE_MODE = os.getenv("OFFLINE_MODE", "False").lower() == "true"
