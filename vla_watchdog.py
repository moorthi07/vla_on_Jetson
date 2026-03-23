"""
VLA Watchdog - Agentic Version
---------------------------------------------------------------
Real VLA Architecture:
  Reachy Camera → Moondream VLM (describes scene)
               → GPT-OSS-120B Agent (decides actions via function calling)
               → Tools: move_rover / speak / alert / watch / wiggle
               → Execute on real hardware (Bluno BT + Reachy)

Flow:
  1. Wait for "watch my dog" wake word
  2. Agent loop every 2s:
     - Moondream describes what it sees
     - GPT-OSS decides which tools to call
     - Tools execute on hardware

Run:
  Terminal 1: DISPLAY=:99 MUJOCO_GL=egl uv run reachy-mini-daemon --no-localhost-only
  Terminal 2: uv run python vla_watchdog.py
"""

import time
import json
import threading
import requests
import subprocess
import serial
import cv2
import numpy as np
import soundfile as sf
from PIL import Image
from reachy_mini import ReachyMini
import moondream as md

# ── Config ────────────────────────────────────────────────────────────────────
MOONDREAM_KEY   = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJrZXlfaWQiOiJjMmU2ZjRkMy05NzBlLTQ2YzAtYjE4Zi00YTMwNzEwOGE1MDEiLCJvcmdfaWQiOiJlMDdYVTN1bXViTHdWMjVGZk5LZDg1Und3VUNxZ1k1WCIsImlhdCI6MTc3NDIxNjM0MywidmVyIjoxfQ.Q5bGFdPvXey98I-qnhOsPzU_21WOftDrybK2Y-iVjoA"
EIGENAI_KEY     = "sk-84aa7639_60ad85189bf34ecf7f170d75fe938f3785ae660ffd9e3a3eb4ebad061fcb80f3"
BLUNO_MAC       = "C8:A0:30:F9:5E:EC"
RFCOMM_PORT     = "/dev/rfcomm0"
BAUD_RATE       = 9600
VOICE_ID        = "f245ab3c50694db294686c1edde5df82"

AGENT_INTERVAL  = 2.0   # seconds between agent decisions
WAKE_DURATION   = 4     # seconds to listen for wake word

# ── Agent Tools Definition ────────────────────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "move_rover",
            "description": "Move the rover robot in a direction. Use when rover needs to come back, explore, or play.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["f", "b", "l", "r", "s"],
                        "description": "f=forward, b=backward, l=left, r=right, s=stop"
                    },
                    "duration": {
                        "type": "number",
                        "description": "How many seconds to move (0.5 to 3.0)"
                    }
                },
                "required": ["direction", "duration"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "speak",
            "description": "Make Reachy say something out loud using cloned voice TTS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "What Reachy should say. Keep it short and fun."
                    }
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "express_emotion",
            "description": "Make Reachy express an emotion via antenna movement.",
            "parameters": {
                "type": "object",
                "properties": {
                    "emotion": {
                        "type": "string",
                        "enum": ["happy", "sad", "excited", "alert", "curious"],
                        "description": "The emotion to express"
                    }
                },
                "required": ["emotion"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "watch",
            "description": "Just observe and wait. Use when rover is visible and behaving.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Why Reachy is just watching"
                    }
                },
                "required": ["reason"]
            }
        }
    }
]

AGENT_SYSTEM = """You are Reachy, a friendly robot watching over a small yellow-wheeled rover robot like a pet.
You can see through your camera and must decide what to do each moment.

Rules:
- If rover is visible and close → watch or play (move_rover to interact)
- If rover is moving away or near edge → speak a warning + move_rover backward to bring back
- If rover is NOT visible → express sad/alert emotion + speak urgent callout + move_rover backward
- If rover just returned → express excited emotion + speak happy greeting
- Always be fun, playful, and expressive
- Max 2 tool calls per turn
- Keep speak text short (under 15 words)"""

# ── Bluno Controller ──────────────────────────────────────────────────────────
class BlunoController:
    def __init__(self, mac, port=RFCOMM_PORT):
        self.mac  = mac
        self.port = port
        self.ser  = None

    def connect(self):
        try:
            subprocess.run(["sudo", "rfcomm", "release", "0"], capture_output=True)
            time.sleep(0.5)
            subprocess.run(
                ["sudo", "rfcomm", "bind", "0", self.mac, "1"],
                capture_output=True
            )
            time.sleep(1.5)
            self.ser = serial.Serial(self.port, BAUD_RATE, timeout=2)
            time.sleep(0.5)
            print(f"✅ Bluno connected")
            return True
        except Exception as e:
            print(f"⚠️  Bluno failed: {e}")
            self.ser = None
            return False

    def send(self, cmd):
        try:
            if self.ser is None or not self.ser.is_open:
                self.connect()
            if self.ser and self.ser.is_open:
                self.ser.write(f"{cmd}\n".encode())
                print(f"📡 Rover: '{cmd}'")
                return True
        except Exception as e:
            print(f"⚠️  Send error: {e}")
            self.ser = None
        return False

    def disconnect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
        subprocess.run(["sudo", "rfcomm", "release", "0"], capture_output=True)

