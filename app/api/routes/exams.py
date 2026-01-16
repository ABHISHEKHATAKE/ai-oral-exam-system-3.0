from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from app.models.schemas import ExamRequest, ExamResponse
from app.api.dependencies import require_role, get_current_user
from app.services.exam_service import exam_service
from app.services.grok_service import grok_exam_service
from app.services.voice_service import voice_service
from app.core.security import decode_token
from datetime import datetime
import json
from datetime import datetime, timezone, timedelta
import base64
import os

IST = timezone(timedelta(hours=5, minutes=30))


router = APIRouter(prefix="/api/exams", tags=["Exams"])

@router.post("/start", response_model=ExamResponse)
def start_exam(
    request: dict,
    user: dict = Depends(require_role("student"))
):
    """Start an exam session"""
    print(f"\n✅ [START_EXAM] Endpoint called")
    print(f"✅ [START_EXAM] User: {user['sub']}")
    print(f"✅ [START_EXAM] Raw request: {request}")
    request_value = request.get('student_id') if isinstance(request, dict) else None
    print(f"✅ [START_EXAM] Student identifier in request: {request_value}")
    
    # Verify student is starting their own exam
    student = exam_service.students.get(request_value)
    resolved_student_id = request_value
    # If not found by student_id, try to resolve by email
    if not student and request_value:
        for sid, data in exam_service.students.items():
            if data.get('email') == request_value:
                student = data
                resolved_student_id = sid
                break

    if not student:
        print(f"❌ [START_EXAM] Student {request_value} not found")
        raise HTTPException(404, "Student not found")
    
    if student.get('email') != user.get("sub"):
        print(f"❌ [START_EXAM] Email mismatch: {student.get('email')} != {user.get('sub')}")
        raise HTTPException(403, "You can only start your own exam")
    
    print(f"✅ [START_EXAM] Student found: {student['name']}")
    
    # If frontend provided exam_data (student selected a specific exam), skip scheduling check
    exam_data = request.get('exam_data') if isinstance(request, dict) else None
    if not exam_data:
        can_start, message = exam_service.can_start_exam(resolved_student_id)
        if not can_start:
            print(f"❌ [START_EXAM] Cannot start exam: {message}")
            raise HTTPException(400, message)
    
    print(f"✅ [START_EXAM] Can start exam - calling exam_service.start_exam()")

    # Start exam
    # Use resolved_student_id (could have been found via email)
    try:
        result = exam_service.start_exam(resolved_student_id, exam_data)
    except Exception as e:
        import traceback
        print(f"❌ [START_EXAM] Exception while starting exam for {resolved_student_id}: {e}")
        traceback.print_exc()
        # Return exception message in response for debugging (remove in production)
        raise HTTPException(status_code=500, detail=f"Internal server error while starting exam: {e}")
    
    print(f"✅ [START_EXAM] Exam started successfully!")
    print(f"✅ [START_EXAM] Exam ID: {result['exam_id']}")
    print(f"✅ [START_EXAM] Active exams: {list(exam_service.active_exams.keys())}")
    print(f"✅ [START_EXAM] Grok conversations: {list(grok_exam_service.conversations.keys())}")
    
    return ExamResponse(
        exam_id=result['exam_id'],
        student_id=resolved_student_id,
        student_name=result['student_name'],
        status="in_progress",
        created_at=datetime.now(IST).isoformat(),
        first_question=result.get('first_question')
    )

@router.post("/process_answer")
def process_answer(
    request: dict,
    user: dict = Depends(require_role("student"))
):
    """Process student answer and return next question"""
    exam_id = request.get('exam_id')
    answer = request.get('answer')
    response_time = request.get('response_time', 0)
    
    if not exam_id or not answer:
        raise HTTPException(400, "exam_id and answer are required")
    
    # Verify exam exists and belongs to student
    if exam_id not in exam_service.active_exams:
        raise HTTPException(404, "Exam not found")
    
    exam = exam_service.active_exams[exam_id]
    # Allow token payloads that include either `student_id` or only `sub` (email)
    token_student_id = user.get('student_id')
    token_sub = user.get('sub')
    if token_student_id:
        if exam['student_id'] != token_student_id:
            raise HTTPException(403, "You can only answer your own exam")
    else:
        # Fall back to email comparison
        student_record = exam_service.students.get(exam['student_id'], {})
        student_email = student_record.get('email')
        if student_email != token_sub:
            raise HTTPException(403, "You can only answer your own exam")
    
    # Process the answer
    result = exam_service.process_answer(exam_id, answer, response_time)
    
    return result

