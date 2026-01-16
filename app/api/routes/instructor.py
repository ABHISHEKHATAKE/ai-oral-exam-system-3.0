from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import List
from app.models.schemas import (
    ExamSchedule, 
    StudentDetailResponse, 
    GradingResult,
    PDFUploadResponse
)
from app.api.dependencies import require_role
from app.services.exam_service import exam_service
from app.services.mongo_service import mongo_service
from app.services.grok_service import grok_exam_service
from datetime import datetime
from app.core.security import IST
import os
import uuid

router = APIRouter(prefix="/api/instructor", tags=["Instructor"])
@router.get("/results")
def get_all_results(user: dict = Depends(require_role("instructor"))):
    """Get all exam results for all students"""
    all_results = []
    
    # First, from in-memory active_exams
    for exam_id, exam_data in exam_service.active_exams.items():
        if exam_data['status'] == 'completed':
            student_id = exam_data['student_id']
            student_name = exam_service.students.get(student_id, {}).get('name', 'Unknown')
            
            # Use actual AI evaluation results
            total_score = exam_data.get('total_score', 0)
            max_score = exam_data.get('max_score', len(exam_data.get('questions', [])))
            percentage = exam_data.get('percentage', 0)
            total_questions = len(exam_data.get('questions', []))
            
            # Calculate average cheat score
            responses = exam_data.get('responses', [])
            avg_cheat_score = sum(r.get('cheat_score', 0) for r in responses) / len(responses) if responses else 0
            
            all_results.append({
                "exam_id": exam_id,
                "student_id": student_id,
                "student_name": student_name,
                "completed_at": exam_data.get('completed_at', datetime.now(IST)).isoformat() if hasattr(exam_data.get('completed_at'), 'isoformat') else str(exam_data.get('completed_at')),
                "total_score": total_score,
                "max_score": max_score,
                "percentage": percentage,
                "risk_level": exam_data.get('risk_level', 'LOW'),
                "suspicion_score": avg_cheat_score,
                "total_questions": total_questions
            })
    
    # Also load from MongoDB if available
    try:
        if mongo_service.is_connected():
            # Get all completed exams from MongoDB
            all_completed = mongo_service.get_all_completed_exams()
            for exam in all_completed:
                # Avoid duplicates
                if not any(r['exam_id'] == exam['exam_id'] for r in all_results):
                    student_id = exam['student_id']
                    student_name = exam_service.students.get(student_id, {}).get('name', 'Unknown')
                    
                    # Use stored scores from MongoDB
                    total_score = exam.get('total_score', 0)
                    max_score = exam.get('max_score', len(exam.get('question_scores', [])))
                    percentage = exam.get('percentage', 0)
                    total_questions = len(exam.get('question_scores', []))
                    
                    # Calculate average cheat score from responses
                    responses = exam.get('responses', [])
                    avg_cheat_score = sum(r.get('cheat_score', 0) for r in responses) / len(responses) if responses else 0
                    
                    all_results.append({
                        "exam_id": exam['exam_id'],
                        "student_id": student_id,
                        "student_name": student_name,
                        "completed_at": exam.get('completed_at', ''),
                        "total_score": total_score,
                        "max_score": max_score,
                        "percentage": percentage,
                        "risk_level": exam.get('risk_level', 'LOW'),
                        "suspicion_score": avg_cheat_score,
                        "total_questions": total_questions
                    })
    except Exception as e:
        print(f"Warning: Could not load completed exams from MongoDB: {e}")
    
    # Sort by completed_at (most recent first)
    all_results.sort(key=lambda x: x['completed_at'], reverse=True)
    
    print(f"👨‍🏫 [INSTRUCTOR RESULTS] Returning {len(all_results)} total exam results")
    for result in all_results:
        print(f"   {result['student_name']} ({result['student_id']}): {result['total_score']}/{result['max_score']} ({result['percentage']:.1f}%)")
    
    return {
        "total_results": len(all_results),
        "results": all_results
    }
