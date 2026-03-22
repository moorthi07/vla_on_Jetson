"""
VLA Watchdog - Reachy Mini + Moondream + Higgs TTS + Bluno BT + Emotions
-------------------------------------------------------------------------
Flow:
  1. Reachy waits listening for "watch my dog"
  2. Once heard → Reachy gets excited, plays with rover
  3. Reachy watches rover via Moondream VLA
  4. Emotional reactions:
     - Rover visible   → happy antenna wiggle
     - Rover leaves    → sad droop + funny alert + sends rover back
     - Rover returns   → excited dance
     - Playing         → commentary + head tracking

Run:
  Terminal 1: DISPLAY=:99 MUJOCO_GL=egl uv run reachy-mini-daemon --no-localhost-only
  Terminal 2: uv run python vla_watchdog.py
"""

import time
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
VOICE_ID        = "f245ab3c50694db294686c1edde5df82"  # cloned voice

GONE_THRESHOLD  = 3.0   # seconds before alert
ALERT_COOLDOWN  = 8.0   # seconds between alerts
CHECK_INTERVAL  = 0.5   # seconds between camera checks
HAPPY_INTERVAL  = 10.0  # seconds between happy wiggles when rover visible

# ── Bluno Controller ──────────────────────────────────────────────────────────
class BlunoController:
    def __init__(self, mac, port=RFCOMM_PORT):
        self.mac  = mac
        self.port = port
        self.ser  = None

    def connect(self):
        try:
            subprocess.run(
                ["sudo", "rfcomm", "bind", "0", self.mac, "1"],
                capture_output=True
            )
            time.sleep(1)
            self.ser = serial.Serial(self.port, BAUD_RATE, timeout=2)
            print(f"✅ Bluno connected via {self.port}")
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

# ── Emotions via Reachy movements ─────────────────────────────────────────────
class ReachyEmotions:
    def __init__(self, reachy):
        self.reachy = reachy

    def happy_wiggle(self):
        """Fast antenna wiggle - excited/happy"""
        print("😄 Emotion: HAPPY WIGGLE")
        try:
            r = self.reachy
            for _ in range(3):
                r.set_target_antenna_joint_positions(
                    {"left_antenna": 30, "right_antenna": -30}
                )
                time.sleep(0.15)
                r.set_target_antenna_joint_positions(
                    {"left_antenna": -30, "right_antenna": 30}
                )
                time.sleep(0.15)
            r.set_target_antenna_joint_positions(
                {"left_antenna": 0, "right_antenna": 0}
            )
        except Exception as e:
            print(f"⚠️  Emotion error: {e}")

    def sad_droop(self):
        """Slow antenna droop - sad/worried"""
        print("😢 Emotion: SAD DROOP")
        try:
            r = self.reachy
            r.set_target_antenna_joint_positions(
                {"left_antenna": -45, "right_antenna": -45}
            )
            time.sleep(1.5)
        except Exception as e:
            print(f"⚠️  Emotion error: {e}")

    def excited_dance(self):
        """Head bob + antenna wiggle - very excited"""
        print("🎉 Emotion: EXCITED DANCE")
        try:
            r = self.reachy
            for _ in range(2):
                r.set_target_antenna_joint_positions(
                    {"left_antenna": 45, "right_antenna": 45}
                )
                time.sleep(0.2)
                r.set_target_antenna_joint_positions(
                    {"left_antenna": -45, "right_antenna": -45}
                )
                time.sleep(0.2)
            r.set_target_antenna_joint_positions(
                {"left_antenna": 0, "right_antenna": 0}
            )
        except Exception as e:
            print(f"⚠️  Emotion error: {e}")

    def curious_tilt(self):
        """Head tilt - curious/watching"""
        print("🤔 Emotion: CURIOUS TILT")
        try:
            r = self.reachy
            r.set_target_head_pose({"roll": 15, "pitch": -10, "yaw": 0})
            time.sleep(1.0)
            r.set_target_head_pose({"roll": 0, "pitch": 0, "yaw": 0})
        except Exception as e:
            print(f"⚠️  Emotion error: {e}")

    def alert_look(self):
        """Head snap up - alert/alarmed"""
        print("😱 Emotion: ALERT")
        try:
            r = self.reachy
            r.set_target_head_pose({"roll": 0, "pitch": -20, "yaw": 0})
            r.set_target_antenna_joint_positions(
                {"left_antenna": 45, "right_antenna": 45}
            )
            time.sleep(0.8)
            r.set_target_head_pose({"roll": 0, "pitch": 0, "yaw": 0})
        except Exception as e:
            print(f"⚠️  Emotion error: {e}")

    def track_rover(self, frame):
        """Move head to look toward rover position in frame"""
        try:
            h, w = frame.shape[:2]
            # Simple: check which third of screen rover is in
            # Moondream already told us it's visible, estimate center
            # For now do a gentle scan left-right
            r = self.reachy
            r.set_target_head_pose({"roll": 0, "pitch": 0, "yaw": -15})
            time.sleep(0.3)
            r.set_target_head_pose({"roll": 0, "pitch": 0, "yaw": 15})
            time.sleep(0.3)
            r.set_target_head_pose({"roll": 0, "pitch": 0, "yaw": 0})
        except Exception as e:
            print(f"⚠️  Track error: {e}")

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
        time.sleep(len(text) * 0.055 + 1.5)
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
def listen(reachy, duration=4):
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

