# ============================================================================
# FILE: app/api/routes/students.py - COMPLETE REPLACEMENT
# ============================================================================
from fastapi import APIRouter, Depends, HTTPException
from app.models.schemas import StudentProfile, DashboardResponse, ChangeStudentIDRequest
from app.api.dependencies import require_role, get_current_user
from app.services.exam_service import exam_service
from datetime import datetime, timedelta
from app.core.security import IST
from typing import List

router = APIRouter(prefix="/api/student", tags=["Students"])

@router.post("/profile")
def create_profile(
    profile: StudentProfile,
    user: dict = Depends(require_role("student"))
):
    """Create or update student profile"""
    # Simple validation - just check if student_id is provided
    if not profile.student_id or not profile.student_id.strip():
        raise HTTPException(400, "Student ID is required")

    # Check if profile already exists for this user
    existing_student_id = None
    for sid, data in exam_service.students.items():
        if data.get("email") == user["sub"]:
            existing_student_id = sid
            break

    # Register student in exam system
    student_data = {
        "student_id": profile.student_id,
        "name": profile.name,
        "email": user["sub"],  # Use authenticated user's email
        "project_title": profile.project_title,
        "project_description": profile.project_description,
        "technologies": profile.technologies,
        "metrics": profile.metrics,
        "case_study": profile.case_study
    }

    exam_service.register_student(student_data)

    if existing_student_id and existing_student_id != profile.student_id:
        # Student ID changed, remove old entry
        if existing_student_id in exam_service.students:
            del exam_service.students[existing_student_id]

    return {
        "message": "Profile created successfully",
        "student_id": profile.student_id
    }


@router.post("/change-id")
def change_student_id(
    body: ChangeStudentIDRequest,
    user: dict = Depends(require_role("student"))
):
    """Change the student's student_id safely: verifies password, checks uniqueness, and migrates data."""
    email = user["sub"]

    # Find current student_id by email
    current_student_id = None
    for sid, data in exam_service.students.items():
        if data.get("email") == email:
            current_student_id = sid
            break

    if not current_student_id:
        raise HTTPException(404, "Profile not found. Please create your profile first.")

    new_id = body.new_student_id.strip()
    if not new_id:
        raise HTTPException(400, "New student_id cannot be empty")

    # Check if new id already taken in-memory
    if new_id in exam_service.students and new_id != current_student_id:
        raise HTTPException(400, "New student_id already in use")

    # Verify password against user record (DB or in-memory)
    from app.services.mongo_service import mongo_service
    from app.core.security import verify_password

    user_record = None
    if mongo_service.is_connected():
        user_record = mongo_service.get_user_by_username(email)

    if not user_record:
        # Fallback to in-memory users (auth.users_db)
        try:
            from app.api.routes.auth import users_db
            user_record = users_db.get(email)
        except Exception:
            user_record = None

    if not user_record or not verify_password(body.current_password, user_record.get("hashed_password")):
        raise HTTPException(401, "Password verification failed")

    # At this point password verified. Proceed to update in-memory structures
    student_data = exam_service.students.pop(current_student_id)
    student_data["student_id"] = new_id
    exam_service.students[new_id] = student_data

    # Move exam_schedules mapping if present
    try:
        if current_student_id in exam_service.exam_schedules:
            exam_service.exam_schedules[new_id] = exam_service.exam_schedules.pop(current_student_id)
            exam_service.exam_schedules[new_id]["student_id"] = new_id
    except Exception:
        pass

    # Move student_pdf_exams list
    try:
        if current_student_id in exam_service.student_pdf_exams:
            exam_service.student_pdf_exams[new_id] = exam_service.student_pdf_exams.pop(current_student_id)
            # Update pdf_exams entries to point to new id
            for eid in exam_service.student_pdf_exams[new_id]:
                if eid in exam_service.pdf_exams:
                    exam_service.pdf_exams[eid]["student_id"] = new_id
    except Exception:
        pass

    # Update active_exams and completed maps
    try:
        for eid, edata in list(exam_service.active_exams.items()):
            if edata.get("student_id") == current_student_id:
                exam_service.active_exams[eid]["student_id"] = new_id
        for pid, pdata in list(exam_service.completed_pdf_exams.items()):
            if pdata.get("student_id") == current_student_id:
                exam_service.completed_pdf_exams[pid]["student_id"] = new_id
    except Exception:
        pass

    # Persist changes to MongoDB if available
    try:
        if mongo_service.is_connected():
            ok = mongo_service.update_student_id(current_student_id, new_id)
            if not ok:
                raise Exception("DB migration failed")
            # Also persist updated student document
            mongo_service.create_student(student_data)
    except Exception as e:
        # Rollback in-memory changes on failure
        exam_service.students.pop(new_id, None)
        exam_service.students[current_student_id] = student_data
        raise HTTPException(500, f"Failed to migrate student_id: {e}")

    return {"message": "Student ID changed successfully", "old_student_id": current_student_id, "new_student_id": new_id}


    # Persist to MongoDB if available
    try:
        from app.services.mongo_service import mongo_service
        if mongo_service.is_connected():
            mongo_service.create_student({
                "student_id": student_id,
                "name": updated["name"],
                "email": updated["email"],
                "project_details": updated["project_details"],
                "case_study": updated.get("case_study")
            })
    except Exception:
        pass

    return {"message": "Profile updated successfully", "student_id": student_id}

