# ============================================================================
# COMPLETE EXAM SYSTEM TEST - AUTOMATED FLOW
# ============================================================================
# This script tests the ENTIRE exam flow:
# 1. Instructor creates account and schedules exam
# 2. Student creates account and profile
# 3. Student takes exam via WebSocket
# 4. Instructor views results
# ============================================================================

import requests
import asyncio
import websockets
import json
from datetime import datetime, timedelta, timezone
import sys
import random
import string

# Configuration
BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"
IST = timezone(timedelta(hours=5, minutes=30))

# ============================================================================
# PART 1: INSTRUCTOR SETUP
# ============================================================================

def instructor_signup():
    """Step 1: Create instructor account"""
    print("\n" + "="*60)
    print("📝 STEP 1: Creating Instructor Account")
    print("="*60)
    
    response = requests.post(f"{BASE_URL}/api/auth/signup", json={
        "username": "professor@university.edu",
        "password": "InstructorPass123",
        "role": "instructor"
    })
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.json()

def instructor_login():
    """Step 2: Instructor login"""
    print("\n" + "="*60)
    print("🔑 STEP 2: Instructor Login")
    print("="*60)
    
    response = requests.post(f"{BASE_URL}/api/auth/token", data={
        "username": "professor@university.edu",
        "password": "InstructorPass123"
    })
    
    token = response.json()["access_token"]
    print(f"✅ Instructor Token: {token[:50]}...")
    return token

# ============================================================================
# PART 2: STUDENT SETUP
# ============================================================================

def student_signup():
    """Step 3: Create student account"""
    print("\n" + "="*60)
    print("📝 STEP 3: Creating Student Account")
    print("="*60)
    
    response = requests.post(f"{BASE_URL}/api/auth/signup", json={
        "username": "rahul@student.edu",
        "password": "StudentPass456",
        "role": "student"
    })
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.json()

def student_login():
    """Step 4: Student login"""
    print("\n" + "="*60)
    print("🔑 STEP 4: Student Login")
    print("="*60)
    
    response = requests.post(f"{BASE_URL}/api/auth/token", data={
        "username": "rahul@student.edu",
        "password": "StudentPass456"
    })
    
    token = response.json()["access_token"]
    print(f"✅ Student Token: {token[:50]}...")
    return token