@router.websocket("/ws/{exam_id}")
async def exam_websocket(websocket: WebSocket, exam_id: str):
    """WebSocket for real-time exam interaction (text mode)"""
    await websocket.accept()
    
    # Authenticate via query param token
    token = websocket.query_params.get("token")
    mode = websocket.query_params.get("mode", "text")
    
    if not token:
        await websocket.send_json({"error": "Authentication required"})
        await websocket.close()
        return
    
    try:
        user = decode_token(token)
        if user["role"] != "student":
            await websocket.send_json({"error": "Only students can take exams"})
            await websocket.close()
            return
    except:
        await websocket.send_json({"error": "Invalid token"})
        await websocket.close()
        return
    
    # Verify exam exists
    if exam_id not in exam_service.active_exams:
        await websocket.send_json({"error": "Invalid exam ID"})
        await websocket.close()
        return
    
    exam = exam_service.active_exams[exam_id]
    exam['mode'] = mode  # Store mode for tracking
    
    # Send first question
    await websocket.send_json({
        "type": "question",
        "content": exam.get("first_question", "Please introduce yourself."),
        "mode": mode
    })
    
    try:
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "answer":
                answer = data.get("content")
                response_time = data.get("response_time", 0)
                
                print(f"📝 [ANSWER RECEIVED] Exam {exam_id}: '{answer[:100]}...' (length: {len(answer)}, time: {response_time:.1f}s)")
                
                # Process answer
                result = exam_service.process_answer(exam_id, answer, response_time)
                
                # Check if exam is completed
                if result.get("exam_completed"):
                    # End exam and get results
                    try:
                        final_result = exam_service.end_exam(exam_id)
                        
                        print(f"🏁 [EXAM COMPLETED] Exam {exam_id} finished with final result: {final_result.get('total_score', 0)}/{final_result.get('max_score', 0)}")
                        
                        await websocket.send_json({
                            "type": "exam_complete",
                            "message": "Exam completed successfully",
                            "data": final_result
                        })
                    except Exception as e:
                        await websocket.send_json({"error": str(e)})
                        print(f"Error ending exam {exam_id}: {e}")
                    break
                else:
                    # Send next question
                    await websocket.send_json({
                        "type": "question",
                        "content": result['next_question'],
                        "question_number": result['question_number'],
                        "mode": mode
                    })
            
            elif data.get("type") == "end_exam":
                # End exam and get results
                try:
                    final_result = exam_service.end_exam(exam_id)
                    
                    print(f"⏹️ [EXAM MANUALLY ENDED] Exam {exam_id} ended with result: {final_result.get('total_score', 0)}/{final_result.get('max_score', 0)}")
                    
                    await websocket.send_json({
                        "type": "exam_complete",
                        "message": "Exam completed successfully",
                        "data": final_result
                    })
                except Exception as e:
                    await websocket.send_json({"error": str(e)})
                    print(f"Error ending exam {exam_id}: {e}")
                break
    
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for exam {exam_id}")
    except Exception as e:
        await websocket.send_json({"error": str(e)})
    finally:
        await websocket.close()


