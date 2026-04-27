# processing/ai_pipeline.py (Unified GPT-OSS Unified Pipeline)

import httpx
import json
import random
import asyncio
from typing import List, Optional, Dict
import time
import re

from langchain.text_splitter import RecursiveCharacterTextSplitter
from fuzzywuzzy import fuzz
from config import (OLLAMA_MODEL, CHARS_PER_CHUNK, MIN_CHUNK_LENGTH, OLLAMA_BASE_URL, OFFLINE_MODE)
from models import QuestionType, Question, DifficultyLevel

# --- The Advanced Unified Prompt ---

def get_unified_generation_prompt(context: str, q_type: QuestionType, difficulty: DifficultyLevel = DifficultyLevel.medium) -> str:
    """Enhanced prompt with difficulty level support for better reliability with various models."""
    type_str = "MULTIPLE CHOICE (MCQ)" if q_type == QuestionType.mcq else "TRUE/FALSE"
    options_str = """{
    "A": "True",
    "B": "False"
  }""" if q_type == QuestionType.true_false else """{
    "A": "Option 1",
    "B": "Option 2",
    "C": "Option 3",
    "D": "Option 4"
  }"""
    
    # Difficulty-specific instructions
    difficulty_instructions = {
        DifficultyLevel.easy: """**EASY LEVEL**: 
- Focus on basic definitions, fundamental concepts, and straightforward facts.
- Questions should test recall and basic understanding.
- Avoid complex reasoning or multi-step logic.
- Use clear, simple language.""",
        DifficultyLevel.medium: """**MEDIUM LEVEL**: 
- Focus on application of concepts and understanding relationships.
- Questions should require some analysis or connection between ideas.
- May involve comparing, contrasting, or explaining concepts.
- Use professional, clear language.""",
        DifficultyLevel.hard: """**HARD LEVEL**: 
- Focus on complex analysis, synthesis, and evaluation.
- Questions should require critical thinking, inference, or multi-step reasoning.
- May involve edge cases, subtle distinctions, or advanced applications.
- Use precise, technical language where appropriate."""
    }
    
    prompt = f"""### INSTRUCTIONS:
1. Generate exactly ONE {type_str} question from the CONTEXT provided.
2. **Difficulty Level**: {difficulty.value.upper()}
{difficulty_instructions[difficulty]}
3. **Professional Style**: The question must look like it's from an official EXAM or INTERVIEW.
4. **Standalone Human Question**: Ask the question exactly as a human interviewer would.
5. **NO SOURCE REFERENCES**: Strictly FORBIDDEN to use phrases like "According to the PDF", "Based on the information", etc.
6. **Direct Inquiry**: The question must be a direct inquiry about the subject matter itself.
7. Provide the output in strictly RAW JSON format.

### CONTEXT:
{context}

### REQUIRED JSON STRUCTURE:
{{
  "question_text": "Direct subject-matter question here?",
  "question_type": "{q_type.value}",
  "options": {options_str},
  "correct_answer": "A"
}}
(Note: For True/False questions, "correct_answer" should be true or false (boolean), not "A")

NO PREAMBLE. NO EXPLANATION. ONLY RAW JSON."""
    return prompt

# --- Pipeline Operations ---

async def generate_structured_question(client: httpx.AsyncClient, context: str, q_type: QuestionType, difficulty: DifficultyLevel = DifficultyLevel.medium) -> Optional[dict]:
    """Uses GPT-OSS via Ollama to generate a structured question with specified difficulty."""
    if OFFLINE_MODE:
        return None

    prompt = get_unified_generation_prompt(context, q_type, difficulty)
    
    # Construct the full URL robustly
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.4,
            "num_predict": 1024,
            "num_ctx": 16384
        }
    }

    try:
        response = await client.post(url, json=payload, timeout=240.0)
        
        if response.status_code != 200:
            return None
            
        raw_text = response.text
        if not raw_text:
            return None
            
        try:
            full_result = response.json()
            raw_json = full_result.get("response", "").strip()
            
            if not raw_json:
                return None
            
            # Robust JSON extraction using regex (matches the outermost { })
            json_match = re.search(r'(\{.*\})', raw_json, re.DOTALL)
            if json_match:
                extracted_json = json_match.group(1)
                data = json.loads(extracted_json)
            else:
                data = json.loads(raw_json)
            
            # NORMALIZATION: Ensure fields match the Question model
            if "question" in data and "question_text" not in data:
                data["question_text"] = data.pop("question")
            
            if "answer" in data and "correct_answer" not in data:
                data["correct_answer"] = data.pop("answer")
            
            # Force the requested question type
            data["question_type"] = q_type.value
                
            return data
                
        except (json.JSONDecodeError, KeyError):
            return None
    except Exception as e:
        print(f"Error in Unified Generation: {e}")
        return None

