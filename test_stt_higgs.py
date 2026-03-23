# test_stt_higgs.py
import requests
import numpy as np
import soundfile as sf
import time
from reachy_mini import ReachyMini

EIGENAI_KEY = "sk-84aa7639_60ad85189bf34ecf7f170d75fe938f3785ae660ffd9e3a3eb4ebad061fcb80f3"

def record(reachy, duration=5):
    chunks = []
    reachy.media.start_recording()
    end_time = time.time() + duration
    while time.time() < end_time:
        sample = reachy.media.get_audio_sample()
        if sample is not None:
            chunks.append(sample)
    reachy.media.stop_recording()
    sr = reachy.media.get_input_audio_samplerate()
    audio = np.concatenate(chunks, axis=0)
    sf.write("/tmp/stt_input.wav", audio, sr)
    return "/tmp/stt_input.wav"

def transcribe(audio_path):
    with open(audio_path, "rb") as f:
        response = requests.post(
            "https://api-web.eigenai.com/api/v1/generate",
            headers={"Authorization": f"Bearer {EIGENAI_KEY}"},
            files={
                "model": (None, "higgs_asr_3"),
                "file": f,
                "language": (None, "English")
            }
        )
    print(f"ASR status: {response.status_code}")
    print(f"ASR response: {response.text}")
    if response.status_code == 200:
        data = response.json()
        return data.get("text") or data.get("transcription") or str(data)
    return None

with ReachyMini(connection_mode="localhost_only") as reachy:
    print("🎙️ Say something (5s)...")
    path = record(reachy, 5)
    print("📝 Transcribing with Higgs ASR 3...")
    text = transcribe(path)
    print(f"✅ You said: {text}")