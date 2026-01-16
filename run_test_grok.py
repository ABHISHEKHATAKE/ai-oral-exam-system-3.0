from app.services.grok_service import GrokExamService

svc = GrokExamService()
# Test with more substantial PDF content
pdf_content = """
Neural networks are computing systems inspired by biological neural networks that constitute animal brains.
Such systems learn to perform tasks by considering examples, generally without being programmed with task-specific rules.
A neural network is based on a collection of connected units or nodes called artificial neurons.
Each connection between artificial neurons can transmit a signal from one to another.
The artificial neuron that receives the signal can process it and then signal artificial neurons connected to it.

The architecture of neural networks consists of several layers:
1. Input layer: receives the initial data
2. Hidden layers: process the information through weighted connections
3. Output layer: produces the final result

Deep learning uses neural networks with multiple hidden layers, enabling more complex pattern recognition.
Backpropagation is the primary algorithm used to train neural networks by adjusting connection weights.
"""

questions = svc.generate_exam_questions('test', None, pdf_content, 5)
for i, q in enumerate(questions, 1):
    print(f"Q{i}: {q['question']}")