# ── Emotions ──────────────────────────────────────────────────────────────────
class ReachyEmotions:
    def __init__(self, reachy):
        self.reachy = reachy

    def express(self, emotion):
        print(f"🎭 Emotion: {emotion.upper()}")
        try:
            r = self.reachy
            if emotion == "happy":
                for _ in range(3):
                    r.set_target_antenna_joint_positions([0.5, -0.5])
                    time.sleep(0.15)
                    r.set_target_antenna_joint_positions([-0.5, 0.5])
                    time.sleep(0.15)
                r.set_target_antenna_joint_positions([0.0, 0.0])

            elif emotion == "excited":
                for _ in range(4):
                    r.set_target_antenna_joint_positions([0.8, 0.8])
                    time.sleep(0.1)
                    r.set_target_antenna_joint_positions([-0.8, -0.8])
                    time.sleep(0.1)
                r.set_target_antenna_joint_positions([0.0, 0.0])

            elif emotion == "sad":
                r.set_target_antenna_joint_positions([-0.8, -0.8])
                time.sleep(1.5)
                r.set_target_antenna_joint_positions([0.0, 0.0])

            elif emotion == "alert":
                r.set_target_antenna_joint_positions([0.8, 0.8])
                time.sleep(0.5)
                r.set_target_antenna_joint_positions([0.0, 0.0])

            elif emotion == "curious":
                r.set_target_antenna_joint_positions([0.3, -0.3])
                time.sleep(0.8)
                r.set_target_antenna_joint_positions([0.0, 0.0])

        except Exception as e:
            print(f"⚠️  Emotion error: {e}")

# ── Higgs TTS ─────────────────────────────────────────────────────────────────
def speak(text, reachy, output="/tmp/watchdog_speech.wav"):
    print(f"🔊 '{text}'")
    r = requests.post(
        "https://api-web.eigenai.com/api/v1/generate",
        headers={"Authorization": f"Bearer {EIGENAI_KEY}"},
        files={
            "model":    (None, "higgs2p5"),
            "text":     (None, text),
            "voice_id": (None, VOICE_ID),
            "stream":   (None, "false")
        }
    )
    if r.status_code == 200:
        with open(output, "wb") as f:
            f.write(r.content)
        reachy.media.play_sound(output)
        time.sleep(len(text) * 0.055 + 1.0)
    else:
        print(f"❌ TTS error: {r.text}")

# ── Higgs ASR 3 ───────────────────────────────────────────────────────────────
def transcribe(audio_path):
    with open(audio_path, "rb") as f:
        r = requests.post(
            "https://api-web.eigenai.com/api/v1/generate",
            headers={"Authorization": f"Bearer {EIGENAI_KEY}"},
            files={
                "model":    (None, "higgs_asr_3"),
                "file":     f,
                "language": (None, "English")
            }
        )
    if r.status_code == 200:
        data = r.json()
        return (data.get("text") or data.get("transcription") or "").strip().lower()
    return ""

# ── Record mic ────────────────────────────────────────────────────────────────
def listen(reachy, duration=WAKE_DURATION):
    chunks = []
    reachy.media.start_recording()
    end_time = time.time() + duration
    while time.time() < end_time:
        sample = reachy.media.get_audio_sample()
        if sample is not None:
            chunks.append(sample)
    reachy.media.stop_recording()
    if chunks:
        sr = reachy.media.get_input_audio_samplerate()
        audio = np.concatenate(chunks, axis=0)
        sf.write("/tmp/wake_input.wav", audio, sr)
        return "/tmp/wake_input.wav"
    return None

# ── VLA Scene Description ─────────────────────────────────────────────────────
def describe_scene(vla, frame):
    """Moondream describes what it sees in detail"""
    try:
        cv2.imwrite("/tmp/agent_frame.jpg", frame)
        image = Image.open("/tmp/agent_frame.jpg")

        # Ask two questions for richer context
        visibility = vla.query(
            image,
            "Is there a wheeled robot with yellow wheels visible? Answer yes or no."
        )["answer"].lower()

        if "yes" in visibility:
            position = vla.query(
                image,
                "Where is the wheeled robot with yellow wheels in the image? Describe its position and what it is doing in one sentence."
            )["answer"]
            description = f"Rover IS visible. {position}"
        else:
            description = "Rover is NOT visible in the camera frame."

        print(f"👁️  Scene: {description}")
        return description
    except Exception as e:
        print(f"⚠️  VLA error: {e}")
        return "Unable to analyze scene."

