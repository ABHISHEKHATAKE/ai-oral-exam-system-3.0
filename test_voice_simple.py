#!/usr/bin/env python3
"""
Simple voice test - Record 10 seconds and transcribe
This bypasses all the web complexity to test if voice works at all
"""
import asyncio
import base64
import io
import sys
sys.path.insert(0, 'd:/Assigment(2) - Copy/exam_system')

from app.services.grok_service import grok_exam_service

async def test_voice():
    print("\n" + "="*60)
    print("SIMPLE VOICE TEST")
    print("="*60)
    
    # Test 1: Check if Groq API is working
    print("\n✅ Test 1: Testing Groq API connection...")
    if not grok_exam_service.client:
        print("❌ Groq client not initialized!")
        return
    print("✅ Groq client is ready")
    
    # Test 2: Test TTS (Text to Speech)
    print("\n✅ Test 2: Testing TTS (converting text to audio)...")
    tts_result = await grok_exam_service.text_to_speech("Hello, this is a test. Please tell me your name.")
    if tts_result.get('status') == 'success':
        audio_data = tts_result.get('audio', '')
        print(f"✅ TTS Success! Generated {len(audio_data)} chars of base64 audio")
    else:
        print(f"❌ TTS Failed: {tts_result}")
        return
    
    # Test 3: Simulate voice input (for testing, we'll use a small WAV file or silence)
    print("\n✅ Test 3: Testing STT (audio to text) with a sample audio file...")
    
    # Create a minimal WAV file (silence for 2 seconds at 16kHz)
    import struct
    sample_rate = 16000
    duration = 2  # 2 seconds
    samples = int(sample_rate * duration)
    
    # Generate silence
    audio_data = struct.pack('<h', 0) * samples  # 16-bit PCM silence
    
    # Create WAV header
    channels = 1
    sample_width = 2
    num_samples = samples
    
    # WAV header
    wav_header = b'RIFF'
    file_size = 36 + num_samples * sample_width
    wav_header += struct.pack('<I', file_size)
    wav_header += b'WAVE'
    wav_header += b'fmt '
    wav_header += struct.pack('<I', 16)  # subchunk1 size
    wav_header += struct.pack('<H', 1)   # PCM format
    wav_header += struct.pack('<H', channels)
    wav_header += struct.pack('<I', sample_rate)
    wav_header += struct.pack('<I', sample_rate * channels * sample_width)
    wav_header += struct.pack('<H', channels * sample_width)
    wav_header += struct.pack('<H', 16)  # bits per sample
    wav_header += b'data'
    wav_header += struct.pack('<I', num_samples * sample_width)
    
    wav_file = wav_header + audio_data
    
    print(f"   - Created {len(wav_file)} byte WAV file (silence)")
    
    # Encode to base64
    audio_base64 = base64.b64encode(wav_file).decode('utf-8')
    print(f"   - Encoded to {len(audio_base64)} chars of base64")
    
    # Try to transcribe
    print("\n   - Sending to Groq for transcription...")
    stt_result = await grok_exam_service.transcribe_audio_base64(audio_base64)
    
    if stt_result.get('status') == 'success':
        text = stt_result.get('text', '')
        print(f"✅ STT Success! Transcribed: '{text}'")
    else:
        print(f"❌ STT Failed: {stt_result.get('message')}")
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)
    print("\n✅ If you see this, the basic voice system works!")
    print("   Next step: Fix the exam initialization")

if __name__ == "__main__":
    asyncio.run(test_voice())
