import os
import sys
import numpy as np
import wave
import contextlib
from pathlib import Path

import pytest

from main.services import AudioService


class DummyWhisperModel:
    def __init__(self, text="hello world"):
        self.text = text
    def transcribe(self, audio, language="uk"):
        return {"text": self.text}

class DummyElevenStream(list):
    pass

@pytest.fixture
def audio_service():
    return AudioService()

@pytest.fixture(autouse=True)
def mock_sounddevice(monkeypatch):
    import types
    # mock sd.rec to return zeros
    sd = types.SimpleNamespace()
    def rec(n, samplerate=16000, channels=1, dtype='int16'):
        return np.zeros((n, channels), dtype=np.int16)
    def wait():
        return None
    def play(samples, samplerate=16000):
        # accept playback silently
        return None
    sd.rec = rec
    sd.wait = wait
    sd.play = play
    monkeypatch.setitem(globals(), 'sd', sd)
    monkeypatch.setitem(__import__('sounddevice').__dict__, 'rec', rec)
    monkeypatch.setitem(__import__('sounddevice').__dict__, 'wait', wait)
    monkeypatch.setitem(__import__('sounddevice').__dict__, 'play', play)

@pytest.fixture(autouse=True)
def mock_whisper(monkeypatch):
    import types
    dummy = DummyWhisperModel()
    def load_model(name):
        return dummy
    whisper_mod = types.SimpleNamespace(load_model=load_model)
    monkeypatch.setitem(sys.modules, 'whisper', whisper_mod)
    yield

@pytest.fixture(autouse=True)
def mock_elevenlabs(monkeypatch):
    class DummyClient:
        class text_to_speech:
            @staticmethod
            def convert(text, voice_id, model_id, output_format):
                return DummyElevenStream([b'\x00' * 1000])
    def dummy_elevenlabs(*args, **kwargs):
        return DummyClient()
    monkeypatch.setattr('elevenlabs.client.ElevenLabs', DummyClient, raising=False)

def test_record_creates_wav(audio_service, tmp_path):
    path = audio_service.record(duration=1)
    assert os.path.exists(path)
    with contextlib.closing(wave.open(path, 'rb')) as wf:
        assert wf.getframerate() == 16000
    os.unlink(path)

def test_recognize_uses_dummy_whisper(audio_service, tmp_path, monkeypatch):
    # create simple wav file
    import wave
    fname = tmp_path / 'sample.wav'
    with wave.open(str(fname), 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b'\x00' * 1600)
    text = audio_service.recognize(str(fname))
    assert 'hello' in text

def test_play_tts_no_exception(audio_service):
    # Should silently succeed even if environment headless
    audio_service.play_tts('Test speaking')