@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(user: dict = Depends(require_role("student"))):
    """Get student dashboard data"""
    student_email = user["sub"]
    
    # Find student by email
    student_data = None
    student_id = None
    for sid, data in exam_service.students.items():
        if data.get("email") == student_email:
            student_data = data
            student_id = sid
            break
    
    # If not found in memory, try MongoDB
    if not student_data:
        try:
            from app.services.mongo_service import mongo_service
            if mongo_service.is_connected():
                db_student = mongo_service.get_student_by_email(student_email)
                if db_student:
                    # Load into memory cache
                    exam_service.students[db_student['student_id']] = db_student
                    student_data = db_student
                    student_id = db_student['student_id']
        except Exception as e:
            pass
    
    if not student_data:
        return DashboardResponse(
            name="",
            upcoming_exams=[],
            past_results=[],
            profile_complete=False
        )
    
    # Check if profile is actually complete (has required fields)
    profile_complete = bool(
        student_data.get('name') and
        student_data.get('student_id') and
        student_data.get('email') and
        student_data.get('project_title')
    )
    
    # Get upcoming exams from exam_schedules
    upcoming = []
    # First, from in-memory
    if student_id in exam_service.exam_schedules:
        schedule = exam_service.exam_schedules[student_id]
        if schedule['end_time'] > datetime.now(IST):
            upcoming.append({
                "type": "project",
                "start_time": schedule['start_time'].isoformat(),
                "duration": schedule['duration_minutes']
            })
    
    # Also load from MongoDB if available
    try:
        from app.services.mongo_service import mongo_service
        if mongo_service.is_connected():
            db_schedule = mongo_service.get_exam_schedule(student_id)
            if db_schedule and db_schedule.get('end_time'):
                # Convert string to datetime if needed
                end_time = db_schedule['end_time']
                if isinstance(end_time, str):
                    end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                if end_time > datetime.now(IST):
                    # Avoid duplicates
                    if not any(u['type'] == 'project' for u in upcoming):
                        upcoming.append({
                            "type": "project",
                            "start_time": db_schedule['start_time'] if isinstance(db_schedule['start_time'], str) else db_schedule['start_time'].isoformat(),
                            "duration": db_schedule['duration_minutes']
                        })
    except Exception:
        pass

    # Get PDF exams from MongoDB if available, otherwise from in-memory
    pdf_exams_list = []
    try:
        from app.services.mongo_service import mongo_service
        if mongo_service.is_connected():
            pdf_exams_list = mongo_service.get_pdf_exams_by_student(student_id)
        else:
            pdf_exams_list = exam_service.get_all_pdf_exams_for_student(student_id)
    except Exception:
        pdf_exams_list = exam_service.get_all_pdf_exams_for_student(student_id)

    for pdf_meta in pdf_exams_list:
        exam_id = pdf_meta.get('exam_id')
        # Skip completed PDF exams so they don't appear in upcoming
        if exam_id in exam_service.completed_pdf_exams:
            continue

        # Calculate end time
        start_dt = pdf_meta.get('start_time')
        duration = pdf_meta.get('duration_minutes')
        end_time = None
        if start_dt and duration:
            end_dt = start_dt + timedelta(minutes=duration)
            end_time = end_dt.isoformat() if hasattr(end_dt, 'isoformat') else str(end_dt)

        upcoming.append({
            "type": "pdf",
            "exam_id": exam_id,
            "exam_name": pdf_meta.get('exam_name', 'PDF-Based Exam'),
            "start_time": pdf_meta.get('start_time').isoformat() if pdf_meta.get('start_time') and hasattr(pdf_meta.get('start_time'), 'isoformat') else (str(pdf_meta.get('start_time')) if pdf_meta.get('start_time') else None),
            "end_time": end_time,
            "duration": pdf_meta.get('duration_minutes'),
            "is_completed": False,
            "status": "Available"
        })
    
    # Get past results - look through completed exams
    past_results = []
    # First, from in-memory active_exams
    for exam_id, exam_data in exam_service.active_exams.items():
        if exam_data['student_id'] == student_id and exam_data['status'] == 'completed':
            # Use actual AI evaluation results instead of hardcoded scoring
            total_score = exam_data.get('total_score', 0)
            max_score = exam_data.get('max_score', len(exam_data.get('questions', [])))
            total_questions = len(exam_data.get('questions', []))
            
            past_results.append({
                "exam_id": exam_id,
                "completed_at": exam_data.get('completed_at', datetime.now(IST)).isoformat() if hasattr(exam_data.get('completed_at'), 'isoformat') else str(exam_data.get('completed_at')),
                "total_score": total_score,
                "total_questions": total_questions,
                "risk_level": exam_data.get('risk_level', 'UNKNOWN')
            })
    
    # Also load from MongoDB if available
    try:
        from app.services.mongo_service import mongo_service
        if mongo_service.is_connected():
            db_completed = mongo_service.get_completed_exams_by_student(student_id)
            for exam in db_completed:
                # Avoid duplicates
                if not any(r['exam_id'] == exam['exam_id'] for r in past_results):
                    # Use actual stored AI evaluation results
                    total_score = exam.get('total_score', 0)
                    total_questions = exam.get('total_questions', len(exam.get('question_scores', [])))
                    past_results.append({
                        "exam_id": exam['exam_id'],
                        "completed_at": exam.get('completed_at', ''),
                        "total_score": total_score,
                        "total_questions": total_questions,
                        "risk_level": exam.get('risk_level', 'UNKNOWN')
                    })
    except Exception:
        pass
    
    print(f"📊 [DASHBOARD] Returning dashboard for {student_data.get('name', '')}: {len(upcoming)} upcoming, {len(past_results)} completed exams")
    for result in past_results:
        print(f"   Completed: {result['exam_id']} - {result['total_score']}/{result['total_questions']} questions")
    
    return DashboardResponse(
        name=student_data.get('name', ''),
        upcoming_exams=upcoming,
        past_results=past_results,
        profile_complete=profile_complete
    )

