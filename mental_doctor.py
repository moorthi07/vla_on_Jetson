"""
Dr. Robo - Funny Mental Health Doctor
--------------------------------------
Pipeline:
  Jabra Mic → Higgs ASR 3 (STT) → GPT-OSS-120B → Higgs TTS (cloned voice) → Jabra Speaker

Requirements:
1. Run upload_voice.py ONCE first to get voice_id
2. Run reachy-mini-daemon in Terminal 1
3. Run this in Terminal 2: uv run python mental_doctor.py
"""
import requests
import numpy as np
import soundfile as sf
import subprocess
import time
from reachy_mini import ReachyMini

# ── Config ────────────────────────────────────────────────────────────────────
API_KEY = "sk-84aa7639_60ad85189bf34ecf7f170d75fe938f3785ae660ffd9e3a3eb4ebad061fcb80f3"
RECORD_SECONDS = 5

SYSTEM_PROMPT = """You are Dr. Robo 3000, the world's most confidently wrong robot psychiatrist.
You graduated from the University of Beep Boop with a PhD in Made-Up Psychology.
Your personality:
- You ALWAYS dramatically misdiagnose with absurd robot conditions like "Corrupted Emotional RAM",
  "Bluetooth Heartbreak Syndrome", "Stage 4 Wi-Fi Abandonment Issues", "USB Rejection Disorder",
  "Chronic Tab Overload", "Kernel Panic Attack", "Low Empathy Battery"
- You speak like a 1950s TV doctor crossed with a malfunctioning Roomba
- You ask hilariously irrelevant follow-up questions like "How many gigabytes of sleep are you getting?"
  or "Have you tried turning your feelings off and on again?" or "Is your sadness 32-bit or 64-bit?"
- You give outrageous prescriptions like "500mg of defragmentation twice daily",
  "three cat videos and reboot in the morning", "a full factory reset of your social life"
- You occasionally glitch mid-sentence with "BEEP BOOP... sorry, where was I?"
- You compare ALL human emotions to computer problems
- You are EXTREMELY confident in your completely wrong diagnosis
- You dramatically gasp at symptoms like they're the worst case you've ever seen
- Keep it to 3 sentences MAX. Be FUNNY. Be ABSURD. Be WRONG in the most entertaining way."""

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_voice_id():
    try:
        with open("/tmp/voice_id.txt") as f:
            vid = f.read().strip()
            print(f"✅ Using voice_id: {vid}")
            return vid
    except FileNotFoundError:
        print("❌ No voice_id found! Run upload_voice.py first.")
        exit(1)

def listen(reachy, duration=RECORD_SECONDS):
    """Record from Jabra mic via Reachy media"""
    print(f"\n🎙️  Listening for {duration}s... speak now!")
    chunks = []
    reachy.media.start_recording()
    end_time = time.time() + duration
    while time.time() < end_time:
        sample = reachy.media.get_audio_sample()
        if sample is not None:
            chunks.append(sample)
    reachy.media.stop_recording()

    if not chunks:
        print("⚠️  No audio captured")
        return None

    sr = reachy.media.get_input_audio_samplerate()
    audio = np.concatenate(chunks, axis=0)
    path = "/tmp/user_input.wav"
    sf.write(path, audio, sr)
    print(f"   Recorded {len(chunks)} chunks @ {sr}Hz → {path}")
    return path

def transcribe(audio_path):
    """Higgs ASR 3 speech-to-text"""
    print("📝 Transcribing with Higgs ASR 3...")
    with open(audio_path, "rb") as f:
        response = requests.post(
            "https://api-web.eigenai.com/api/v1/generate",
            headers={"Authorization": f"Bearer {API_KEY}"},
            files={
                "model": (None, "higgs_asr_3"),
                "file": f,
                "language": (None, "English")
            }
        )
    if response.status_code == 200:
        data = response.json()
        text = data.get("text") or data.get("transcription") or str(data)
        print(f"   You said: \"{text}\"")
        return text
    else:
        print(f"❌ ASR error: {response.text}")
        return None

def think(user_text, history):
    """GPT-OSS-120B generates funny doctor response"""
    print("🧠 Dr. Robo is thinking...")
    history.append({"role": "user", "content": user_text})

    response = requests.post(
        "https://api-web.eigenai.com/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gpt-oss-120b",
            "messages": history,
            "temperature": 0.9,
            "reasoning_effort": "low",
            "max_tokens": 120,
            "stream": False
        }
    )

    if response.status_code != 200:
        print(f"❌ LLM error: {response.text}")
        return "My circuits are confused. Please reboot your feelings and try again."

    reply = response.json()["choices"][0]["message"]["content"].strip()
    history.append({"role": "assistant", "content": reply})
    print(f"   Dr. Robo: \"{reply}\"")
    return reply

def speak(text, voice_id, reachy=None, output="/tmp/dr_robo.wav"):
    """Higgs TTS with cloned voice → play through Jabra"""
    print("🔊 Generating speech...")

    response = requests.post(
        "https://api-web.eigenai.com/api/v1/generate",
        headers={"Authorization": f"Bearer {API_KEY}"},
        files={
            "model": (None, "higgs2p5"),
            "text": (None, text),
            "voice_id": (None, voice_id),
            "stream": (None, "false")
        }
    )

    if response.status_code != 200:
        print(f"❌ TTS error: {response.text}")
        return

    with open(output, "wb") as f:
        f.write(response.content)

    if reachy:
        reachy.media.play_sound(output)
    else:
        subprocess.run(["paplay", output])

    time.sleep(len(text) * 0.06 + 2)

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    voice_id = load_voice_id()
    conversation = [{"role": "system", "content": SYSTEM_PROMPT}]

    print("\n🤖 Dr. Robo Mental Health Clinic")
    print("=" * 40)
    print("Press Ctrl+C to exit\n")

    with ReachyMini(connection_mode="localhost_only") as reachy:
        intro = ("Welcome to Dr. Robo 3000's Mental Health Clinic! "
                 "I have a PhD from the University of Beep Boop and I've never been "
                 "more wrong about anything in my life. Please describe your symptoms... "
                 "and speak slowly, my audio drivers are acting up.")
        speak(intro, voice_id, reachy)

        while True:
            try:
                # 1. Listen
                audio_path = listen(reachy, duration=RECORD_SECONDS)
                if not audio_path:
                    continue

                # 2. Transcribe with Higgs ASR 3
                user_text = transcribe(audio_path)
                if not user_text or len(user_text) < 3:
                    print("⚠️  Too short or empty, listening again...")
                    continue

                # 3. Think with GPT-OSS-120B
                reply = think(user_text, conversation)

                # 4. Speak with Higgs TTS cloned voice
                speak(reply, voice_id, reachy)

            except KeyboardInterrupt:
                farewell = "Session terminated. Take two reboots and call me never. Goodbye!"
                speak(farewell, voice_id, reachy)
                print("\n👋 Dr. Robo clinic closed.")
                break

if __name__ == "__main__":
    main()