async def process_single_chunk(client: httpx.AsyncClient, chunk: str, q_type: QuestionType, difficulty: DifficultyLevel = DifficultyLevel.medium) -> Optional[dict]:
    """Processes a chunk using the unified model with specified difficulty and ensures data integrity."""
    data = await generate_structured_question(client, chunk, q_type, difficulty)
    
    if not data or not isinstance(data, dict):
        return None
    
    # Ensure correct types for Pydantic
    if q_type == QuestionType.true_false:
        # Normalize boolean correct_answer
        ans = data.get("correct_answer")
        if isinstance(ans, str):
            data["correct_answer"] = ans.lower() == "true"
        elif not isinstance(ans, bool):
            data["correct_answer"] = True # Default fallback
            
    return data

async def generate_questions_from_text(
    cleaned_text: str,
    num_questions: Optional[int] = None,
    question_type: Optional[QuestionType] = None,
    difficulty: Optional[DifficultyLevel] = None
) -> List[Question]:
    
    if not cleaned_text.strip(): return []

    # Chunking
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=150, separators=["\n\n", "\n", ". ", " "])
    all_chunks = text_splitter.split_text(cleaned_text)
    
    # Deduplication
    unique_chunks = []
    for chunk in all_chunks:
        chunk = chunk.strip()
        if len(chunk) < MIN_CHUNK_LENGTH: continue
        is_duplicate = False
        for existing in unique_chunks:
            if fuzz.ratio(chunk, existing) > 80:
                is_duplicate = True
                break
        if not is_duplicate:
            unique_chunks.append(chunk)
    
    chunks = unique_chunks
    if not chunks: return []

    # Handle num_questions=0 or None as default
    if num_questions is None or num_questions <= 0:
        num_to_generate = min(len(chunks) * 2, 20)
    else:
        num_to_generate = num_questions

    # Question Type Distribution
    if question_type:
        type_assignments = [question_type] * num_to_generate
    else:
        num_mcq = int(round(num_to_generate * 0.5))
        num_tf = num_to_generate - num_mcq
        type_assignments = [QuestionType.mcq] * num_mcq + [QuestionType.true_false] * num_tf
        random.shuffle(type_assignments)
    
    # Difficulty Distribution
    if difficulty is None:
        # Random mix of all difficulty levels
        difficulty_assignments = [
            DifficultyLevel.easy,
            DifficultyLevel.medium,
            DifficultyLevel.hard
        ] * (num_to_generate // 3 + 1)
        difficulty_assignments = difficulty_assignments[:num_to_generate]
        random.shuffle(difficulty_assignments)
    else:
        # All questions with the same specified difficulty
        difficulty_assignments = [difficulty] * num_to_generate
    
    results = []
    async with httpx.AsyncClient() as client:
        # Display message based on difficulty mode
        if difficulty is None:
            print(f"AI is generating {num_to_generate} questions with MIXED difficulty levels. This may take a few moments...")
        else:
            difficulty_str = difficulty.upper() if isinstance(difficulty, str) else difficulty.value.upper()
            print(f"AI is generating {num_to_generate} questions at {difficulty_str} difficulty. This may take a few moments...")
        
        for i in range(num_to_generate):
            chunk = chunks[i % len(chunks)]
            q_type = type_assignments[i]
            q_difficulty = difficulty_assignments[i]
            
            for attempt in range(3):
                res = await process_single_chunk(client, chunk, q_type, q_difficulty)
                if res:
                    results.append(res)
                    break
                await asyncio.sleep(1 * (attempt + 1))
            
            print(f"  -> Progress: {i+1}/{num_to_generate} [Collected: {len(results)}]", end="\r")
    
    final_questions = []
    for r in results:
        try:
            if r.get("question_type") == "mcq" and not isinstance(r.get("options"), dict):
                continue
            final_questions.append(Question(**r))
        except Exception:
            continue
            
    random.shuffle(final_questions)
    return final_questions