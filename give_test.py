#!/usr/bin/env python3
"""
Simple Exam Test Script
-----------------------
Prerequisites:
1. Student account created
2. Student profile completed
3. Exam scheduled by instructor

This script only handles:
- Student login
- Start exam
- Take exam (interactive Q&A)
- View results
"""

import requests
import asyncio
import websockets
import json
import sys
from datetime import datetime, timedelta, timezone

# Configuration
BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"
IST = timezone(timedelta(hours=5, minutes=30))

# ============================================================================
# STUDENT LOGIN
# ============================================================================

def student_login(email, password):
    """Login as student"""
    print("\n" + "="*60)
    print("🔑 LOGGING IN")
    print("="*60)
    
    response = requests.post(f"{BASE_URL}/api/auth/token", data={
        "username": email,
        "password": password
    })
    
    if response.status_code == 200:
        token = response.json()["access_token"]
        print(f"✅ Login Successful!")
        print(f"Token: {token[:50]}...")
        return token
    else:
        print(f"❌ Login Failed: {response.json()}")
        return None

# ============================================================================
# START EXAM
# ============================================================================

def start_exam(student_token, student_id):
    """Start the scheduled exam"""
    print("\n" + "="*60)
    print("🎓 STARTING EXAM")
    print("="*60)
    
    response = requests.post(
        f"{BASE_URL}/api/exams/start",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"student_id": student_id}
    )
    
    if response.status_code == 200:
        exam_info = response.json()
        print(f"✅ Exam Started Successfully!")
        print(f"Exam ID: {exam_info['exam_id']}")
        print(f"Student: {exam_info['student_name']}")
        print(f"Status: {exam_info['status']}")
        return exam_info
    else:
        error = response.json()
        print(f"❌ Error: {error.get('detail', 'Unknown error')}")
        
        if "not started yet" in str(error):
            print("\n⏰ The exam hasn't started yet. Please wait until the scheduled time.")
        elif "time is over" in str(error):
            print("\n⏰ The exam window has closed. Please contact your instructor.")
        elif "not scheduled" in str(error):
            print("\n📅 No exam is scheduled for you. Please contact your instructor.")
            
        return None

# ============================================================================
# TAKE EXAM - INTERACTIVE
# ============================================================================

async def take_exam_interactive(exam_id, student_token):
    """Take exam with keyboard input"""
    print("\n" + "="*70)
    print("💬 INTERACTIVE EXAM - AI will ask you questions")
    print("="*70)
    print("\n📝 Instructions:")
    print("   - The AI will ask questions about your project")
    print("   - Type your answers and press ENTER")
    print("   - Type 'END EXAM' to finish early")
    print("   - Take your time and answer thoughtfully")
    print("\n" + "="*70 + "\n")
    
    uri = f"{WS_URL}/api/exams/ws/{exam_id}?token={student_token}&mode=text"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("🔗 Connected to exam server\n")
            
            question_count = 0
            
            while True:
                # Receive message from server
                message = await websocket.recv()
                data = json.loads(message)
                
                if data.get("type") == "question":
                    question_count += 1
                    print("\n" + "─"*70)
                    print(f"📝 Question {question_count}:")
                    print(f"\n🤖 AI: {data['content']}")
                    print("\n" + "─"*70)
                    
                    # Get answer from keyboard
                    print("\n✍️  Your Answer:")
                    print(">>> ", end="", flush=True)
                    
                    # Read answer from stdin
                    answer_text = await asyncio.get_event_loop().run_in_executor(
                        None, sys.stdin.readline
                    )
                    answer_text = answer_text.strip()
                    
                    # Check for special commands
                    if answer_text.upper() == "END EXAM":
                        print("\n🏁 Ending exam...")
                        await websocket.send(json.dumps({"type": "end_exam"}))
                        break
                    
                    if not answer_text:
                        print("⚠️  Empty answer. Using default response.")
                        answer_text = "I need more time to think about this question."
                    
                    # Calculate response time
                    response_time = max(5, len(answer_text.split()) * 0.5)
                    
                    print(f"📤 Sending answer... (response time: {response_time:.1f}s)")
                    
                    # Send answer to server
                    await websocket.send(json.dumps({
                        "type": "answer",
                        "mode": "text",
                        "content": answer_text,
                        "response_time": response_time
                    }))
                
                elif data.get("type") == "exam_complete":
                    print("\n" + "="*70)
                    print("✅ EXAM COMPLETED!")
                    print("="*70)
                    print(f"\n📊 Summary:")
                    print(f"   Questions: {data['data']['total_questions']}")
                    print(f"   Answers: {data['data'].get('total_answers', 0)}")
                    print(f"   Risk Level: {data['data']['risk_level']}")
                    
                    if data['data'].get('cheat_flags'):
                        print(f"\n⚠️  Flags: {', '.join(data['data']['cheat_flags'])}")
                    else:
                        print(f"\n✅ No issues detected")
                    
                    print("\n" + "="*70)
                    print("Your instructor will review and provide feedback.")
                    print("="*70 + "\n")
                    break
                
                elif data.get("error"):
                    print(f"\n❌ Error: {data['error']}")
                    break
    
    except websockets.exceptions.WebSocketException as e:
        print(f"\n❌ WebSocket Error: {e}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

# ============================================================================
# MAIN FUNCTION
# ============================================================================

async def main():
    """Main exam flow"""
    print("\n" + "🎓"*30)
    print("AI ORAL EXAMINATION - TAKE EXAM")
    print("🎓"*30)
    
    # Get student credentials
    print("\n📧 Enter your credentials:")
    email = input("Email: ").strip()
    password = input("Password: ").strip()
    student_id = input("Student ID: ").strip()
    
    # Login
    token = student_login(email, password)
    if not token:
        print("\n❌ Login failed. Exiting.")
        return
    
    # Start exam
    exam_info = start_exam(token, student_id)
    if not exam_info:
        print("\n❌ Could not start exam. Exiting.")
        return
    
    exam_id = exam_info["exam_id"]
    
    print("\n" + "="*70)
    print("⚠️  IMPORTANT:")
    print("   - Answer questions in your own words")
    print("   - Don't copy-paste from websites")
    print("   - Take time to think before answering")
    print("   - The AI will detect suspicious patterns")
    print("="*70)
    
    input("\nPress ENTER when ready to begin exam...")
    
    # Take exam
    await take_exam_interactive(exam_id, token)
    
    print("\n✅ Exam session completed!")
    print("You can now close this window.\n")

if __name__ == "__main__":
    print("\n⚙️  Prerequisites:")
    print("   1. Backend server running on http://localhost:8000")
    print("   2. Student account created")
    print("   3. Student profile completed")
    print("   4. Exam scheduled by instructor")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Exam interrupted by user.")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()