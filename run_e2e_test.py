from app.services.exam_service import exam_service

# Register test student
student = {
    'student_id': 'student1',
    'name': 'Test Student',
    'email': 'student1@example.com',
    'project_title': 'Neural Net Project',
    'project_description': 'A project about neural networks',
    'technologies': ['Python', 'TensorFlow'],
    'metrics': []
}
exam_service.register_student(student)

# Store PDF exam metadata (pointing to a non-existent file to force fallback)
pdf_path = 'uploads/nonexistent_sample.pdf'
exam_id = exam_service.store_pdf_exam_metadata(
    student_id='student1',
    pdf_path=pdf_path,
    pdf_filename='nonexistent_sample.pdf',
    instruction='Ask deep conceptual questions about neural networks',
    exam_name='Neural Networks PDF Exam'
)
print('Stored PDF exam id:', exam_id)

# Start the exam (should use fallback PDF content and generate questions from it)
result = exam_service.start_exam('student1', {'type': 'pdf', 'exam_id': exam_id, 'exam_name': 'Neural Networks PDF Exam'})
print('\nStarted exam result:')
print(result)

# Show generated questions stored in active_exams
active = exam_service.active_exams.get(result['exam_id'])
print('\nFirst question:')
print(active['questions'][0]['question'])

# Submit an answer for the first question
proc = exam_service.process_answer(result['exam_id'], 'This is my answer about neural networks.', 12.5)
print('\nAfter submitting answer, process_answer returned:')
print(proc)

# End exam and print results
final = exam_service.end_exam(result['exam_id'])
print('\nFinal exam results:')
print(final)
