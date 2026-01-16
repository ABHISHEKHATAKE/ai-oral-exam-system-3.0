"""
Voice processing service for oral exams
Handles speech-to-text and audio processing
"""
import librosa
import soundfile as sf
import numpy as np
from typing import Optional, Dict, Tuple, List
import io
import base64
import json

class VoiceService:
    """Service for processing voice inputs and converting to text"""
    
    def __init__(self):
        self.sample_rate = 16000
        # Silence detection thresholds
        self.silence_threshold = 0.02  # RMS threshold for silence
        self.silence_duration = 1.5  # seconds of silence to trigger processing
        
    def detect_silence(self, audio: np.ndarray, sr: int, threshold: float = 0.02, min_duration: float = 1.5) -> Tuple[bool, float]:
        """
        Detect if audio contains significant silence
        Returns (is_silent, duration_of_silence)
        """
        # Calculate RMS energy
        rms = librosa.feature.rms(y=audio)[0]
        
        # Normalize RMS values
        rms_normalized = rms / (np.max(rms) + 1e-10)
        
        # Find frames below threshold (silence)
        silent_frames = rms_normalized < threshold
        
        # Convert frames to duration
        frame_length = len(audio) / len(rms)
        silent_duration = np.sum(silent_frames) * (frame_length / sr)
        
        return silent_duration >= min_duration, silent_duration
    
    def split_by_silence(self, audio: np.ndarray, sr: int) -> List[np.ndarray]:
        """
        Split audio into speech segments separated by silence
        """
        # Calculate RMS energy for each frame
        frame_length = 512
        hop_length = 160
        
        rms = librosa.feature.rms(y=audio, frame_length=frame_length, hop_length=hop_length)[0]
        rms_normalized = rms / (np.max(rms) + 1e-10)
        
        # Identify silence frames
        threshold = 0.1
        silent_frames = rms_normalized < threshold
        
        # Find edges (transitions between silence and speech)
        edges = np.diff(silent_frames.astype(int))
        speech_starts = np.where(edges == -1)[0] * hop_length
        speech_ends = np.where(edges == 1)[0] * hop_length
        
        # Ensure proper pairing
        if len(speech_starts) > len(speech_ends):
            speech_ends = np.append(speech_ends, len(audio))
        
        # Extract speech segments
        segments = []
        for start, end in zip(speech_starts, speech_ends):
            segment = audio[start:end]
            if len(segment) > 0:
                segments.append(segment)
        
        return segments

    def detect_adaptive_pause(self, audio: np.ndarray, sr: int, min_pause: float = 3.0, max_pause: float = 5.0) -> Tuple[bool, float]:
        """
        Detect adaptive pause (3-5 seconds) based on speech patterns
        Used for pure voice exam mode auto-advance
        
        Args:
            audio: Audio data
            sr: Sample rate
            min_pause: Minimum pause duration (default 3.0 seconds)
            max_pause: Maximum pause duration (default 5.0 seconds)
            
        Returns:
            (is_pause_detected, pause_duration)
        """
        try:
            # Calculate RMS energy
            rms = librosa.feature.rms(y=audio)[0]
            rms_normalized = rms / (np.max(rms) + 1e-10)
            
            # Silence threshold
            silence_threshold = 0.1
            
            # Find silence frames
            silent_frames = rms_normalized < silence_threshold
            
            # Convert frames to time
            frame_length = len(audio) / len(rms)
            frame_duration = frame_length / sr
            
            # Find longest silence period
            silence_segments = []
            current_silence_start = None
            
            for i, is_silent in enumerate(silent_frames):
                if is_silent:
                    if current_silence_start is None:
                        current_silence_start = i
                else:
                    if current_silence_start is not None:
                        silence_duration = (i - current_silence_start) * frame_duration
                        silence_segments.append(silence_duration)
                        current_silence_start = None
            
            # Check last segment
            if current_silence_start is not None:
                silence_duration = (len(silent_frames) - current_silence_start) * frame_duration
                silence_segments.append(silence_duration)
            
            if not silence_segments:
                return False, 0.0
            
            max_silence = max(silence_segments)
            
            # Check if pause is within 3-5 second range
            is_pause_detected = min_pause <= max_silence <= max_pause
            
            return is_pause_detected, max_silence
            
        except Exception as e:
            return False, 0.0

        
    def process_audio_base64(self, audio_data: str) -> Dict:
        """
        Process audio data from base64-encoded WebAudio
        Returns text transcription
        """
        try:
            # Decode base64 audio
            audio_bytes = base64.b64decode(audio_data)
            
            # Load audio from bytes
            audio, sr = librosa.load(io.BytesIO(audio_bytes), sr=self.sample_rate)
            
            # Normalize audio
            audio = self._normalize_audio(audio)
            
            # Extract features for voice analysis
            features = self._extract_features(audio, sr)
            
            # For now, we'll prepare audio for Groq transcription
            # The actual transcription will be done by Groq's speech-to-text
            audio_buffer = self._prepare_audio_for_transcription(audio, sr)
            
            return {
                "status": "success",
                "audio_buffer": audio_buffer,
                "sample_rate": sr,
                "duration": len(audio) / sr,
                "features": features
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    def process_audio_blob(self, audio_blob: bytes) -> Dict:
        """
        Process audio blob from WebRTC recording
        """
        try:
            # Load audio from bytes
            audio, sr = librosa.load(io.BytesIO(audio_blob), sr=self.sample_rate)
            
            # Normalize
            audio = self._normalize_audio(audio)
            
            # Extract features
            features = self._extract_features(audio, sr)
            
            return {
                "status": "success",
                "audio_data": audio,
                "sample_rate": sr,
                "duration": len(audio) / sr,
                "features": features
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    def _normalize_audio(self, audio: np.ndarray) -> np.ndarray:
        """Normalize audio to [-1, 1] range"""
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            audio = audio / max_val
        return audio
    
    def _extract_features(self, audio: np.ndarray, sr: int) -> Dict:
        """
        Extract audio features for analysis
        """
        try:
            # Extract MFCCs (Mel-Frequency Cepstral Coefficients)
            mfcc = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13)
            
            # Extract spectral features
            spectral_centroid = librosa.feature.spectral_centroid(y=audio, sr=sr)
            spectral_rolloff = librosa.feature.spectral_rolloff(y=audio, sr=sr)
            
            # Energy
            S = librosa.feature.melspectrogram(y=audio, sr=sr)
            energy = np.mean(S, axis=0)
            
            # Zero crossing rate
            zcr = librosa.feature.zero_crossing_rate(audio)
            
            # RMS energy
            rms = librosa.feature.rms(y=audio)
            
            return {
                "mfcc_mean": float(np.mean(mfcc)),
                "mfcc_std": float(np.std(mfcc)),
                "spectral_centroid_mean": float(np.mean(spectral_centroid)),
                "spectral_rolloff_mean": float(np.mean(spectral_rolloff)),
                "energy_mean": float(np.mean(energy)),
                "zcr_mean": float(np.mean(zcr)),
                "rms_mean": float(np.mean(rms)),
                "duration": len(audio) / sr
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _prepare_audio_for_transcription(self, audio: np.ndarray, sr: int) -> str:
        """
        Prepare audio for transcription by Groq
        Converts to base64-encoded WAV format
        """
        try:
            # Convert to WAV bytes
            wav_buffer = io.BytesIO()
            sf.write(wav_buffer, audio, sr, format='WAV')
            wav_buffer.seek(0)
            
            # Encode to base64
            encoded = base64.b64encode(wav_buffer.read()).decode('utf-8')
            return encoded
        except Exception as e:
            return None
    
    def validate_audio_quality(self, features: Dict) -> Tuple[bool, str]:
        """
        Validate audio quality
        Returns (is_valid, message)
        """
        if features.get("error"):
            return False, "Could not extract audio features"
        
        duration = features.get("duration", 0)
        
        if duration < 0.5:
            return False, "Audio too short (minimum 0.5 seconds)"
        
        if duration > 300:  # 5 minutes max
            return False, "Audio too long (maximum 5 minutes)"
        
        rms_mean = features.get("rms_mean", 0)
        if rms_mean < 0.01:
            return False, "Audio level too low. Please speak louder"
        
        return True, "Audio quality acceptable"


# Create singleton instance
voice_service = VoiceService()