@router.websocket("/ws/webcam/{exam_id}")
async def exam_webcam_websocket(websocket: WebSocket, exam_id: str):
    """WebSocket for real-time webcam exam interaction (webcam frames + optional voice answers)

    Behavior:
    - Sends the first question as TTS audio (voice-only) to the client
    - Accepts `video_frame` messages with base64-encoded JPEG/PNG frames and stores them
    - Accepts `voice_chunk` messages (same as voice endpoint) for student answers
    - Uses existing grok_exam_service for TTS and transcription
    """
    await websocket.accept()

    # Authenticate via query param token
    token = websocket.query_params.get("token")

    if not token:
        await websocket.send_json({"error": "Authentication required"})
        await websocket.close()
        return

    try:
        user = decode_token(token)
        if user["role"] != "student":
            await websocket.send_json({"error": "Only students can take exams"})
            await websocket.close()
            return
    except:
        await websocket.send_json({"error": "Invalid token"})
        await websocket.close()
        return

    # Verify exam exists
    if exam_id not in exam_service.active_exams:
        await websocket.send_json({"error": "Invalid exam ID"})
        await websocket.close()
        return

    exam = exam_service.active_exams[exam_id]
    exam['mode'] = 'webcam'
    student_id = exam['student_id']
    frame_count = 0
    audio_chunks = []

    try:
        # Send first question and its audio
        first_question = exam.get("first_question", "Please introduce yourself.")
        tts_result = await grok_exam_service.text_to_speech(first_question)

        await websocket.send_json({
            "type": "question",
            "content": first_question,
            "audio": tts_result.get("audio"),
            "mode": "webcam",
            "status": "listening"
        })

        while True:
            data = await websocket.receive_json()

            if data.get("type") == "video_frame":
                # Receive a webcam frame (base64-encoded image)
                img_b64 = data.get("image")
                fmt = data.get("format", "jpg")
                frame_count += 1
                try:
                    import base64, tempfile
                    img_bytes = base64.b64decode(img_b64)
                    fname = f"webcam_{exam_id}_{frame_count}.jpg"
                    # Use UPLOADS_DIR env var or /tmp/uploads on Linux
                    upload_dir = os.environ.get('UPLOADS_DIR')
                    if not upload_dir:
                        upload_dir = '/tmp/uploads' if os.name != 'nt' else os.path.join(os.getcwd(), 'uploads')
                    os.makedirs(upload_dir, exist_ok=True)
                    path = os.path.join(upload_dir, fname)
                    with open(path, "wb") as fh:
                        fh.write(img_bytes)
                    # Store frame path in exam data for later review
                    if 'frames' not in exam:
                        exam['frames'] = []
                    exam['frames'].append(path)

                    # Ack to client
                    await websocket.send_json({"type": "frame_ack", "frame": frame_count})
                except Exception as e:
                    await websocket.send_json({"type": "error", "message": f"Failed to save frame: {e}"})

            elif data.get("type") == "voice_chunk":
                # Voice chunk handling mirrors pure_voice logic
                audio_chunk = data.get("audio")
                is_final = data.get("is_final", False)
                silence_duration = data.get("silence_duration", 0)

                if audio_chunk:
                    audio_chunks.append(audio_chunk)

                if is_final and audio_chunks:
                    # Use the same approach as pure_voice: pick first valid chunk
                    import base64
                    binary_chunks = []
                    for chunk in audio_chunks:
                        try:
                            binary_chunks.append(base64.b64decode(chunk))
                        except Exception:
                            pass

                    if not binary_chunks:
                        await websocket.send_json({"type": "error", "message": "No valid audio frames"})
                        audio_chunks = []
                        continue

                    combined_binary = binary_chunks[0]
                    combined_audio = base64.b64encode(combined_binary).decode('utf-8')

                    transcription_result = await grok_exam_service.transcribe_audio_base64(combined_audio)

                    if transcription_result.get("status") == "success":
                        transcribed_text = transcription_result.get("text", "")
                        await websocket.send_json({"type": "transcription", "text": transcribed_text})

                        # Process the answer using existing exam flow
                        result = grok_exam_service.process_voice_answer(
                            student_id,
                            transcribed_text,
                            silence_duration
                        )

                        is_exam_complete = result.get('exam_complete', False)

                        if is_exam_complete:
                            final_result = exam_service.end_exam(exam_id)
                            farewell = "Your exam has been completed. Thank you."
                            farewell_audio = await grok_exam_service.text_to_speech(farewell)
                            await websocket.send_json({
                                "type": "exam_complete",
                                "audio": farewell_audio.get("audio"),
                                "message": "Exam completed",
                                "mode": "webcam"
                            })
                            break

                        # Send next question audio
                        next_question = result.get('next_question', 'Thank you.')
                        tts_result = await grok_exam_service.text_to_speech(next_question)
                        await websocket.send_json({
                            "type": "question",
                            "audio": tts_result.get("audio"),
                            "question_number": result.get('question_number'),
                            "mode": "webcam",
                            "status": "listening"
                        })

                    else:
                        await websocket.send_json({"type": "error", "message": f"Transcription failed: {transcription_result.get('message')}"})

                    audio_chunks = []

            elif data.get("type") == "end_exam":
                final_result = exam_service.end_exam(exam_id)
                farewell = "Your exam has been completed. Thank you."
                farewell_audio = await grok_exam_service.text_to_speech(farewell)
                await websocket.send_json({
                    "type": "exam_complete",
                    "audio": farewell_audio.get("audio"),
                    "message": "Exam completed",
                    "mode": "webcam"
                })
                break

    except WebSocketDisconnect:
        print(f"Webcam WebSocket disconnected for exam {exam_id}")
    except Exception as e:
        print(f"Webcam error: {str(e)}")
    finally:
        await websocket.close()


