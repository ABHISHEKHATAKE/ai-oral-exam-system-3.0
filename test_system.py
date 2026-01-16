import sys
sys.path.insert(0, '.')

print('🧪 TESTING EXAM SYSTEM COMPONENTS')
print('=' * 50)

# Test 1: Imports
print('\n1. Testing imports...')
try:
    from app.services.grok_service import grok_exam_service
    from app.services.exam_service import ExamService
    from app.api.routes.exams import router
    print('✅ All imports successful')
except Exception as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)

# Test 2: Service initialization
print('\n2. Testing service initialization...')
try:
    exam_svc = ExamService()
    print('✅ ExamService initialized')
except Exception as e:
    print(f'❌ ExamService error: {e}')
    sys.exit(1)

# Test 3: Question generation
print('\n3. Testing question generation...')
pdf_content = '''Neural networks are computing systems inspired by biological neural networks. They consist of interconnected nodes called neurons that process information. The network learns through training data to make predictions.'''

try:
    questions = grok_exam_service.generate_exam_questions('test', None, pdf_content, 2)
    print(f'✅ Generated {len(questions)} questions')
    for i, q in enumerate(questions, 1):
        print(f'   {i}. {q["question"]}')
except Exception as e:
    print(f'❌ Question generation error: {str(e)[:100]}...')
    print('   (This is expected if GROQ_API_KEY is invalid)')

# Test 4: Student registration and exam service methods
print('\n4. Testing student registration and exam service methods...')
try:
    # Register a test student
    student_data = {
        'student_id': 'test_student',
        'name': 'Test Student',
        'email': 'test@example.com'
    }
    exam_svc.register_student(student_data)
    print('✅ Student registered successfully')

    # Test PDF exam creation
    exam_data = {
        'pdf_path': 'test.pdf',
        'instruction': 'Test neural networks',
        'exam_name': 'Neural Networks Test'
    }
    result = exam_svc.start_exam('test_student', exam_data)
    print('✅ Exam started successfully')
    print(f'   Questions: {len(result.get("questions", []))}')

    # Test answer processing
    if result.get('questions'):
        exam_id = result['exam_id']
        answer = "Neural networks are computing systems that mimic biological brains."
        process_result = exam_svc.process_answer(exam_id, answer, 10.5)
        print('✅ Answer processed successfully')
        print(f'   Score: {process_result.get("score", "N/A")}')

        # Test exam completion
        end_result = exam_svc.end_exam(exam_id)
        print('✅ Exam completed successfully')
        print(f'   Final score: {end_result.get("total_score", "N/A")}/{end_result.get("max_score", "N/A")}')

except Exception as e:
    print(f'❌ Exam service error: {e}')
    import traceback
    traceback.print_exc()

print('\n' + '=' * 50)
print('🎯 TESTING COMPLETE')
print('Note: API errors are expected if GROQ_API_KEY is invalid')