def student_create_profile(student_token):
    """Step 5: Student creates profile"""
    print("\n" + "="*60)
    print("👤 STEP 5: Student Creates Profile")
    print("="*60)
    
    profile = {
        "student_id": "S12345",
        "name": "Rahul Sharma",
        "email": "rahul@student.edu",
        "project_title": "E-commerce Recommendation System",
        "project_description": "Built a machine learning-based recommendation engine using collaborative filtering and deep learning to suggest products based on user behavior",
        "technologies": ["Python", "TensorFlow", "FastAPI", "PostgreSQL", "Redis"],
        "metrics": ["Precision", "Recall", "Click-through Rate", "Conversion Rate"],
        "case_study": "Implemented for online fashion retailer with 1M+ products. Increased conversion by 25%."
    }
    
    response = requests.post(
        f"{BASE_URL}/api/student/profile",
        headers={"Authorization": f"Bearer {student_token}"},
        json=profile
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.json()

# ============================================================================
# PART 3: EXAM SCHEDULING
# ============================================================================

def instructor_view_students(instructor_token):
    """Step 6: Instructor views registered students"""
    print("\n" + "="*60)
    print("👥 STEP 6: Instructor Views Students")
    print("="*60)
    
    response = requests.get(
        f"{BASE_URL}/api/instructor/students",
        headers={"Authorization": f"Bearer {instructor_token}"}
    )
    
    students = response.json()
    print(f"Total Students: {students['total']}")
    for student in students['students']:
        print(f"  - {student['name']} ({student['student_id']}): {student['project_title']}")
    
    return students

def schedule_exam(instructor_token, student_id):
    """Step 7: Instructor schedules exam"""
    print("\n" + "="*60)
    print("📅 STEP 7: Scheduling Exam")
    print("="*60)
    
    # Schedule exam for 30 seconds from now
    now = datetime.now(IST)
    exam_start = now + timedelta(seconds=30)
    time_str = exam_start.strftime("%Y-%m-%d %I:%M %p")
    
    print(f"Current Time (IST): {now.strftime('%Y-%m-%d %I:%M:%S %p')}")
    print(f"Exam Start Time: {time_str}")
    
    response = requests.post(
        f"{BASE_URL}/api/instructor/schedule-exam",
        headers={"Authorization": f"Bearer {instructor_token}"},
        json={
            "student_id": student_id,
            "start_time": time_str,
            "duration_minutes": 10  # 10 minute window
        }
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return exam_start

# ============================================================================
# PART 4: STUDENT TAKES EXAM
# ============================================================================

def student_check_dashboard(student_token):
    """Step 8: Student checks dashboard"""
    print("\n" + "="*60)
    print("📊 STEP 8: Student Checks Dashboard")
    print("="*60)
    
    response = requests.get(
        f"{BASE_URL}/api/student/dashboard",
        headers={"Authorization": f"Bearer {student_token}"}
    )
    
    dashboard = response.json()
    print(f"Student Name: {dashboard['name']}")
    print(f"Profile Complete: {dashboard['profile_complete']}")
    print(f"Upcoming Exams: {len(dashboard['upcoming_exams'])}")
    
    if dashboard['upcoming_exams']:
        for exam in dashboard['upcoming_exams']:
            print(f"  - Exam at: {exam['start_time']}")
            print(f"    Duration: {exam['duration']} minutes")
    
    return dashboard

def start_exam(student_token, student_id):
    """Step 9: Student starts exam"""
    print("\n" + "="*60)
    print("🎓 STEP 9: Starting Exam")
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
        print(f"❌ Error: {response.json()}")
        return None

async def take_exam_via_websocket(exam_id, student_token):
    """Take exam with keyboard input - AI asks questions, you answer"""
    print("\n" + "="*70)
    print("💬 INTERACTIVE EXAM - Answer questions using your keyboard")
    print("="*70)
    print("\n📝 Instructions:")
    print("   - The AI will ask you questions about your project")
    print("   - Type your answers and press ENTER")
    print("   - Type 'END EXAM' to finish the exam early")
    print("   - Type 'SKIP' to skip a question")
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
                    print(f"\n🤖 AI Examiner: {data['content']}")
                    print("\n" + "─"*70)
                    
                    # Get answer from keyboard
                    print("\n✍️  Your Answer (press ENTER when done):")
                    print(">>> ", end="", flush=True)
                    
                    # Read answer from stdin
                    answer_text = await asyncio.get_event_loop().run_in_executor(
                        None, sys.stdin.readline
                    )
                    answer_text = answer_text.strip()
                    
                    # Check for special commands
                    if answer_text.upper() == "END EXAM":
                        print("\n🏁 Ending exam as requested...")
                        await websocket.send(json.dumps({"type": "end_exam"}))
                        break
                    
                    if answer_text.upper() == "SKIP":
                        answer_text = "I would prefer to skip this question."
                    
                    if not answer_text:
                        print("⚠️  Empty answer detected. Please provide an answer.")
                        answer_text = "I need more time to think about this."
                    
                    # Calculate response time (simulated based on answer length)
                    response_time = max(5, len(answer_text.split()) * 0.5)
                    
                    print(f"\n📤 Sending answer... (took {response_time:.1f} seconds)")
                    
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
                    print(f"   Total Questions Asked: {data['data']['total_questions']}")
                    print(f"   Total Answers Provided: {data['data']['total_answers']}")
                    print(f"   Suspicion Score: {data['data']['suspicion_score']}/10")
                    print(f"   Risk Level: {data['data']['risk_level']}")
                    
                    if data['data']['cheat_flags']:
                        print(f"\n⚠️  Flags: {', '.join(data['data']['cheat_flags'])}")
                    else:
                        print(f"\n✅ No irregularities detected")
                    
                    print("\n" + "="*70)
                    print("Thank you for taking the exam!")
                    print("Your instructor will review your responses and provide feedback.")
                    print("="*70 + "\n")
                    break
                
                elif data.get("error"):
                    print(f"\n❌ Error: {data['error']}")
                    break
    
    except Exception as e:
        print(f"\n❌ Connection Error: {e}")
        import traceback
        traceback.print_exc()

# ============================================================================
# PART 5: VIEW RESULTS
# ============================================================================

def instructor_view_dashboard(instructor_token):
    """Step 11: Instructor views dashboard"""
    print("\n" + "="*60)
    print("📊 STEP 11: Instructor Dashboard")
    print("="*60)
    
    response = requests.get(
        f"{BASE_URL}/api/instructor/dashboard",
        headers={"Authorization": f"Bearer {instructor_token}"}
    )
    
    dashboard = response.json()
    print(f"Total Students: {dashboard['total_students']}")
    print(f"Completed Exams: {len(dashboard['completed_exams'])}")
    print(f"Pending Grading: {dashboard['pending_grading']}")
    
    return dashboard

def view_exam_results(instructor_token, exam_id):
    """Step 12: Instructor views exam results"""
    print("\n" + "="*60)
    print("🎯 STEP 12: Viewing Exam Results")
    print("="*60)
    
    response = requests.get(
        f"{BASE_URL}/api/instructor/results/{exam_id}",
        headers={"Authorization": f"Bearer {instructor_token}"}
    )
    
    if response.status_code == 200:
        results = response.json()
        print(f"\n📊 EXAM RESULTS:")
        print(f"Student ID: {results['student_id']}")
        print(f"Total Score: {results['total_score']}/20")
        print(f"\nScore Breakdown:")
        for category, score in results['scores'].items():
            print(f"  - {category.replace('_', ' ').title()}: {score:.2f}")
        
        print(f"\n💪 Strengths:")
        for strength in results['strengths']:
            print(f"  ✓ {strength}")
        
        print(f"\n📈 Areas for Improvement:")
        for weakness in results['weaknesses']:
            print(f"  • {weakness}")
        
        print(f"\n📝 Feedback: {results['feedback']}")
        
        print(f"\n🔍 Cheat Detection:")
        print(f"  Risk Level: {results['risk_level']}")
        print(f"  Suspicion Score: {results['suspicion_score']}/10")
        if results['cheat_flags']:
            print(f"  Flags: {', '.join(results['cheat_flags'])}")
        else:
            print(f"  ✅ No cheating detected")
        
        return results
    else:
        print(f"❌ Error: {response.json()}")
        return None

# ============================================================================
# MAIN TEST FLOW
# ============================================================================

async def main():
    """Run complete exam flow"""
    print("\n" + "🎓"*30)
    print("AI ORAL EXAMINATION SYSTEM - COMPLETE TEST")
    print("🎓"*30)
    
    try:
        # PART 1: Instructor Setup
        instructor_signup()
        instructor_token = instructor_login()
        
        # PART 2: Student Setup
        student_signup()
        student_token = student_login()
        student_create_profile(student_token)
        
        # PART 3: Schedule Exam
        instructor_view_students(instructor_token)
        exam_start_time = schedule_exam(instructor_token, "S12345")
        
        # PART 4: Student prepares
        student_check_dashboard(student_token)
        
        # Wait until exam time
        now = datetime.now(IST)
        wait_seconds = (exam_start_time - now).total_seconds()
        
        if wait_seconds > 0:
            print(f"\n⏰ Waiting {int(wait_seconds)} seconds for exam to start...")
            await asyncio.sleep(wait_seconds + 5)  # Wait a bit extra to be safe
        
        # Start exam
        exam_info = start_exam(student_token, "S12345")
        
        if exam_info:
            exam_id = exam_info["exam_id"]
            
            # Take exam via WebSocket
            await take_exam_via_websocket(exam_id, student_token)
            
            # Wait a moment for processing
            await asyncio.sleep(2)
            
            # PART 5: View Results
            instructor_view_dashboard(instructor_token)
            view_exam_results(instructor_token, exam_id)
            
            print("\n" + "="*60)
            print("🎉 COMPLETE TEST FINISHED SUCCESSFULLY!")
            print("="*60)
        else:
            print("\n❌ Could not start exam. Check the error above.")
    
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("\n⚙️  Make sure your server is running on http://localhost:8000")
    print("⚙️  Run: python main.py\n")
    
    input("Press ENTER to start the test...")
    
    # Run the async main function
    asyncio.run(main())