@router.websocket("/ws/voice/{exam_id}")
async def exam_voice_websocket(websocket: WebSocket, exam_id: str):
    """WebSocket for real-time voice exam interaction"""
    await websocket.accept()
    
    # Authenticate via query param token
    token = websocket.query_params.get("token")
    
    if not token:
        await websocket.send_json({"error": "Authentication required"})
        await websocket.close()
        return
    
    try:
        user = decode_token(token)
        if user["role"] != "student":
            await websocket.send_json({"error": "Only students can take exams"})
            await websocket.close()
            return
    except:
        await websocket.send_json({"error": "Invalid token"})
        await websocket.close()
        return
    
    # Verify exam exists
    if exam_id not in exam_service.active_exams:
        await websocket.send_json({"error": "Invalid exam ID"})
        await websocket.close()
        return
    
    exam = exam_service.active_exams[exam_id]
    exam['mode'] = 'voice'  # Set mode to voice
    
    student_id = exam['student_id']
    audio_chunks = []
    silence_counter = 0
    is_recording = False
    
    # Initialize exam conversation if not already done
    project_details = exam.get('project_details', {
        'title': 'Student Project',
        'description': 'A student project for evaluation',
        'technologies': ['Python', 'JavaScript'],
        'metrics': []
    })
    
    try:
        # Check if conversation already initialized (should be from exam_service.start_exam)
        if exam_id not in grok_exam_service.conversations:
            first_question = grok_exam_service.start_exam(exam_id, student_id, project_details)
            print(f"✅ Voice exam initialized for exam_id {exam_id}")
        else:
            print(f"✅ Voice exam conversation already initialized for exam_id {exam_id}")
            first_question = "Hello, welcome to the oral examination. Please start speaking."
    except Exception as e:
        print(f"❌ Error initializing exam conversation: {e}")
        await websocket.send_json({"error": f"Error starting exam: {str(e)}"})
        await websocket.close()
        return
    
    try:
        # Generate speech for the first question
        tts_result = await grok_exam_service.text_to_speech(first_question)
        
        await websocket.send_json({
            "type": "question",
            "content": first_question,
            "audio": tts_result.get("audio"),
            "mode": "voice",
            "status": "listening"  # Tell client to start listening
        })
        
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "voice_chunk":
                # Receive audio chunk (base64)
                audio_chunk = data.get("audio")
                is_final = data.get("is_final", False)
                silence_duration = data.get("silence_duration", 0)
                
                if audio_chunk:
                    audio_chunks.append(audio_chunk)
                
                # Check if pause detected (is_final indicates student paused)
                if is_final and audio_chunks:
                    # Combine all chunks and process
                    combined_audio = ''.join(audio_chunks)
                    
                    try:
                        # Transcribe combined audio
                        transcription_result = await grok_exam_service.transcribe_audio_base64(combined_audio)
                        
                        if transcription_result.get("status") == "success":
                            transcribed_text = transcription_result.get("text", "")
                            
                            # Show transcription
                            await websocket.send_json({
                                "type": "transcription",
                                "transcribed_text": transcribed_text,
                                "confidence": transcription_result.get("confidence", 0.95)
                            })
                            
                            # Process the answer using exam_id to get correct conversation
                            is_pdf_exam = exam.get('is_pdf_exam', False)
                            pdf_instruction = exam.get('pdf_metadata', {}).get('instruction') if is_pdf_exam else None
                            
                            result = grok_exam_service.process_voice_answer(
                                exam_id,
                                transcribed_text,
                                silence_duration,
                                is_pdf_exam=is_pdf_exam,
                                pdf_instruction=pdf_instruction
                            )
                            
                            # Check if exam is complete
                            is_exam_complete = result.get('exam_complete', False)
                            
                            if is_exam_complete:
                                # End exam and get results
                                final_result = exam_service.end_exam(exam_id)
                                
                                await websocket.send_json({
                                    "type": "exam_complete",
                                    "message": "Exam completed successfully",
                                    "data": final_result
                                })
                                break
                            
                            next_question = result.get('next_question', 'Thank you.')
                            
                            # Generate speech for next question
                            tts_result = await grok_exam_service.text_to_speech(next_question)
                            
                            # Send next question with audio
                            await websocket.send_json({
                                "type": "question",
                                "content": next_question,
                                "audio": tts_result.get("audio"),
                                "question_number": result.get('question_number'),
                                "mode": "voice",
                                "status": "listening"  # Tell client to keep listening
                            })
                            
                            # Reset audio chunks for next answer
                            audio_chunks = []
                        else:
                            await websocket.send_json({
                                "type": "error",
                                "message": f"Transcription failed: {transcription_result.get('message')}"
                            })
                            audio_chunks = []
                    
                    except Exception as e:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Voice processing error: {str(e)}"
                        })
                        audio_chunks = []
            
            elif data.get("type") == "end_exam":
                # End exam and get results
                final_result = exam_service.end_exam(exam_id)
                
                await websocket.send_json({
                    "type": "exam_complete",
                    "message": "Exam completed successfully",
                    "data": final_result
                })
                break
    
    except WebSocketDisconnect:
        print(f"Voice WebSocket disconnected for exam {exam_id}")
    except Exception as e:
        await websocket.send_json({"error": str(e)})
    finally:
        await websocket.close()

