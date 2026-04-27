# models.py

from pydantic import BaseModel, Field
from typing import List, Union, Dict, Optional
from enum import Enum

# --- Enums and Base Types ---

class QuestionType(str, Enum):
    mcq = "mcq"
    true_false = "true_false"
    multi_select = "multi_select"

class DifficultyLevel(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"

class QuestionStatus(str, Enum):
    new = "new"
    existing = "existing"

# --- Shared Models ---

class Question(BaseModel):
    """
    The primary Question model.
    """
    question_text: str
    question_type: QuestionType
    options: Dict[str, str]
    correct_answer: Union[str, bool, List[str]]
    status: Optional[QuestionStatus] = None

class QuestionResponse(BaseModel):
    """The response model containing a list of Question objects."""
    questions: List[Question]

class Section(BaseModel):
    header: str
    subsections: List[str]

class SectionResponse(BaseModel):
    sections: List[Section]

class SectionSelection(BaseModel):
    selected_sections: List[str]

class StringQuestion(BaseModel):
    """
    A model where values are strings for specific output formats.
    """
    question_text: str
    question_type: str
    options: str
    correct_answer: str
    status: Optional[str] = None

class StringQuestionResponse(BaseModel):
    """The response model containing a list of StringQuestion objects."""
    questions: List[StringQuestion]

# --- Base Models ---

class Base64File(BaseModel):
    """A file encoded in Base64."""
    filename: str = Field(..., description="The original filename")
    file_data: str = Field(..., description="The Base64 encoded string")
    

# --- Request Models for Endpoints ---

class SingleFileRequest(BaseModel):
    """
    Request model for single file with difficulty level.
    """
    filename: str = Field(..., description="The original filename")
    file_data: str = Field(..., description="The Base64 encoded string")
    difficulty: Optional[DifficultyLevel] = None 

class DiffRequest(BaseModel):
    """Request model for the diff endpoint."""
    old_file: Base64File
    new_file: Base64File
    difficulty: Optional[DifficultyLevel] = None

class UpdateQuestionnaireRequest(BaseModel):
    """Request model for the update endpoint."""
    old_file: Base64File
    new_file: Base64File
    existing_questions: dict 
    difficulty: Optional[DifficultyLevel] = None