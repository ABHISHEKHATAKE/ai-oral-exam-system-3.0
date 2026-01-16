import os
from groq import Groq
from dotenv import load_dotenv

# Load .env from exam_system folder (2 levels up)
load_dotenv("../../.env")

api_key = os.getenv("GROQ_API_KEY")

client = Groq(api_key="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")

print("🤖 Groq Chat Started (type 'exit' to stop)\n")

while True:
    user_input = input("You: ")
    
    if user_input.lower() == "exit":
        print("Chat ended.")
        break

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are a friendly assistant."},
            {"role": "user", "content": user_input}
        ],
        temperature=0.7,
        max_tokens=200
    )

    reply = response.choices[0].message.content
    print("Groq:", reply)
