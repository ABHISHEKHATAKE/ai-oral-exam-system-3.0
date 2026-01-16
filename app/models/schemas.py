from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str

class SignUp(BaseModel):
    username: EmailStr
    password: str
    role: str  # "instructor" or "student"


class StudentProfile(BaseModel):
    student_id: str
    name: str
    email: Optional[EmailStr] = None  # Made optional since it's set from JWT token
    project_title: str
    project_description: str
    technologies: List[str]
    metrics: List[str]
    case_study: str

class ExamSchedule(BaseModel):
    student_id: str
    start_time: str  # Format: "YYYY-MM-DD HH:MM AM/PM"
    duration_minutes: int

class ExamRequest(BaseModel):
    student_id: str

class ExamResponse(BaseModel):
    exam_id: str
    student_id: str
    student_name: str
    status: str
    created_at: str
    first_question: Optional[str] = None

class GradingResult(BaseModel):
    student_id: str
    total_score: float
    scores: Dict[str, float]
    strengths: List[str]
    weaknesses: List[str]
    feedback: str
    risk_level: str
    suspicion_score: float
    cheat_flags: List[str]

class Question(BaseModel):
    id: str
    type: str  # "text" or "mcq"
    question: str
    options: Optional[List[str]] = None  # Only for MCQ questions
    correct_answer: Optional[str] = None  # Only for MCQ questions (index or text)

class ExamData(BaseModel):
    exam_id: str
    student_id: str
    questions: List[Question]
    current_question_index: int
    answers: Dict[str, str]  # question_id -> answer
    start_time: datetime
    status: str  # "active", "completed", "timeout"

class StudentDetailResponse(BaseModel):
    student_id: str
    name: str
    email: str
    project_details: Dict
    case_study: str

class DashboardResponse(BaseModel):
    name: str
    upcoming_exams: List[Dict]
    past_results: List[Dict]
    profile_complete: bool

class PDFUploadResponse(BaseModel):
    message: str
    questions: List[str]
    pdf_name: str
    instruction: str
    exam_name: Optional[str] = None


class ChangeStudentIDRequest(BaseModel):
    new_student_id: str
    current_password: str
