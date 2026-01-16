from typing import Dict, List
from datetime import datetime, timedelta
from app.core.security import IST
from app.services.cheat_detector import CheatDetector
from app.services.grok_service import GrokExamService
from app.services.mongo_service import mongo_service
import pdfplumber
import os

class ExamService:
    def __init__(self):
        self.students: Dict = {}
        self.exam_schedules: Dict = {}
        self.active_exams: Dict = {}
        self.pdf_exams: Dict = {}  # Store PDF exam metadata: exam_id -> exam_data
        self.student_pdf_exams: Dict = {}  # Store student_id -> [exam_ids] for quick lookup
        self.completed_pdf_exams: Dict = {}  # Track completed PDF exams: exam_id -> completion_data
        self.cheat_detector = CheatDetector()
        self.grok_service = GrokExamService()

        # Load persisted data from MongoDB if available
        self._load_from_db()

    def _load_from_db(self):
        """Load persisted data from MongoDB on startup"""
        try:
            if mongo_service.is_connected():
                # Load students
                student_docs = mongo_service.list_students()
                for doc in student_docs:
                    # Handle backward compatibility: flatten nested project_details if present
                    if 'project_details' in doc:
                        doc['project_title'] = doc['project_details']['title']
                        doc['project_description'] = doc['project_details']['description']
                        doc['technologies'] = doc['project_details']['technologies']
                        doc['metrics'] = doc['project_details']['metrics']
                        del doc['project_details']
                    self.students[doc['student_id']] = doc
                print(f"Loaded {len(student_docs)} students from MongoDB")

                # Load completed PDF exams first to prevent them from appearing in upcoming exams
                completed_pdf_docs = mongo_service.get_all_completed_pdf_exams()
                for doc in completed_pdf_docs:
                    exam_id = doc.get('exam_id') or doc.get('pdf_metadata', {}).get('exam_id')
                    if exam_id:
                        self.completed_pdf_exams[exam_id] = {
                            'exam_id': exam_id,
                            'student_id': doc['student_id'],
                            'completed_at': doc.get('completed_at', ''),
                            'exam_name': doc.get('pdf_metadata', {}).get('exam_name', 'PDF Exam')
                        }
                print(f"Loaded {len(completed_pdf_docs)} completed PDF exams from MongoDB")

                # Load PDF exams and rebuild mappings, excluding completed ones
                pdf_docs = mongo_service.get_all_pdf_exams()
                for doc in pdf_docs:
                    exam_id = doc['exam_id']
                    student_id = doc['student_id']
                    self.pdf_exams[exam_id] = doc
                    # Only add to student_pdf_exams if not completed
                    if exam_id not in self.completed_pdf_exams:
                        if student_id not in self.student_pdf_exams:
                            self.student_pdf_exams[student_id] = []
                        self.student_pdf_exams[student_id].append(exam_id)
                print(f"Loaded {len(pdf_docs)} PDF exams from MongoDB")
                
                # Load exam schedules
                # Since we don't have get_all_schedules, we can skip for now or add later
        except Exception as e:
            print(f"Warning: Could not load data from MongoDB: {e}")

    def register_student(self, student_data: Dict):
        """Register a new student"""
        # Store in in-memory cache
        self.students[student_data['student_id']] = student_data
        # Persist to MongoDB if available
        try:
            mongo_service.create_student(student_data)
        except Exception:
            pass
    
    def schedule_exam(self, student_id: str, start_time: datetime, duration_minutes: int):
        """Schedule an exam for a student"""
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        schedule_data = {
            "student_id": student_id,
            "start_time": start_time,
            "end_time": end_time,
            "duration_minutes": duration_minutes
        }
        
        self.exam_schedules[student_id] = schedule_data
        
        # Persist to MongoDB
        try:
            mongo_service.create_exam_schedule(schedule_data)
        except Exception as e:
            print(f"Warning: Could not persist exam schedule to DB: {e}")
    
    def can_start_exam(self, student_id: str, exam_id: str = None) -> tuple[bool, str]:
        """Check if student can start exam now"""
        # Check for PDF exams
        pdf_exams = self.get_all_pdf_exams_for_student(student_id)
        if pdf_exams:
            # If exam_id provided, check that specific exam
            if exam_id:
                exam_to_check = None
                for exam in pdf_exams:
                    if exam.get('exam_id') == exam_id:
                        exam_to_check = exam
                        break
                
                if not exam_to_check:
                    return False, "Exam not found"
            else:
                # Use first available exam
                exam_to_check = pdf_exams[0]
                exam_id = exam_to_check.get('exam_id')
            
            # Check if already completed
            if exam_id in self.completed_pdf_exams:
                return False, "You have already completed this exam"
            
            # Check if PDF exam has scheduling constraints
            if exam_to_check.get('start_time') and exam_to_check.get('duration_minutes'):
                # Scheduled PDF exam - check time window
                now = datetime.now(IST)
                start = exam_to_check['start_time']
                end = start + timedelta(minutes=exam_to_check['duration_minutes'])
                
                if now < start:
                    return False, "Exam has not started yet"
                if now > end:
                    return False, "Exam window has closed"
            
            # Check if already in progress
            for exam in self.active_exams.values():
                if exam['student_id'] == student_id and exam['status'] == 'in_progress':
                    return False, "Exam already in progress"
            return True, "OK"
        
        # Check for scheduled project exam
        if student_id not in self.exam_schedules:
            return False, "Exam not scheduled"
        
        now = datetime.now(IST)
        schedule = self.exam_schedules[student_id]
        
        if now < schedule['start_time']:
            return False, "Exam has not started yet"
        
        if now > schedule['end_time']:
            return False, "Exam window has closed"
        
        # Check if already in progress
        for exam in self.active_exams.values():
            if exam['student_id'] == student_id and exam['status'] == 'in_progress':
                return False, "Exam already in progress"
        
        return True, "OK"
    
    def start_exam(self, student_id: str, exam_data: Dict = None) -> Dict:
        """Start a new exam session with text questions based on project or PDF content"""
        try:
            exam_id = f"exam_{student_id}_{int(datetime.now(IST).timestamp())}"

            student = self.students[student_id]
        
            # Check if this is a PDF exam
            pdf_content = None
            is_pdf_exam = False
            pdf_metadata = None

            # First check if PDF content is provided directly in exam_data
            if exam_data and exam_data.get('pdf_content'):
                pdf_content = exam_data['pdf_content']
                is_pdf_exam = True
                pdf_metadata = exam_data
                print(f"✅ [START_EXAM] Using provided PDF content ({len(pdf_content)} chars)")

            # Otherwise, try to extract from PDF file
            elif exam_data and exam_data.get('type') == 'pdf' and exam_data.get('exam_id'):
                pdf_exam_id = exam_data['exam_id']
                if pdf_exam_id in self.pdf_exams:
                    pdf_meta = self.pdf_exams[pdf_exam_id]
                    is_pdf_exam = True
                    pdf_metadata = pdf_meta
                    # Extract PDF content
                    pdf_path = pdf_meta.get('pdf_path')
                    if pdf_path:
                        # Ensure absolute path from project root
                        if not os.path.isabs(pdf_path):
                            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                            pdf_path = os.path.join(project_root, pdf_path)
                        if os.path.exists(pdf_path):
                            try:
                                with pdfplumber.open(pdf_path) as pdf:
                                    pdf_content = ""
                                    for page in pdf.pages:
                                        page_text = page.extract_text()
                                        if page_text:
                                            pdf_content += page_text + "\n"
                                    print(f"✅ [START_EXAM] Extracted {len(pdf_content)} chars from PDF")
                            except Exception as e:
                                print(f"❌ [START_EXAM] Error extracting PDF content: {e}")
                                pdf_content = None
                        else:
                            print(f"❌ [START_EXAM] PDF file not found: {pdf_path}")
                    else:
                        print(f"❌ [START_EXAM] No PDF path in metadata")

            # If no exam_data provided but PDF exams available, use the first available PDF exam
            elif not exam_data:
                pdf_exams = self.get_all_pdf_exams_for_student(student_id)
                if pdf_exams:
                    pdf_meta = pdf_exams[0]  # Use first available
                    pdf_exam_id = pdf_meta['exam_id']
                    is_pdf_exam = True
                    pdf_metadata = pdf_meta
                    # Extract PDF content
                    pdf_path = pdf_meta.get('pdf_path')
                    if pdf_path:
                        # Ensure absolute path from project root
                        if not os.path.isabs(pdf_path):
                            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                            pdf_path = os.path.join(project_root, pdf_path)
                        if os.path.exists(pdf_path):
                            try:
                                with pdfplumber.open(pdf_path) as pdf:
                                    pdf_content = ""
                                    for page in pdf.pages:
                                        page_text = page.extract_text()
                                        if page_text:
                                            pdf_content += page_text + "\n"
                                    print(f"✅ [START_EXAM] Extracted {len(pdf_content)} chars from PDF")
                            except Exception as e:
                                print(f"❌ [START_EXAM] Error extracting PDF content: {e}")
                                pdf_content = None
                        else:
                            print(f"❌ [START_EXAM] PDF file not found: {pdf_path}")
                    else:
                        print(f"❌ [START_EXAM] No PDF path in metadata")
                    pdf_meta = self.pdf_exams[pdf_exam_id]
                    # Extract PDF content
                    pdf_path = pdf_meta.get('pdf_path')
                    if pdf_path:
                        # Ensure absolute path from project root
                        if not os.path.isabs(pdf_path):
                            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                            pdf_path = os.path.join(project_root, pdf_path)
                        if os.path.exists(pdf_path):
                            try:
                                with pdfplumber.open(pdf_path) as pdf:
                                    pdf_content = ""
                                    for page in pdf.pages:
                                        page_text = page.extract_text()
                                        if page_text:
                                            pdf_content += page_text + "\n"
                                    print(f"✅ [START_EXAM] Extracted {len(pdf_content)} chars from PDF")
                            except Exception as e:
                                print(f"❌ [START_EXAM] Error extracting PDF content: {e}")
                                pdf_content = None
                        else:
                            print(f"❌ [START_EXAM] PDF file not found: {pdf_path}")
                    else:
                        print(f"❌ [START_EXAM] No PDF path in metadata")

            # If PDF content extraction failed, create fallback content for PDF exams
            if is_pdf_exam and not pdf_content:
                exam_name = pdf_metadata.get('exam_name', 'the subject') if pdf_metadata else 'the subject'
                pdf_content = f"This is a PDF-based examination about {exam_name}. The exam covers important concepts and topics related to {exam_name}. Students are expected to demonstrate their understanding of the key principles and applications discussed in the material."
                print(f"⚠️ [START_EXAM] Using fallback PDF content for {exam_name}")

            # Generate questions
            questions = self.grok_service.generate_exam_questions(
                exam_id=exam_id,
                project_details={
                    'title': student.get('project_title', 'Project'),
                    'description': student.get('project_description', 'Project description'),
                    'technologies': student.get('technologies', []),
                    'metrics': student.get('metrics', [])
                },
                pdf_content=pdf_content,
                num_questions=8
            )

            exam_data_to_store = {
                "exam_id": exam_id,
                "student_id": student_id,
                "start_time": datetime.now(IST),
                "status": "in_progress",
                "questions": questions,
                "current_question_index": 0,
                "answers": {},
                "responses": [],
                "cheat_indicators": [],
                "is_pdf_exam": is_pdf_exam,
                "pdf_metadata": pdf_metadata
            }

            self.active_exams[exam_id] = exam_data_to_store

            # Get first question
            first_question_data = questions[0]
            first_question = first_question_data["question"]
            if first_question_data["type"] == "mcq":
                options_text = "\n".join([f"{chr(65+i)}) {opt}" for i, opt in enumerate(first_question_data["options"])])
                first_question = f"{first_question}\n\n{options_text}"

            return {
                "exam_id": exam_id,
                "first_question": first_question,
                "student_name": student['name']
            }
        except Exception as e:
            import traceback, json
            print(f"❌ [EXAM_SERVICE] Exception in start_exam for student_id={student_id}")
            try:
                print(f"  exam_data keys: {list(exam_data.keys()) if isinstance(exam_data, dict) else exam_data}")
            except Exception:
                pass
            try:
                print(f"  student present: {student_id in self.students}")
            except Exception:
                pass
            traceback.print_exc()
            # Re-raise to be handled by route (which will log and return 500)
            raise
    
    def process_answer(self, exam_id: str, answer: str, response_time: float) -> Dict:
        """Process student answer and get next question"""
        exam = self.active_exams[exam_id]
        current_index = exam['current_question_index']
        questions = exam['questions']
        
        # Store the answer for current question
        current_question = questions[current_index]
        exam['answers'][current_question['id']] = answer
        
        # Analyze for cheating (simplified for now)
        cheat_analysis = self.cheat_detector.analyze_response(
            question=current_question['question'],
            answer=answer,
            response_time=response_time,
            question_difficulty=1  # Default difficulty
        )
        
        # Store response data
        exam['responses'].append({
            "question_id": current_question['id'],
            "question_type": current_question['type'],
            "answer": answer,
            "response_time": response_time,
            "timestamp": datetime.now(IST).isoformat(),
            "cheat_score": cheat_analysis['suspicion_score']
        })
        
        if cheat_analysis['flags']:
            exam['cheat_indicators'].extend(cheat_analysis['flags'])
        
        # Move to next question
        next_index = current_index + 1
        
        if next_index >= len(questions):
            # Exam completed
            return {
                "exam_completed": True,
                "message": "Exam completed successfully!"
            }
        
        # Get next question
        next_question_data = questions[next_index]
        next_question = next_question_data["question"]
        
        # Update current question index
        exam['current_question_index'] = next_index
        
        return {
            "next_question": next_question,
            "question_number": next_index + 1,
            "total_questions": len(questions)
        }
    
    def end_exam(self, exam_id: str) -> Dict:
        """Complete exam and generate grading"""
        exam = self.active_exams[exam_id]
        student_id = exam['student_id']
        questions = exam['questions']
        answers = exam['answers']
        
        # Calculate scores for each question (text-based evaluation)
        total_score = 0
        max_score = len(questions)
        question_scores = []
        
        for question in questions:
            question_id = question['id']
            answer = answers.get(question_id, "")
            
            # Use AI evaluation for text questions
            try:
                evaluation = self.grok_service.evaluate_answer(question['question'], answer)
                score = evaluation['score']
                feedback = evaluation['feedback']
                evaluation_text = evaluation['evaluation']
            except Exception as e:
                print(f"⚠️ [EVALUATION] Failed to evaluate answer for question {question_id}: {e}")
                # Fallback to basic evaluation
                answer_length = len(answer.strip())
                score = 1.0 if answer_length > 0 else 0
                feedback = "Answer recorded but evaluation failed."
                evaluation_text = "Basic evaluation used"
            
            question_scores.append({
                "question_id": question_id,
                "question": question['question'],
                "type": "text",
                "student_answer": answer,
                "score": score,
                "max_score": 1,
                "feedback": feedback,
                "evaluation": evaluation_text
            })
            
            total_score += score
        
        # Calculate percentage
        percentage = (total_score / max_score) * 100 if max_score > 0 else 0
        
        print(f"🎯 [EXAM SCORES] Exam {exam_id} completed for student {student_id}")
        print(f"🎯 [EXAM SCORES] Total Score: {total_score}/{max_score} ({percentage:.1f}%)")
        print(f"🎯 [EXAM SCORES] Individual question scores:")
        for i, q_score in enumerate(question_scores):
            print(f"   Q{i+1}: {q_score['score']:.2f}/1.00 - {q_score['question'][:50]}...")
        
        # Calculate cheat score
        total_cheat_score = sum(r['cheat_score'] for r in exam['responses'])
        avg_cheat_score = total_cheat_score / len(exam['responses']) if exam['responses'] else 0
        
        # Determine risk level
        if avg_cheat_score >= 6:
            risk_level = "HIGH"
        elif avg_cheat_score >= 3:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        # Generate feedback based on performance
        if percentage >= 80:
            feedback = "Excellent performance! You demonstrated strong understanding of the material."
        elif percentage >= 60:
            feedback = "Good performance. You have a solid grasp of most concepts but could improve in some areas."
        else:
            feedback = "Needs improvement. Consider reviewing the material and practicing more."
        
        exam['status'] = 'completed'
        exam['completed_at'] = datetime.now(IST)
        exam['total_score'] = total_score
        exam['max_score'] = max_score
        exam['percentage'] = percentage
        exam['question_scores'] = question_scores
        
        # Persist completed exam to MongoDB
        try:
            mongo_service.create_completed_exam({
                "exam_id": exam_id,
                "student_id": student_id,
                "status": "completed",
                "completed_at": exam['completed_at'].isoformat() if hasattr(exam['completed_at'], 'isoformat') else str(exam['completed_at']),
                "total_score": total_score,
                "max_score": max_score,
                "percentage": percentage,
                "question_scores": question_scores,
                "responses": exam.get('responses', []),
                "cheat_indicators": exam.get('cheat_indicators', []),
                "risk_level": risk_level,
                "feedback": feedback,
                "is_pdf_exam": exam.get('is_pdf_exam', False),
                "pdf_metadata": exam.get('pdf_metadata', {})
            })
            print(f"💾 [EXAM SAVED] Exam {exam_id} saved to database with score {total_score}/{max_score}")
        except Exception as e:
            print(f"Warning: Could not persist completed exam to DB: {e}")
        
        # Mark PDF exam as completed
        if exam.get('is_pdf_exam'):
            pdf_exam_id = exam.get('pdf_metadata', {}).get('exam_id')
            self.completed_pdf_exams[pdf_exam_id] = {
                'exam_id': pdf_exam_id,
                'student_id': student_id,
                'completed_at': datetime.now(IST),
                'exam_name': exam.get('pdf_metadata', {}).get('exam_name', 'PDF Exam')
            }
            # Remove this exam from the student's upcoming list so it no longer appears
            try:
                if student_id in self.student_pdf_exams:
                    if pdf_exam_id in self.student_pdf_exams[student_id]:
                        self.student_pdf_exams[student_id].remove(pdf_exam_id)
            except Exception:
                pass
        else:
            # If this was a project-based exam, remove any scheduled entry so it no longer appears as upcoming
            try:
                if student_id in self.exam_schedules:
                    self.exam_schedules.pop(student_id, None)
                # Also delete from DB
                mongo_service.delete_exam_schedule(student_id)
            except Exception:
                pass
        
        return {
            "exam_id": exam_id,
            "student_id": student_id,
            "total_questions": max_score,
            "suspicion_score": avg_cheat_score,
            "risk_level": risk_level,
            "cheat_flags": list(set(exam['cheat_indicators']))
        }
    
    def store_pdf_exam_metadata(self, student_id: str, pdf_path: str, pdf_filename: str, instruction: str, exam_name: str = None, start_time = None, duration_minutes: int = None):
        """Store PDF exam metadata for a student"""
        import uuid
        exam_id = f"pdf_exam_{uuid.uuid4()}"
        
        self.pdf_exams[exam_id] = {
            "exam_id": exam_id,
            "student_id": student_id,
            "pdf_path": pdf_path,
            "pdf_filename": pdf_filename,
            "instruction": instruction,
            "exam_name": exam_name or "PDF-Based Exam",
            "start_time": start_time,
            "duration_minutes": duration_minutes,
            "created_at": datetime.now(IST)
        }
        
        # Add to student's exam list
        if student_id not in self.student_pdf_exams:
            self.student_pdf_exams[student_id] = []
        self.student_pdf_exams[student_id].append(exam_id)
        # Persist to MongoDB if available
        try:
            from app.services.mongo_service import mongo_service
            mongo_service.create_pdf_exam(self.pdf_exams[exam_id])
        except Exception:
            pass

        return exam_id
    
    def get_pdf_exam_metadata(self, student_id: str) -> Dict:
        """Get first PDF exam metadata for a student (for backward compatibility)"""
        if student_id in self.student_pdf_exams and self.student_pdf_exams[student_id]:
            exam_id = self.student_pdf_exams[student_id][-1]
            return self.pdf_exams.get(exam_id, None)
        return None
    
    def get_all_pdf_exams_for_student(self, student_id: str) -> List[Dict]:
        """Get all PDF exams for a student"""
        exam_ids = self.student_pdf_exams.get(student_id, [])
        exams = []
        for exam_id in exam_ids:
            if exam_id in self.pdf_exams:
                exams.append(self.pdf_exams[exam_id])
        return exams

    def _check_mcq_answer(self, student_answer: str, correct_answer: str, options: List[str]) -> bool:
        """Check if MCQ answer is correct"""
        if not student_answer or not correct_answer:
            return False
        
        # Clean up student answer
        student_answer = student_answer.strip().upper()
        
        # If student answered with letter (A, B, C, D)
        if len(student_answer) == 1 and student_answer in 'ABCD':
            # Convert letter to index (A=0, B=1, etc.)
            answer_index = ord(student_answer) - ord('A')
            if 0 <= answer_index < len(options):
                selected_option = options[answer_index]
                return selected_option.strip().lower() == correct_answer.strip().lower()
        
        # If student answered with the full text
        return student_answer.lower() == correct_answer.lower()

# Global instance
exam_service = ExamService()