@router.get("/students")
def list_students(user: dict = Depends(require_role("instructor"))):
    """Get list of all registered students"""
    students = []
    
    # Try to get from MongoDB first
    try:
        if mongo_service.is_connected():
            docs = mongo_service.list_students()
            for d in docs:
                students.append({
                    "student_id": d.get('student_id'),
                    "name": d.get('name'),
                    "email": d.get('email'),
                    "project_title": d.get('project_details', {}).get('title', 'Not specified')
                })
    except Exception:
        pass
    
    # Also add any students from in-memory cache that might not be in MongoDB yet
    for sid, data in exam_service.students.items():
        # Check if this student is already in the list
        if not any(s['student_id'] == sid for s in students):
            students.append({
                "student_id": sid,
                "name": data.get('name', 'Unknown'),
                "email": data.get('email', ''),
                "project_title": data.get('project_details', {}).get('title', 'Not specified')
            })
    
    return {"students": students, "total": len(students)}

@router.get("/students/{student_id}", response_model=StudentDetailResponse)
def get_student_details(
    student_id: str,
    user: dict = Depends(require_role("instructor"))
):
    """Get detailed info for a specific student"""
    if student_id not in exam_service.students:
        raise HTTPException(404, "Student not found")
    
    student = exam_service.students[student_id]
    return StudentDetailResponse(
        student_id=student_id,
        name=student['name'],
        email=student['email'],
        project_details=student['project_details'],
        case_study=student['case_study']
    )

@router.post("/schedule-exam")
def schedule_exam(
    schedule: ExamSchedule,
    user: dict = Depends(require_role("instructor"))
):
    """Schedule an exam for a student"""
    if schedule.student_id not in exam_service.students:
        raise HTTPException(404, "Student not found")
    
    # Parse time string
    try:
        start_time = datetime.strptime(schedule.start_time, "%Y-%m-%d %I:%M %p")
        start_time = start_time.replace(tzinfo=IST)
    except ValueError:
        raise HTTPException(
            400,
            "Invalid time format. Use: YYYY-MM-DD HH:MM AM/PM"
        )
    
    exam_service.schedule_exam(
        schedule.student_id,
        start_time,
        schedule.duration_minutes
    )
    
    return {
        "message": "Exam scheduled successfully",
        "student_id": schedule.student_id,
        "start_time": start_time.isoformat(),
        "duration": schedule.duration_minutes
    }

@router.get("/results/{exam_id}", response_model=GradingResult)
def get_exam_results(
    exam_id: str,
    user: dict = Depends(require_role("instructor"))
):
    """Get grading results for a specific exam"""
    exam_data = None
    
    # First check active exams
    if exam_id in exam_service.active_exams:
        exam_data = exam_service.active_exams[exam_id]
    else:
        # Check MongoDB for completed exams
        try:
            if mongo_service.is_connected():
                completed_exam = mongo_service.get_completed_exam_by_id(exam_id)
                if completed_exam:
                    exam_data = completed_exam
                else:
                    raise HTTPException(404, "Exam not found")
        except Exception:
            raise HTTPException(404, "Exam not found")
    
    if not exam_data or exam_data.get('status') != 'completed':
        raise HTTPException(400, "Exam not yet completed")
    
    # Use actual AI evaluation results
    total_score = exam_data.get('total_score', 0)
    max_score = exam_data.get('max_score', len(exam_data.get('questions', [])) or len(exam_data.get('question_scores', [])))
    
    # Calculate average cheat score
    responses = exam_data.get('responses', [])
    avg_cheat_score = sum(r.get('cheat_score', 0) for r in responses) / len(responses) if responses else 0
    
    print(f"👨‍🏫 [INSTRUCTOR EXAM DETAIL] Exam {exam_id}: {total_score}/{max_score} for student {exam_data['student_id']}")
    
    return GradingResult(
        student_id=exam_data['student_id'],
        total_score=total_score,
        scores={
            "technical_knowledge": total_score * 0.4,
            "problem_solving": total_score * 0.3,
            "communication": total_score * 0.3
        },
        strengths=["Good technical understanding", "Clear communication"],
        weaknesses=["Could elaborate more on edge cases"],
        feedback=exam_data.get('feedback', 'Solid performance overall.'),
        risk_level=exam_data.get('risk_level', 'LOW'),
        suspicion_score=avg_cheat_score,
        cheat_flags=exam_data.get('cheat_indicators', []) or exam_data.get('cheat_flags', [])
    )

