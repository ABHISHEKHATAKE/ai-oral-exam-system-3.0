from typing import List, Dict, Optional, Any
import os, re
from dotenv import load_dotenv
from groq import Groq


# Load .env locally (Render ignores this and uses its own env vars)
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


class GrokExamService:
    def __init__(self):
        # If GROQ_API_KEY is missing, operate in degraded mode with fallbacks.
        self.conversations = {}
        if not GROQ_API_KEY:
            print("⚠️ [GROK] GROQ_API_KEY is missing. Operating in fallback mode (no external LLM calls).")
            self.client = None
            self.model = None
            return

        try:
            self.client = Groq(api_key=GROQ_API_KEY, proxies=None)
            self.model = "llama-3.1-8b-instant"
            masked = GROQ_API_KEY[:4] + "..." + GROQ_API_KEY[-4:]
            print(f"✅ GROQ API Loaded: {masked}")
        except Exception as e:
            print(f"⚠️ [GROK] Failed to initialize Groq client: {e}. Falling back to local mode.")
            self.client = None
            self.model = None

    # -------- PDF QUESTION GENERATION --------
    def generate_pdf_questions(self, pdf_content: str, instruction: str) -> List[str]:
        relevant_text = pdf_content[:6000]

        prompt = f"""
You are a professor conducting an oral exam.

Instruction: {instruction}

Content:
{relevant_text}

Generate 5 deep viva questions.
Format:
Q1. ...
Q2. ...
Q3. ...
Q4. ...
Q5. ...
"""

        # If client is not available, return simple fallback questions
        if not self.client:
            return [
                "Q1. Summarize the main points from the provided material.",
                "Q2. Explain one key concept and its applications.",
                "Q3. Describe a challenge mentioned and how to address it.",
                "Q4. Describe how the material relates to your project.",
                "Q5. What future work or improvements would you suggest?"
            ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=400
        )

        questions = [
            q.strip() for q in response.choices[0].message.content.split("\n")
            if q.strip().startswith("Q")
        ]

        return questions or ["Q1. Explain the main concepts from the given material."]

    # -------- PROJECT QUESTION GENERATION --------
    def generate_project_questions(self, project_details: Dict) -> List[str]:
        title = project_details.get("title", "Project")
        description = project_details.get("description", "")
        technologies = project_details.get("technologies", [])

        prompt = f"""
You are a professor conducting an oral exam.

Project: {title}
Description: {description}
Technologies: {', '.join(technologies)}

Generate 8 technical viva questions.
Return one per line.
"""

        if not self.client:
            # Simple heuristics based on project details
            title = project_details.get("title", "Project")
            techs = ', '.join(project_details.get('technologies', []))
            return [
                f"Explain the primary goal of {title}.",
                f"Describe the key technologies used: {techs}.",
                "Walk through the main components and their interactions.",
                "Explain a difficult bug you encountered and how you fixed it.",
                "How would you scale this project for more users?",
                "Discuss security considerations for this project.",
                "What tests did you write and why?",
                "What improvements would you prioritize next?"
            ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800
        )

        return [q.strip() for q in response.choices[0].message.content.split("\n") if q.strip()][:8]

    # -------- MAIN EXAM GENERATION --------
    def generate_exam_questions(
        self,
        exam_id: str,
        project_details: Dict = None,
        pdf_content: str = None,
        num_questions: int = 8
    ) -> List[Dict]:

        if pdf_content:
            instruction = project_details.get("title", "PDF Exam") if project_details else "PDF Exam"
            raw_questions = self.generate_pdf_questions(pdf_content, instruction)
        elif project_details:
            raw_questions = self.generate_project_questions(project_details)
        else:
            raise ValueError("No PDF or project details provided")

        questions = []
        for i, q in enumerate(raw_questions[:num_questions]):
            questions.append({
                "id": f"q{i+1}",
                "type": "text",
                "question": q,
                "options": None,
                "correct_answer": None
            })

        return questions

    # -------- ANSWER EVALUATION --------
    def evaluate_answer(self, question: str, student_answer: str) -> Dict[str, Any]:
        if not student_answer.strip():
            return {
                "score": 0.0,
                "max_score": 1.0,
                "feedback": "No answer provided.",
                "evaluation": "Empty response"
            }
        # If no external LLM available, use a simple heuristic: score based on answer length
        if not self.client:
            length = len(student_answer.strip())
            score = 1.0 if length > 50 else (0.5 if length > 10 else 0.0)
            feedback = "Good answer." if score >= 1.0 else ("Partial answer." if score > 0 else "No meaningful answer.")
            return {
                "score": float(score),
                "max_score": 1.0,
                "feedback": feedback,
                "evaluation": "Fallback evaluation used"
            }

        prompt = f"""
Evaluate the student's answer from 0.0 to 1.0.

Question: {question}
Answer: {student_answer}

Format:
SCORE: x.x
FEEDBACK: ...
EVALUATION: ...
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=300
        )

        text = response.choices[0].message.content
        score, feedback, evaluation = 0.5, "", ""

        for line in text.split("\n"):
            if line.startswith("SCORE:"):
                try:
                    score = float(line.replace("SCORE:", "").strip())
                except Exception:
                    pass
            elif line.startswith("FEEDBACK:"):
                feedback = line.replace("FEEDBACK:", "").strip()
            elif line.startswith("EVALUATION:"):
                evaluation = line.replace("EVALUATION:", "").strip()

        return {
            "score": min(1.0, max(0.0, score)),
            "max_score": 1.0,
            "feedback": feedback,
            "evaluation": evaluation
        }


# Global singleton
grok_exam_service = GrokExamService()

# Minimal TTS and transcription fallbacks to support voice flows when Groq client is unavailable
def _fallback_text_to_speech(text: str) -> dict:
    # Return a dummy base64 audio placeholder (empty) and status
    return {"status": "success", "audio": ""}

def _fallback_transcribe_audio_base64(audio_b64: str) -> dict:
    # Can't transcribe without external service; return empty transcription
    return {"status": "error", "message": "Transcription not available in fallback", "text": ""}

# Attach methods to instance for compatibility
if not grok_exam_service.client:
    setattr(grok_exam_service, 'text_to_speech', lambda text: _fallback_text_to_speech(text))
    setattr(grok_exam_service, 'transcribe_audio_base64', lambda audio: _fallback_transcribe_audio_base64(audio))
    # process_voice_answer should create a simple progression through questions
    def _fallback_process_voice_answer(student_id, transcribed_text, silence_duration, **kwargs):
        # Very simple: advance one question and return next_question placeholder
        return {"exam_complete": False, "next_question": "Thank you. Next question: Tell me more about your project.", "question_number": 2}
    setattr(grok_exam_service, 'process_voice_answer', _fallback_process_voice_answer)