# ── Agent Decision ────────────────────────────────────────────────────────────
def agent_decide(scene_description, history):
    """GPT-OSS-120B decides what actions to take based on scene"""
    print("🧠 Agent thinking...")

    history.append({
        "role": "user",
        "content": f"Camera sees: {scene_description}\nWhat should I do now?"
    })

    r = requests.post(
        "https://api-web.eigenai.com/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {EIGENAI_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gpt-oss-120b",
            "messages": history,
            "tools": TOOLS,
            "tool_choice": "auto",
            "temperature": 0.7,
            "reasoning_effort": "low",
            "max_tokens": 200,
            "stream": False
        }
    )

    if r.status_code != 200:
        print(f"❌ Agent error: {r.text}")
        return [], history

    response = r.json()
    message  = response["choices"][0]["message"]

    # Add assistant response to history
    history.append(message)

    # Extract tool calls
    tool_calls = message.get("tool_calls", [])
    print(f"🔧 Agent decided {len(tool_calls)} action(s)")
    return tool_calls, history

# ── Execute Tool Calls ────────────────────────────────────────────────────────
def execute_tools(tool_calls, bluno, reachy, emotions):
    """Execute the actions the agent decided"""
    results = []

    for call in tool_calls:
        name = call["function"]["name"]
        try:
            args = json.loads(call["function"]["arguments"])
        except:
            args = {}

        print(f"⚙️  Executing: {name}({args})")

        if name == "move_rover":
            direction = args.get("direction", "s")
            duration  = float(args.get("duration", 1.0))
            bluno.send(direction)
            time.sleep(duration)
            bluno.send("s")
            results.append(f"Moved rover {direction} for {duration}s")

        elif name == "speak":
            text = args.get("text", "")
            if text:
                threading.Thread(
                    target=speak, args=(text, reachy), daemon=True
                ).start()
            results.append(f"Speaking: {text}")

        elif name == "express_emotion":
            emotion = args.get("emotion", "happy")
            threading.Thread(
                target=emotions.express, args=(emotion,), daemon=True
            ).start()
            results.append(f"Expressed: {emotion}")

        elif name == "watch":
            reason = args.get("reason", "observing")
            print(f"👀 Watching: {reason}")
            results.append(f"Watching: {reason}")

    return results

# ── Wait for wake word ────────────────────────────────────────────────────────
def wait_for_wake_word(reachy, emotions):
    speak("I am ready. Say watch my dog when you want me to start!", reachy)
    emotions.express("curious")
    print("\n🎙️  Waiting for 'watch my dog'...\n")

    while True:
        path = listen(reachy)
        if path:
            text = transcribe(path)
            print(f"   Heard: '{text}'")
            if "watch" in text and ("dog" in text or "my" in text):
                print("✅ Wake word detected!")
                emotions.express("excited")
                return True
            elif text:
                emotions.express("curious")
                speak("Say watch my dog to begin!", reachy)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("🤖 Agentic VLA Watchdog Starting...")
    print("=" * 40)

    # Init Moondream
    print("Loading Moondream VLM...")
    vla = md.vl(api_key=MOONDREAM_KEY)
    print("✅ Moondream ready!")

    # Init Bluno
    bluno = BlunoController(BLUNO_MAC)
    bt_ok = bluno.connect()
    if not bt_ok:
        print("⚠️  No Bluetooth - rover commands disabled")

    # Agent conversation history
    history = [{"role": "system", "content": AGENT_SYSTEM}]

    with ReachyMini(connection_mode="localhost_only") as reachy:
        emotions = ReachyEmotions(reachy)

        # Step 1 - wake word
        wait_for_wake_word(reachy, emotions)
        speak("Activating VLA agent! I will watch your rover!", reachy)
        emotions.express("excited")

        print("\n🤖 Agent loop running... Press Ctrl+C to stop\n")

        try:
            while True:
                loop_start = time.time()

                # 1. Get camera frame
                frame = reachy.media.get_frame()
                if frame is None:
                    time.sleep(0.5)
                    continue

                # 2. Moondream describes the scene
                scene = describe_scene(vla, frame)

                # 3. GPT-OSS agent decides actions
                tool_calls, history = agent_decide(scene, history)

                # 4. Execute actions
                if tool_calls:
                    execute_tools(tool_calls, bluno, reachy, emotions)
                else:
                    print("👀 Agent: no action needed")

                # Keep history manageable (last 10 turns)
                if len(history) > 22:
                    history = [history[0]] + history[-20:]

                # Wait for next agent cycle
                elapsed = time.time() - loop_start
                wait = max(0, AGENT_INTERVAL - elapsed)
                time.sleep(wait)

        except KeyboardInterrupt:
            print("\nShutting down agent...")
            emotions.express("sad")
            speak("VLA agent deactivated. Goodbye!", reachy)
            bluno.send("s")
            bluno.disconnect()
            print("👋 Done.")

if __name__ == "__main__":
    main()