@router.get("/dashboard")
def instructor_dashboard(user: dict = Depends(require_role("instructor"))):
    """Get instructor dashboard data"""
    scheduled_exams = [
        {
            "student_id": sid,
            "student_name": exam_service.students[sid]['name'],
            "start_time": schedule['start_time'].isoformat(),
            "duration": schedule['duration_minutes']
        }
        for sid, schedule in exam_service.exam_schedules.items()
        if schedule['end_time'] > datetime.now(IST)
    ]
    
    completed_exams = [
        {
            "exam_id": eid,
            "student_id": exam['student_id'],
            "completed_at": exam.get('completed_at', '').isoformat() if hasattr(exam.get('completed_at', ''), 'isoformat') else ''
        }
        for eid, exam in exam_service.active_exams.items()
        if exam['status'] == 'completed'
    ]
    
    return {
        "total_students": len(exam_service.students),
        "scheduled_exams": scheduled_exams,
        "completed_exams": completed_exams,
        "pending_grading": len([e for e in exam_service.active_exams.values() if e['status'] == 'completed'])
    }

@router.post("/upload_pdf", response_model=PDFUploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    instruction: str = Form(...),
    user: dict = Depends(require_role("instructor"))
):
    """
    Upload PDF and generate viva questions based on instruction
    
    Args:
        file: PDF file to upload
        instruction: Instruction/topic to generate questions from (e.g., "chapter 1 to chapter 3" or "3.2.4")
    
    Returns:
        PDFUploadResponse with generated questions
    """
    # Validate file type
    if file.content_type != "application/pdf":
        raise HTTPException(400, "Only PDF files are allowed")
    
    # Determine uploads directory (use UPLOADS_DIR env var or platform-safe default)
    uploads_dir = os.environ.get('UPLOADS_DIR')
    if not uploads_dir:
        if os.name == 'nt':
            uploads_dir = os.path.join(os.getcwd(), 'uploads')
        else:
            uploads_dir = '/tmp/uploads'
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir, exist_ok=True)
    
    # Save file
    file_path = os.path.join(uploads_dir, file.filename)
    try:
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(500, f"Failed to save file: {str(e)}")
    
    # Generate questions using Grok service
    try:
        questions = await grok_exam_service.generate_pdf_questions(file_path, instruction)
        
        return PDFUploadResponse(
            message="PDF processed successfully",
            questions=questions,
            pdf_name=file.filename,
            instruction=instruction
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to generate questions: {str(e)}")

@router.get("/schedule-pdf-exam")
async def get_pdf_exams(user: dict = Depends(require_role("instructor"))):
    """Debug endpoint - Get all scheduled PDF exams"""
    pdf_exams = {}
    for student_id, exam_data in exam_service.pdf_exams.items():
        student_name = exam_service.students.get(student_id, {}).get('name', 'Unknown')
        pdf_exams[student_id] = {
            "student_name": student_name,
            "exam_name": exam_data.get('exam_name'),
            "start_time": exam_data.get('start_time').isoformat() if exam_data.get('start_time') and hasattr(exam_data.get('start_time'), 'isoformat') else str(exam_data.get('start_time')),
            "duration": exam_data.get('duration_minutes'),
            "instruction": exam_data.get('instruction')
        }
    
    return {
        "total_pdf_exams": len(pdf_exams),
        "pdf_exams": pdf_exams,
        "all_students": list(exam_service.students.keys())
    }


@router.post("/schedule-pdf-exam")
async def schedule_pdf_exam(
    student_id: str = Form(...),
    file: UploadFile = File(...),
    instruction: str = Form(...),
    exam_name: str = Form(...),
    start_time: str = Form(None),
    duration_minutes: int = Form(None),
    user: dict = Depends(require_role("instructor"))
):
    """
    Schedule a PDF-based exam for a student
    
    Args:
        student_id: ID of the student
        file: PDF file to use for exam
        instruction: Instruction/topic for question generation
        exam_name: Name of the exam to display to student
        start_time: Optional start time (Format: "YYYY-MM-DD HH:MM AM/PM" or ISO format)
        duration_minutes: Optional duration in minutes
    
    Returns:
        Success message
    """
    # Validate student exists
    if student_id not in exam_service.students:
        raise HTTPException(404, f"Student not found. Available students: {list(exam_service.students.keys())}")
    
    print(f"\n{'='*80}")
    print(f"📝 SCHEDULE PDF EXAM REQUEST")
    print(f"{'='*80}")
    print(f"Student ID: {student_id}")
    print(f"File Name: {file.filename}")
    print(f"Content Type: {file.content_type}")
    print(f"Instruction: {instruction}")
    print(f"Exam Name: {exam_name}")
    
    # Validate file type
    if file.content_type != "application/pdf":
        raise HTTPException(400, "Only PDF files are allowed")
    
    # Determine uploads directory (use UPLOADS_DIR env var or platform-safe default)
    uploads_dir = os.environ.get('UPLOADS_DIR')
    if not uploads_dir:
        if os.name == 'nt':
            uploads_dir = os.path.join(os.getcwd(), 'uploads')
        else:
            uploads_dir = '/tmp/uploads'
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir, exist_ok=True)
    
    # Save file with unique name
    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join(uploads_dir, unique_filename)
    
    print(f"Full File Path: {os.path.abspath(file_path)}")
    
    try:
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
        print(f"✅ File saved successfully ({len(contents)} bytes)")
    except Exception as e:
        print(f"❌ File save failed: {e}")
        raise HTTPException(500, f"Failed to save file: {str(e)}")
    
    # Parse start time if provided
    parsed_start_time = None
    if start_time:
        try:
            # Try ISO format first (from datetime-local input)
            if 'T' in start_time:
                parsed_start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                # Convert to IST if it doesn't have timezone info
                if parsed_start_time.tzinfo is None:
                    parsed_start_time = parsed_start_time.replace(tzinfo=IST)
            else:
                # Try the other format
                parsed_start_time = datetime.strptime(start_time, "%Y-%m-%d %I:%M %p")
                parsed_start_time = parsed_start_time.replace(tzinfo=IST)
        except ValueError as e:
            raise HTTPException(400, f"Invalid time format. Use datetime picker or: YYYY-MM-DD HH:MM AM/PM. Error: {str(e)}")
    
    # Store PDF metadata in exam service
    try:
        print(f"\n{'='*80}")
        print(f"💾 STORING PDF EXAM METADATA")
        print(f"{'='*80}")
        print(f"Student ID: {student_id}")
        print(f"PDF Path: {os.path.abspath(file_path)}")
        print(f"Instruction: {instruction}")
        
        exam_service.store_pdf_exam_metadata(
            student_id=student_id,
            pdf_path=file_path,
            pdf_filename=file.filename,
            instruction=instruction,
            exam_name=exam_name,
            start_time=parsed_start_time,
            duration_minutes=duration_minutes
        )
        
        print(f"✅ PDF exam metadata stored successfully")
        print(f"{'='*80}\n")
        
        return {
            "message": f"PDF exam scheduled successfully for student",
            "student_id": student_id,
            "exam_name": exam_name,
            "pdf_name": file.filename,
            "instruction": instruction,
            "start_time": parsed_start_time.isoformat() if parsed_start_time else None,
            "duration_minutes": duration_minutes
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to schedule exam: {str(e)}")