# ── VLA Check ─────────────────────────────────────────────────────────────────
def is_rover_visible(vla, frame):
    try:
        cv2.imwrite("/tmp/watchdog_frame.jpg", frame)
        image = Image.open("/tmp/watchdog_frame.jpg")
        result = vla.query(
            image,
            "Is there a wheeled robot or vehicle with yellow wheels in this image? Answer yes or no."
        )["answer"].lower()
        visible = "yes" in result
        print(f"👁️  Visible: {visible} ({result[:50]})")
        return visible
    except Exception as e:
        print(f"⚠️  VLA error: {e}")
        return True

# ── Play with rover ───────────────────────────────────────────────────────────
PLAY_SEQUENCE = [
    ("f", "Go forward little guy!",   2.0),
    ("s", "",                          0.5),
    ("l", "Turn left!",                1.5),
    ("s", "",                          0.5),
    ("r", "Now turn right!",           1.5),
    ("s", "",                          0.5),
    ("b", "Come back to me!",          2.0),
    ("s", "",                          0.5),
    ("f", "One more time, go go go!",  1.5),
    ("s", "",                          0.3),
    ("l", "",                          0.8),
    ("s", "",                          0.3),
    ("b", "Come back home!",           1.5),
    ("s", "",                          0.5),
]

def play_with_rover(bluno, reachy, emotions):
    speak("Oh I love this rover! Let me play with it!", reachy)
    emotions.excited_dance()
    time.sleep(0.3)

    for cmd, phrase, duration in PLAY_SEQUENCE:
        if phrase:
            threading.Thread(
                target=speak, args=(phrase, reachy), daemon=True
            ).start()
        if cmd != "s":
            emotions.happy_wiggle()
        bluno.send(cmd)
        time.sleep(duration)

    bluno.send("s")
    emotions.curious_tilt()
    speak("Okay, playtime over. Now stay where I can see you!", reachy)

# ── Alert messages ────────────────────────────────────────────────────────────
ALERT_MESSAGES = [
    "Hey! Come back here, you little rover!",
    "Where do you think you are going? Get back in my sight!",
    "I can not see you anymore, please come back!",
    "My visual cortex has lost track of you, return immediately!",
    "You are triggering my separation anxiety protocols!",
    "I am calling the robot police if you do not come back right now!",
]
alert_index = 0

def get_alert():
    global alert_index
    msg = ALERT_MESSAGES[alert_index % len(ALERT_MESSAGES)]
    alert_index += 1
    return msg

# ── Wait for wake word ────────────────────────────────────────────────────────
def wait_for_wake_word(reachy, emotions):
    speak("I am ready. Say watch my dog when you want me to start!", reachy)
    emotions.curious_tilt()
    print("\n🎙️  Waiting for 'watch my dog'...\n")

    while True:
        path = listen(reachy, duration=4)
        if path:
            text = transcribe(path)
            print(f"   Heard: '{text}'")
            if "watch" in text and ("dog" in text or "my" in text):
                print("✅ Wake word detected!")
                emotions.excited_dance()
                return True
            elif text:
                emotions.curious_tilt()
                speak("I am still waiting. Say watch my dog to begin!", reachy)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("🤖 VLA Watchdog Starting...")
    print("=" * 40)

    print("Loading Moondream VLA...")
    vla = md.vl(api_key=MOONDREAM_KEY)
    print("✅ Moondream ready!")

    bluno = BlunoController(BLUNO_MAC)
    bt_ok = bluno.connect()
    if not bt_ok:
        print("⚠️  No Bluetooth - rover commands disabled")

    with ReachyMini(connection_mode="localhost_only") as reachy:
        emotions = ReachyEmotions(reachy)

        # Step 1 - wake word
        wait_for_wake_word(reachy, emotions)

        # Step 2 - play
        speak("Watch my dog? I am on it!", reachy)
        play_with_rover(bluno, reachy, emotions)

        # Step 3 - watch
        speak("Now I am watching. Do not go too far little rover!", reachy)
        emotions.curious_tilt()

        rover_last_seen  = time.time()
        last_alert       = 0
        last_happy       = 0
        rover_visible    = True

        print("\n👀 Watching rover... Press Ctrl+C to stop\n")

        try:
            while True:
                now   = time.time()
                frame = reachy.media.get_frame()

                if frame is None:
                    time.sleep(CHECK_INTERVAL)
                    continue

                visible = is_rover_visible(vla, frame)

                if visible:
                    rover_last_seen = now

                    # Rover just came back
                    if not rover_visible:
                        print("✅ Rover returned!")
                        def on_return():
                            emotions.excited_dance()
                            speak("You came back! Good dog! I missed you!", reachy)
                        threading.Thread(target=on_return, daemon=True).start()

                    rover_visible = True

                    # Periodic happy wiggle while rover is visible
                    if now - last_happy > HAPPY_INTERVAL:
                        last_happy = now
                        threading.Thread(
                            target=emotions.happy_wiggle, daemon=True
                        ).start()

                else:
                    gone_for = now - rover_last_seen
                    
                    # Just disappeared
                    if rover_visible:
                        emotions.alert_look()
                    
                    rover_visible = False
                    print(f"⚠️  Gone for {gone_for:.1f}s")

                    if gone_for > GONE_THRESHOLD and (now - last_alert) > ALERT_COOLDOWN:
                        last_alert = now
                        msg = get_alert()

                        def alert(m=msg):
                            emotions.sad_droop()
                            speak(m, reachy)
                            bluno.send("b")
                            time.sleep(1.5)
                            bluno.send("s")

                        threading.Thread(target=alert, daemon=True).start()

                time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\nShutting down...")
            emotions.sad_droop()
            speak("Watchdog deactivated. Goodbye!", reachy)
            bluno.send("s")
            bluno.disconnect()
            print("👋 Done.")

if __name__ == "__main__":
    main()