@router.websocket("/ws/pure_voice/{exam_id}")
async def exam_pure_voice_websocket(websocket: WebSocket, exam_id: str):
    """WebSocket for pure voice exam (no text display, auto-advance on 3-5s pause)"""
    await websocket.accept()
    
    # Authenticate via query param token
    token = websocket.query_params.get("token")
    
    if not token:
        await websocket.send_json({"error": "Authentication required"})
        await websocket.close()
        return
    
    try:
        user = decode_token(token)
        if user["role"] != "student":
            await websocket.send_json({"error": "Only students can take exams"})
            await websocket.close()
            return
    except:
        await websocket.send_json({"error": "Invalid token"})
        await websocket.close()
        return
    
    # Verify exam exists - BUT if not, try to create it from token
    print(f"\n🎤 [PURE_VOICE] WebSocket connection attempt")
    print(f"🎤 [PURE_VOICE] Exam ID: {exam_id}")
    print(f"🎤 [PURE_VOICE] Active exams: {list(exam_service.active_exams.keys())}")
    
    if exam_id not in exam_service.active_exams:
        print(f"⚠️  [PURE_VOICE] Exam {exam_id} not found!")
        print(f"🎤 [PURE_VOICE] FALLBACK: Creating exam from user token...")
        
        # Fallback: Extract student_id from exam_id or create new exam
        # exam_id format is "exam_{student_id}_{timestamp}"
        parts = exam_id.split('_')
        if len(parts) >= 2:
            student_id = parts[1]
            print(f"✅ [PURE_VOICE] Extracted student_id from exam_id: {student_id}")
        else:
            student_id = user['sub'].split('@')[0]  # Use email prefix as student_id
            print(f"✅ [PURE_VOICE] Using student_id from token: {student_id}")
        
        # Check if student has profile
        student = exam_service.students.get(student_id)
        if not student:
            print(f"❌ [PURE_VOICE] Student {student_id} has no profile")
            await websocket.send_json({"error": "Student profile not found. Please complete your profile first."})
            await websocket.close()
            return
        
        # Initialize exam data
        print(f"✅ [PURE_VOICE] Found student: {student['name']}")
        exam_data = {
            "exam_id": exam_id,
            "student_id": student_id,
            "start_time": datetime.now(IST),
            "status": "in_progress",
            "responses": [],
            "cheat_indicators": [],
            "is_pdf_exam": False
        }
        exam_service.active_exams[exam_id] = exam_data
        
        # Initialize Grok conversation
        print(f"✅ [PURE_VOICE] Initializing Grok conversation...")
        first_question = grok_exam_service.start_exam(
            student_id,
            student['project_details']
        )
        print(f"✅ [PURE_VOICE] Grok initialized, first question ready")
        
        exam = exam_data
    else:
        exam = exam_service.active_exams[exam_id]
        student_id = exam['student_id']
        # Get first question from grok
        if student_id not in grok_exam_service.conversations:
            print(f"⚠️  [PURE_VOICE] Student {student_id} conversation not initialized, initializing now...")
            student = exam_service.students.get(student_id)
            if student:
                first_question = grok_exam_service.start_exam(
                    student_id,
                    student['project_details']
                )
            else:
                first_question = "Hello! Please introduce yourself and your project."
        else:
            first_question = "Hello! Let's begin the exam."
    
    exam['mode'] = 'pure_voice'  # Set mode to pure voice
    print(f"✅ [PURE_VOICE] Exam found, student_id: {student_id}")
    print(f"✅ [PURE_VOICE] Grok conversations: {list(grok_exam_service.conversations.keys())}")
    print(f"✅ [PURE_VOICE] Student in conversations: {student_id in grok_exam_service.conversations}")
    audio_chunks = []
    silence_counter = 0
    is_recording = False
    
    try:
        # Send first question and its audio (VOICE ONLY - no text)
        # Use the first_question we just created in the fallback, or get from exam
        if 'first_question' not in locals():
            first_question = exam.get("first_question", "Please introduce yourself.")
        
        print(f"\n🎤 [PURE_VOICE] Starting exam for student: {student_id}")
        print(f"🎤 [PURE_VOICE] First question: {first_question}")
        
        # Generate speech for the first question
        tts_result = await grok_exam_service.text_to_speech(first_question)
        
        print(f"\n🎤 [PURE_VOICE] TTS Result status: {tts_result.get('status')}")
        audio_data = tts_result.get("audio")
        
        if audio_data:
            print(f"🎤 [PURE_VOICE] Audio size: {len(audio_data)} characters")
            print(f"🎤 [PURE_VOICE] Audio first 50 chars: {audio_data[:50]}...")
        else:
            print(f"❌ [PURE_VOICE] NO AUDIO DATA!")
            if tts_result.get('message'):
                print(f"❌ [PURE_VOICE] Error: {tts_result.get('message')}")
        
        # Pure voice: Send only audio, no text
        message = {
            "type": "question",
            "audio": audio_data,
            "mode": "pure_voice",
            "status": "listening"
        }
        
        print(f"\n📤 [PURE_VOICE] Message keys: {list(message.keys())}")
        print(f"📤 [PURE_VOICE] Sending question message...")
        
        await websocket.send_json(message)
        
        print(f"✅ [PURE_VOICE] Message sent successfully!\n")
        
        while True:
            data = await websocket.receive_json()
            
            print(f"\n🎤 [PURE_VOICE] Received message type: {data.get('type')}")
            print(f"🎤 [PURE_VOICE] Message keys: {data.keys()}")
            
            if data.get("type") == "voice_chunk":
                # Receive audio chunk (base64)
                audio_chunk = data.get("audio")
                is_final = data.get("is_final", False)
                silence_duration = data.get("silence_duration", 0)
                mode = data.get("mode", "pure_voice")
                
                print(f"\n🎤 [PURE_VOICE] Voice chunk received:")
                print(f"   - Audio size: {len(audio_chunk) if audio_chunk else 0} chars")
                print(f"   - Is final: {is_final}")
                print(f"   - Total chunks accumulated: {len(audio_chunks) + (1 if audio_chunk else 0)}")
                
                if audio_chunk:
                    audio_chunks.append(audio_chunk)
                    if is_final:
                        print(f"   ⏸️  FINAL FLAG RECEIVED - Processing {len(audio_chunks)} chunks")
                
                # Check if pause detected (3-5 seconds)
                # is_final indicates student paused for required duration
                if is_final and audio_chunks:
                    print(f"🎤 [PURE_VOICE] FINAL AUDIO FLAG SET - Processing {len(audio_chunks)} chunks")
                    
                    # IMPORTANT: WebM chunks from browser are individual files
                    # We need to combine them properly or use the first valid one
                    # Each 500ms chunk is a complete WebM file, so concatenating breaks them
                    
                    import base64
                    
                    # Try to find a valid chunk or combine them
                    # For now, let's try each chunk individually to see which is valid
                    print(f"🎤 Attempting to process {len(audio_chunks)} audio chunks")
                    
                    combined_audio = None
                    
                    # Strategy: Combine by decoding binary and re-encoding
                    # BUT only keep complete audio frames, not headers
                    binary_chunks = []
                    for i, chunk in enumerate(audio_chunks):
                        try:
                            binary = base64.b64decode(chunk)
                            binary_chunks.append(binary)
                            print(f"🎤 Chunk {i}: {len(chunk)} chars base64 -> {len(binary)} bytes, header: {binary[:4].hex()}")
                        except Exception as e:
                            print(f"❌ Failed to decode chunk {i}: {e}")
                    
                    if binary_chunks:
                        # Take only the first valid chunk
                        # (it contains all audio from first 500ms onwards recorded by MediaRecorder)
                        combined_binary = binary_chunks[0]
                        
                        # If multiple chunks, also try adding audio data from subsequent chunks
                        # by skipping their WebM headers
                        if len(binary_chunks) > 1:
                            print(f"🎤 Multiple chunks detected, using first chunk: {len(combined_binary)} bytes")
                        
                        combined_audio = base64.b64encode(combined_binary).decode('utf-8')
                        print(f"🎤 Final audio to transcribe: {len(combined_audio)} chars base64, binary header: {combined_binary[:4].hex()}")
                    
                    try:
                        if combined_audio:
                            # Transcribe combined audio (silent processing)
                            print(f"🎤 [PURE_VOICE] Transcribing {len(combined_audio)} chars of base64 audio...")
                            transcription_result = await grok_exam_service.transcribe_audio_base64(combined_audio)
                        else:
                            print(f"❌ [PURE_VOICE] No valid audio to transcribe")
                            transcription_result = {"status": "error", "message": "No valid audio data", "text": ""}
                        
                        print(f"🎤 [PURE_VOICE] Transcription result: {transcription_result}")
                        
                        if transcription_result.get("status") == "success":
                            transcribed_text = transcription_result.get("text", "")
                            print(f"✅ [PURE_VOICE] Transcribed text: '{transcribed_text}'")
                            
                            # Only process if we have actual transcribed text
                            if transcribed_text and transcribed_text.strip():
                                print(f"✅ [PURE_VOICE] Processing answer: '{transcribed_text}'")
                                print(f"✅ [PURE_VOICE] Student ID: {student_id}")
                                print(f"✅ [PURE_VOICE] Exam ID: {exam_id}")
                                
                                # Send what was heard to frontend
                                await websocket.send_json({
                                    "type": "transcription",
                                    "text": transcribed_text,
                                    "message": f"You said: {transcribed_text}"
                                })
                                
                                # Process the answer (NO transcription display in pure voice)
                                result = grok_exam_service.process_voice_answer(
                                    student_id,
                                    transcribed_text,
                                    silence_duration
                                )
                                
                                next_question = result.get('next_question', 'Thank you.')
                                is_exam_complete = result.get('exam_complete', False)
                                
                                print(f"\n✅ [PURE_VOICE] Got next question!")
                                print(f"🎤 [PURE_VOICE] Next question: {next_question[:60]}...")
                                print(f"🎤 [PURE_VOICE] Exam complete: {is_exam_complete}")
                                
                                if is_exam_complete:
                                    # End exam
                                    print(f"\n🎉 [PURE_VOICE] EXAM COMPLETE!")
                                    final_result = exam_service.end_exam(exam_id)
                                    
                                    # Send completion with final audio
                                    farewell = "Your exam has been completed. Thank you for your time."
                                    farewell_audio = await grok_exam_service.text_to_speech(farewell)
                                    
                                    print(f"🎉 [PURE_VOICE] Sending exam complete message")
                                    await websocket.send_json({
                                        "type": "exam_complete",
                                        "audio": farewell_audio.get("audio"),
                                        "message": "Exam completed",
                                        "mode": "pure_voice"
                                    })
                                    break
                                else:
                                    # Generate speech for next question
                                    print(f"\n📢 [PURE_VOICE] Converting next question to speech...")
                                    tts_result = await grok_exam_service.text_to_speech(next_question)
                                    
                                    print(f"📢 [PURE_VOICE] TTS result status: {tts_result.get('status')}")
                                    print(f"📢 [PURE_VOICE] Audio size: {len(tts_result.get('audio', '')) if tts_result.get('audio') else 0} chars")
                                    
                                    # Send next question with ONLY audio (no text)
                                    print(f"📤 [PURE_VOICE] Sending next question to frontend...")
                                    await websocket.send_json({
                                        "type": "question",
                                        "audio": tts_result.get("audio"),
                                        "question_number": result.get('question_number'),
                                        "mode": "pure_voice",
                                        "status": "listening"
                                    })
                                    print(f"✅ [PURE_VOICE] Next question sent!")
                                
                                # Reset audio chunks for next answer
                                audio_chunks = []
                                print(f"🔄 [PURE_VOICE] Reset audio_chunks, waiting for next speech...")
                            else:
                                # Empty transcription - just reset and continue listening
                                print(f"❌ [PURE_VOICE] Empty transcription: '{transcribed_text}'")
                                audio_chunks = []
                        else:
                            # Silent error - just wait for next input
                            print(f"❌ [PURE_VOICE] Transcription failed: {transcription_result}")
                            audio_chunks = []
                    
                    except Exception as e:
                        # Silent error handling - continue listening
                        print(f"❌ [PURE_VOICE] Exception during transcription: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        audio_chunks = []
            
            elif data.get("type") == "end_exam":
                # Manual exam end
                final_result = exam_service.end_exam(exam_id)
                
                farewell = "Your exam has been completed. Thank you."
                farewell_audio = await grok_exam_service.text_to_speech(farewell)
                
                await websocket.send_json({
                    "type": "exam_complete",
                    "audio": farewell_audio.get("audio"),
                    "message": "Exam completed",
                    "mode": "pure_voice"
                })
                break
    
    except WebSocketDisconnect:
        print(f"Pure voice WebSocket disconnected for exam {exam_id}")
    except Exception as e:
        print(f"Pure voice error: {str(e)}")
    finally:
        await websocket.close()