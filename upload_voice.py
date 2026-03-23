"""
Step 1: Run this ONCE to upload your voice sample and get a voice_id.
The voice_id is saved to /tmp/voice_id.txt for reuse.
"""
import requests
import json

API_KEY = "sk-84aa7639_60ad85189bf34ecf7f170d75fe938f3785ae660ffd9e3a3eb4ebad061fcb80f3"
VOICE_SAMPLE = "/tmp/voice_sample_10s.wav"
VOICE_NAME = "ReachyVoice"

def upload_voice():
    print(f"Uploading voice sample: {VOICE_SAMPLE}")
    with open(VOICE_SAMPLE, "rb") as f:
      response = requests.post(
        "https://api-web.eigenai.com/api/v1/generate/upload",
        headers={"Authorization": f"Bearer {API_KEY}"},
        files={
            "voice_reference_file": open(VOICE_SAMPLE, "rb"),
        },
        data={
            "model": "higgs2p5",
            "voice_name": VOICE_NAME
        }
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")

    if response.status_code == 200:
        data = response.json()
        print(f"Full response: {json.dumps(data, indent=2)}")

        # Try common keys for voice_id
        voice_id = (
            data.get("voice_id") or
            data.get("id") or
            data.get("voiceId") or
            str(data)
        )

        # Save to file for reuse
        with open("/tmp/voice_id.txt", "w") as f:
            f.write(voice_id)
        print(f"\n✅ Voice ID saved: {voice_id}")
        print("Run mental_doctor.py next!")
        return voice_id
    else:
        print(f"❌ Upload failed: {response.text}")
        return None

if __name__ == "__main__":
    upload_voice()
