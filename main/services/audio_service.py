"""
AudioService: Encapsulates audio recording, speech recognition (Whisper), and TTS (ElevenLabs).

Provides clean interface for:
- Recording audio from microphone
- Transcribing audio files with Whisper
- Text-to-speech playback with ElevenLabs
"""
from __future__ import annotations

from typing import Optional
import tempfile
import os
import logging
import sys
from shutil import which

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write, read as wav_read
from dotenv import load_dotenv

from ..constants import (
    AUDIO_SAMPLE_RATE,
    DEFAULT_RECORD_DURATION_SEC,
)

load_dotenv()

logger = logging.getLogger(__name__)


class AudioService:
    """Service for audio operations: recording, recognition, TTS."""

    def __init__(self):
        self._whisper_model = None
        self._eleven_client = None

    def _get_whisper_model(self, model_name: str = "small"):
        """Lazy-load Whisper model (singleton pattern)."""
        if self._whisper_model is None:
            import whisper
            self._whisper_model = whisper.load_model(model_name)
        return self._whisper_model

    def _get_elevenlabs_client(self):
        """Lazy-load ElevenLabs client."""
        if self._eleven_client is None:
            from elevenlabs.client import ElevenLabs
            api_key = os.getenv("ELEVENLABS_API_KEY")
            self._eleven_client = ElevenLabs(api_key=api_key)
        return self._eleven_client

    def record(self, duration: int = DEFAULT_RECORD_DURATION_SEC, samplerate: int = AUDIO_SAMPLE_RATE) -> str:
        """
        Record mono audio from default input device to a temp WAV file.
        
        Args:
            duration: Recording duration in seconds
            samplerate: Sample rate (default 16000 Hz)
            
        Returns:
            Path to temporary WAV file
        """
        recording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='int16')
        sd.wait()
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        write(temp_file.name, samplerate, recording)
        return temp_file.name

    def recognize(self, filename: str, language: str = "uk", model_name: str = "small") -> str:
        """
        Transcribe a WAV file using Whisper.
        
        Robust to stereo/mono, integer/float dtypes, and resampling.
        Falls back to passing filename directly if buffer decode fails.
        
        Args:
            filename: Path to WAV file
            language: Language code (default "uk" for Ukrainian)
            model_name: Whisper model size (default "small")
            
        Returns:
            Recognized text (trimmed)
        """
        model = self._get_whisper_model(model_name)
        ffmpeg_available = which("ffmpeg") is not None
        try:
            fs, data = wav_read(filename)
            if hasattr(data, 'ndim') and data.ndim > 1:
                data = data.mean(axis=1)
            if np.issubdtype(data.dtype, np.integer):
                max_val = float(np.iinfo(data.dtype).max)
                audio = (data.astype(np.float32) / max_val)
            else:
                audio = data.astype(np.float32)
            if fs != AUDIO_SAMPLE_RATE:
                try:
                    from scipy.signal import resample_poly
                    # Resample from original fs to target AUDIO_SAMPLE_RATE
                    audio = resample_poly(audio, AUDIO_SAMPLE_RATE, fs).astype(np.float32)
                except Exception as res_err:
                    logger.warning("Resample failed (%s); continuing with original rate %s", res_err, fs)
            result = model.transcribe(audio, language=language)
        except Exception as first_err:
            logger.warning("Direct buffer transcription failed (%s). Fallback to filename (ffmpeg=%s)", first_err, ffmpeg_available)
            if not ffmpeg_available:
                logger.error("ffmpeg not found in PATH; install from https://ffmpeg.org/download.html to enable filename transcription.")
                return ""  # Graceful degrade
            try:
                result = model.transcribe(filename, language=language)
            except Exception as second_err:
                logger.exception("Filename transcription failed: %s", second_err)
                return ""
        return (result.get("text") or "").strip()

    def play_tts(
        self,
        text: str,
        voice_id: str = "9Sj8ugvpK1DmcAXyvi3a",
        model_id: str = "eleven_multilingual_v2"
    ) -> None:
        """
        Convert text to speech and play it using ElevenLabs.
        
        Safe to call on headless servers (no-op on failure).
        
        Args:
            text: Text to convert to speech
            voice_id: ElevenLabs voice ID
            model_id: ElevenLabs model ID
        """
        try:
            client = self._get_elevenlabs_client()
            audio_stream = client.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id=model_id,
                output_format="pcm_16000",
            )
            pcm_bytes = b''.join(
                chunk if isinstance(chunk, (bytes, bytearray)) else bytes(chunk)
                for chunk in audio_stream
            )
            samples = np.frombuffer(pcm_bytes, dtype=np.int16)
            sd.play(samples, samplerate=AUDIO_SAMPLE_RATE)
            sd.wait()
        except Exception as exc:
            logger.warning("TTS playback failed: %s", exc)
            return