@router.get("/student-id")
def get_student_id(user: dict = Depends(require_role("student"))):
    """Get the student ID for the logged-in student"""
    student_email = user["sub"]
    
    # Find student by email
    for student_id, data in exam_service.students.items():
        if data.get("email") == student_email:
            return {
                "student_id": student_id,
                "name": data.get("name"),
                "email": student_email
            }
    
    # Student not found
    raise HTTPException(404, "Student profile not found. Please create your profile first.")

@router.get("/results")
def get_my_results(user: dict = Depends(require_role("student"))):
    """Get all exam results for the logged-in student"""
    student_email = user["sub"]
    
    # Find student ID by email
    student_id = None
    student_name = ""
    for sid, data in exam_service.students.items():
        if data.get("email") == student_email:
            student_id = sid
            student_name = data.get("name", "")
            break
    
    if not student_id:
        raise HTTPException(404, "Student profile not found. Please create your profile first.")
    
    # Get all completed exams for this student
    results = []
    
    # First, from in-memory active_exams
    for exam_id, exam_data in exam_service.active_exams.items():
        if exam_data['student_id'] == student_id and exam_data['status'] == 'completed':
            # Use actual AI evaluation results
            total_score = exam_data.get('total_score', 0)
            max_score = exam_data.get('max_score', len(exam_data.get('questions', [])))
            percentage = exam_data.get('percentage', 0)
            total_questions = len(exam_data.get('questions', []))
            
            # Calculate average cheat score
            responses = exam_data.get('responses', [])
            avg_cheat_score = sum(r.get('cheat_score', 0) for r in responses) / len(responses) if responses else 0
            
            results.append({
                "exam_id": exam_id,
                "completed_at": exam_data.get('completed_at', datetime.now(IST)).isoformat() if hasattr(exam_data.get('completed_at'), 'isoformat') else str(exam_data.get('completed_at')),
                "total_score": total_score,
                "max_score": max_score,
                "percentage": percentage,
                "scores": {
                    "technical_knowledge": total_score * 0.4,
                    "problem_solving": total_score * 0.3,
                    "communication": total_score * 0.3
                },
                "total_questions": total_questions,
                "risk_level": exam_data.get('risk_level', 'LOW'),
                "suspicion_score": avg_cheat_score,
                "feedback": "Your exam has been evaluated. Great job!" if avg_cheat_score < 3 else "Your performance has been recorded. Please contact your instructor for detailed feedback."
            })
    
    # Also load from MongoDB if available
    try:
        from app.services.mongo_service import mongo_service
        if mongo_service.is_connected():
            db_completed = mongo_service.get_completed_exams_by_student(student_id)
            for exam in db_completed:
                # Avoid duplicates
                if not any(r['exam_id'] == exam['exam_id'] for r in results):
                    total_score = exam.get('total_score', 0)
                    max_score = exam.get('max_score', len(exam.get('question_scores', [])))
                    percentage = exam.get('percentage', 0)
                    total_questions = len(exam.get('question_scores', []))
                    
                    # Calculate average cheat score from responses
                    responses = exam.get('responses', [])
                    avg_cheat_score = sum(r.get('cheat_score', 0) for r in responses) / len(responses) if responses else 0
                    
                    results.append({
                        "exam_id": exam['exam_id'],
                        "completed_at": exam.get('completed_at', ''),
                        "total_score": total_score,
                        "max_score": max_score,
                        "percentage": percentage,
                        "scores": {
                            "technical_knowledge": total_score * 0.4,
                            "problem_solving": total_score * 0.3,
                            "communication": total_score * 0.3
                        },
                        "total_questions": total_questions,
                        "risk_level": exam.get('risk_level', 'LOW'),
                        "suspicion_score": avg_cheat_score,
                        "feedback": exam.get('feedback', 'Your exam has been evaluated.')
                    })
    except Exception as e:
        print(f"Warning: Could not load completed exams from MongoDB: {e}")
    
    print(f"📊 [RESULTS] Returning {len(results)} exam results for student {student_id}")
    for result in results:
        print(f"   Exam {result['exam_id']}: {result['total_score']}/{result['max_score']} ({result['percentage']:.1f}%)")
    
    return {
        "student_id": student_id,
        "student_name": student_name,
        "total_exams": len(results),
        "results": results
    }

