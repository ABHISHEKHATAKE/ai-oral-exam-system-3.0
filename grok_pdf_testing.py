import os, re
from dotenv import load_dotenv
import pdfplumber
from groq import Groq

# Load API key
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

pdf_path = "nerual_network.pdf"

# Read PDF text
all_text = ""
with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        if text:
            all_text += text + "\n"

instruction = input("Enter instruction (chapter range or topic): ")

relevant_text = ""

# Case 1: Chapter range (e.g., chapter 1 to chapter 3)
match = re.search(r"chapter\s*(\d+)\s*to\s*chapter\s*(\d+)", instruction.lower())
if match:
    start_ch, end_ch = match.groups()
    start_tag = f"Chapter {start_ch}"
    end_tag = f"Chapter {int(end_ch)+1}"

    s = all_text.find(start_tag)
    e = all_text.find(end_tag)
    if s != -1:
        relevant_text = all_text[s:e] if e != -1 else all_text[s:s+8000]

# Case 2: Topic number (e.g., 3.2.4)
elif re.search(r"\d+\.\d+(\.\d+)?", instruction):
    topic = re.search(r"\d+\.\d+(\.\d+)?", instruction).group()
    s = all_text.find(topic)
    if s != -1:
        relevant_text = all_text[s:s+8000]

# Fallback: first chunk
if not relevant_text:
    relevant_text = all_text[:8000]

# Trim to avoid token overflow
relevant_text = relevant_text[:6000]

prompt = f"""
You are a university professor conducting an oral (viva) examination.

Rules:
- Ask questions directly to the student.
- Do NOT say "author says" or "according to the text".
- Ask conceptual and technical viva questions.
- Number questions as Q1, Q2, ...
- Mention chapter or topic in brackets.

Teacher Instruction: {instruction}

Relevant Book Content:
{relevant_text}

Generate exactly 5 oral exam questions in this format:

Q1. [Chapter/Topic X] Question...
Q2. [Chapter/Topic X] Question...
Q3. [Chapter/Topic X] Question...
Q4. [Chapter/Topic X] Question...
Q5. [Chapter/Topic X] Question...
"""

response = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.7,
    max_tokens=400
)

print("\nAI Generated Viva Questions:\n")
print(response.choices[0].message.content)
