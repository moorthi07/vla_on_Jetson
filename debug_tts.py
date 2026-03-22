# debug_tts.py
import requests

API_KEY = "sk-84aa7639_60ad85189bf34ecf7f170d75fe938f3785ae660ffd9e3a3eb4ebad061fcb80f3"

# Try 1 - simple short text
response = requests.post(
    "https://api-web.eigenai.com/api/v1/generate",
    headers={"Authorization": f"Bearer {API_KEY}"},
    data={
        "model": "higgs2p5",
        "text": "Hello I am Dr Robo",
        "voice_id": "f245ab3c50694db294686c1edde5df82",
        "stream": "false"
    }
)
print(f"Try 1 status: {response.status_code}")
print(f"Try 1 response: {response.text[:100]}")

# Try 2 - using files= like upload worked
response2 = requests.post(
    "https://api-web.eigenai.com/api/v1/generate",
    headers={"Authorization": f"Bearer {API_KEY}"},
    files={
        "model": (None, "higgs2p5"),
        "text": (None, "Hello I am Dr Robo"),
        "voice_id": (None, "f245ab3c50694db294686c1edde5df82"),
        "stream": (None, "false")
    }
)
print(f"Try 2 status: {response2.status_code}")
print(f"Try 2 response: {response2.text[:100]}")