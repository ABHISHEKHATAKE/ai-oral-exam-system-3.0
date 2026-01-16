import os
from dotenv import load_dotenv
from groq import Groq

print('🔍 TESTING UPDATED GROQ API KEY')
print('=' * 50)

# Load environment variables
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Check API key
api_key = os.getenv('GROQ_API_KEY')
if not api_key:
    print('❌ No GROQ_API_KEY found in environment')
    exit(1)

print(f'✅ API Key loaded: {api_key[:10]}...{api_key[-10:]}')

# Initialize client
try:
    client = Groq(api_key=api_key)
    print('✅ Groq client initialized successfully')
except Exception as e:
    print(f'❌ Failed to initialize Groq client: {e}')
    exit(1)

# Test 1: Simple API call
print('\n🧪 Test 1: Simple API call...')
try:
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": "Hello! Please respond with exactly: 'API test successful!'"}],
        temperature=0.1,
        max_tokens=20
    )

    result = response.choices[0].message.content.strip()
    print('✅ API call successful!')
    print(f'📝 Response: {result}')

    if 'API test successful' in result.lower():
        print('🎉 API IS WORKING CORRECTLY!')
    else:
        print('⚠️ API responded but with unexpected content')

except Exception as e:
    print(f'❌ API call failed: {e}')
    if '401' in str(e):
        print('🔑 INVALID API KEY - Please get a new key from https://groq.com/')
    elif '429' in str(e):
        print('⏰ RATE LIMIT exceeded - Try again later')
    elif '500' in str(e):
        print('🛠️ SERVER ERROR on Groq side')
    else:
        print('❓ Unknown error')
    exit(1)

# Test 2: Exam question generation
print('\n🧪 Test 2: Exam question generation...')
try:
    test_content = """Neural networks are computing systems inspired by biological neural networks.
    They consist of interconnected nodes called neurons that process information.
    The network learns through training data to make predictions."""

    prompt = f"""
You are a professor conducting an oral exam.

Instruction: Test neural networks

Content:
{test_content}

Generate 2 deep viva questions.
Format:
Q1. ...
Q2. ...
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=200
    )

    questions = [q for q in response.choices[0].message.content.split("\n") if q.strip().startswith("Q")]
    print('✅ Question generation successful!')
    print(f'📝 Generated {len(questions)} questions:')
    for q in questions:
        print(f'   {q}')

except Exception as e:
    print(f'❌ Question generation failed: {e}')

# Test 3: Full system integration
print('\n🧪 Test 3: Full system integration...')
try:
    from app.services.grok_service import grok_exam_service

    questions = grok_exam_service.generate_exam_questions(
        exam_id='api_test',
        pdf_content=test_content,
        num_questions=2
    )

    print('✅ Full system integration successful!')
    print(f'📝 Generated {len(questions)} formatted questions:')
    for i, q in enumerate(questions, 1):
        print(f'   {i}. {q["question"]}')

except Exception as e:
    print(f'❌ System integration failed: {e}')

print('\n' + '=' * 50)
print('🏁 API TEST COMPLETE')
if 'API test successful' in result.lower():
    print('🎊 YOUR API KEY IS WORKING! The exam system is ready!')
else:
    print('⚠️ API key may have issues - check the results above')