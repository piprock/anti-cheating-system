"""
Audio utilities: microphone capture, speech recognition (Whisper), and TTS playback (ElevenLabs).

- Provides single-load Whisper model accessor
- Handles WAV recording at FS=16000
- Robustly decodes WAV buffers and resamples when needed
"""
from __future__ import annotations

from typing import Optional
import tempfile
import os

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write, read as wav_read
from django.conf import settings

from dotenv import load_dotenv

load_dotenv()

FS: int = 16000
DURATION_DEFAULT: int = 5

_whisper_model = None
_eleven_client = None


def get_whisper_model(model_name: str = "small"):
    global _whisper_model
    if _whisper_model is None:
        import whisper  # lazy import to speed cold paths
        _whisper_model = whisper.load_model(model_name)
    return _whisper_model


def _get_elevenlabs_client():
    global _eleven_client
    if _eleven_client is None:
        from elevenlabs.client import ElevenLabs
        api_key = os.getenv("ELEVENLABS_API_KEY")
        _eleven_client = ElevenLabs(api_key=api_key)
    return _eleven_client


def record_audio(duration: int = DURATION_DEFAULT, samplerate: int = FS) -> str:
    """Record mono audio from default input device to a temp WAV file and return its path."""
    recording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='int16')
    sd.wait()
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    write(temp_file.name, samplerate, recording)
    return temp_file.name


def recognize_speech(filename: str, language: str = "uk", model_name: str = "small") -> str:
    """Transcribe a WAV file using Whisper; robust to stereo/int dtype/resample.

    Returns the recognized text (trimmed). Falls back to passing filename directly if buffer decode fails.
    """
    model = get_whisper_model(model_name)
    try:
        fs, data = wav_read(filename)
        if hasattr(data, 'ndim') and data.ndim > 1:
            data = data.mean(axis=1)
        if np.issubdtype(data.dtype, np.integer):
            max_val = float(np.iinfo(data.dtype).max)
            audio = (data.astype(np.float32) / max_val)
        else:
            audio = data.astype(np.float32)
        if fs != FS:
            try:
                from scipy.signal import resample_poly
                audio = resample_poly(audio, FS, fs).astype(np.float32)
            except Exception:
                # If resample fails, let Whisper handle filename directly
                return model.transcribe(filename, language=language)["text"].strip()
        result = model.transcribe(audio, language=language)
    except Exception:
        result = model.transcribe(filename, language=language)
    return (result.get("text") or "").strip()


def speak(text: str, voice_id: str = "9Sj8ugvpK1DmcAXyvi3a", model_id: str = "eleven_multilingual_v2") -> None:
    """TTS via ElevenLabs; plays back with sounddevice. Safe to call on headless servers (no-op on failure)."""
    try:
        client = _get_elevenlabs_client()
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
        sd.play(samples, samplerate=FS)
        sd.wait()
    except Exception:
        # On servers without audio devices, ignore playback errors
        return
