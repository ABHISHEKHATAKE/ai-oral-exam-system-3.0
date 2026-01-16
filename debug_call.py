import sys, os, asyncio
sys.path.insert(0, '.')
from app.services.grok_service import GrokExamService

async def main():
    svc = GrokExamService()
    # pick an existing PDF
    pdf = os.path.join(os.getcwd(), 'uploads', 'e9a9067f-328d-4f28-969e-16ddc058709f_nerual_network.pdf')
    if not os.path.exists(pdf):
        print('PDF not found:', pdf)
        return
    try:
        questions = await svc.generate_pdf_questions(pdf, 'Ask deep conceptual questions about this PDF')
        print('Questions from Groq:')
        for q in questions:
            print('-', q)
    except Exception as e:
        print('Exception during generate_pdf_questions:', e)

if __name__ == '__main__':
    asyncio.run(main())
