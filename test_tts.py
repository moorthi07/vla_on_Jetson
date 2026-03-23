"""
Step 2: Test TTS with your cloned voice_id.
Run upload_voice.py first to get the voice_id.
"""
import requests
import subprocess

API_KEY = "sk-84aa7639_60ad85189bf34ecf7f170d75fe938f3785ae660ffd9e3a3eb4ebad061fcb80f3"

def load_voice_id():
    try:
        with open("/tmp/voice_id.txt") as f:
            return f.read().strip()
    except FileNotFoundError:
        print("❌ No voice_id found. Run upload_voice.py first!")
        return None


def speak(text, output="/tmp/tts_test.wav"):
    voice_id = load_voice_id()
    if not voice_id:
        return

    print(f"Generating speech for: '{text}'")
    print(f"Using voice_id: {voice_id}")

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

    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        with open(output, "wb") as f:
            f.write(response.content)
        print(f"✅ Saved to {output}")
        subprocess.run(["paplay", output])
    else:
        print(f"❌ TTS failed: {response.text}")

if __name__ == "__main__":
    speak("Hello! I am Dr. Robo, your hilariously unqualified robot mental health doctor. How are you feeling today?")