@router.get("/results/{exam_id}")
def get_specific_result(exam_id: str, user: dict = Depends(require_role("student"))):
    """Get detailed results for a specific exam"""
    student_email = user["sub"]
    
    # Find student ID
    student_id = None
    for sid, data in exam_service.students.items():
        if data.get("email") == student_email:
            student_id = sid
            break
    
    if not student_id:
        raise HTTPException(404, "Student profile not found")
    
    exam_data = None
    
    # First check active exams
    if exam_id in exam_service.active_exams:
        exam_data = exam_service.active_exams[exam_id]
        # Verify this exam belongs to the student
        if exam_data['student_id'] != student_id:
            raise HTTPException(403, "You can only view your own exam results")
        
        # Check if exam is completed
        if exam_data['status'] != 'completed':
            raise HTTPException(400, "Exam is not yet completed")
    else:
        # Check MongoDB for completed exams
        try:
            from app.services.mongo_service import mongo_service
            if mongo_service.is_connected():
                completed_exam = mongo_service.get_completed_exam_by_id(exam_id)
                if completed_exam and completed_exam.get('student_id') == student_id:
                    exam_data = completed_exam
                else:
                    raise HTTPException(404, "Exam not found")
            else:
                raise HTTPException(404, "Exam not found")
        except Exception as e:
            print(f"Error loading exam from MongoDB: {e}")
            raise HTTPException(404, "Exam not found")
    
    # Use the actual scores calculated during end_exam
    total_score = exam_data.get('total_score', 0)
    max_score = exam_data.get('max_score', len(exam_data.get('questions', [])) or len(exam_data.get('question_scores', [])))
    percentage = exam_data.get('percentage', 0)
    total_questions = len(exam_data.get('questions', [])) or len(exam_data.get('question_scores', []))
    
    responses = exam_data.get('responses', [])
    avg_cheat_score = sum(r.get('cheat_score', 0) for r in responses) / len(responses) if responses else 0
    
    # Get conversation transcript (might be in different field for MongoDB data)
    transcript = exam_data.get('transcript', []) or exam_data.get('question_scores', [])
    
    print(f"📋 [DETAILED RESULT] Exam {exam_id}: {total_score}/{max_score} ({percentage:.1f}%) for student {student_id}")
    
    return {
        "exam_id": exam_id,
        "student_id": student_id,
        "completed_at": exam_data.get('completed_at', ''),
        "total_score": total_score,
        "max_score": max_score,
        "percentage": percentage,
        "scores": {
            "technical_knowledge": total_score * 0.4,
            "problem_solving": total_score * 0.3,
            "communication": total_score * 0.3
        },
        "total_questions": total_questions,
        "total_answers": len(responses) if responses else len([r for r in transcript if isinstance(r, dict) and r.get('student_answer')]),
        "risk_level": exam_data.get('risk_level', 'LOW'),
        "suspicion_score": avg_cheat_score,
        "cheat_flags": exam_data.get('cheat_indicators', []) or exam_data.get('cheat_flags', []),
        "feedback": exam_data.get('feedback', 'Your exam has been evaluated.'),
        "transcript_available": len(transcript) > 0
    }