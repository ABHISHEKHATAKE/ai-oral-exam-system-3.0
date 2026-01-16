#!/usr/bin/env python3
"""Quick test to verify gTTS works"""

import asyncio
from gtts import gTTS
import io
import base64

text = "Hello, welcome to the oral examination. Could you please introduce yourself briefly?"

print(f"Testing gTTS with text: {text}")
print("-" * 60)

try:
    # Create TTS
    print("Creating gTTS object...")
    tts = gTTS(text=text, lang='en', slow=True)
    
    # Write to buffer
    print("Writing to buffer...")
    audio_buffer = io.BytesIO()
    tts.write_to_fp(audio_buffer)
    audio_buffer.seek(0)
    audio_data = audio_buffer.read()
    
    print(f"✅ Audio generated successfully!")
    print(f"   Audio size: {len(audio_data)} bytes")
    
    # Encode to base64
    audio_base64 = base64.b64encode(audio_data).decode('utf-8')
    print(f"   Base64 size: {len(audio_base64)} characters")
    print(f"   Base64 first 100 chars: {audio_base64[:100]}...")
    
    # Save to file for testing
    with open('test_gtts_output.mp3', 'wb') as f:
        f.write(audio_data)
    print(f"✅ Test audio saved to: test_gtts_output.mp3")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
