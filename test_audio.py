# test_audio.py
from reachy_mini import ReachyMini
import time

with ReachyMini(connection_mode="localhost_only") as reachy:
    print("Playing wake_up sound...")
    reachy.media.play_sound("/home/seeed/reachy_mini/src/reachy_mini/assets/wake_up.wav")
    time.sleep(3)
    
    print("Playing dance sound...")
    reachy.media.play_sound("/home/seeed/reachy_mini/src/reachy_mini/assets/dance1.wav")
    time.sleep(3)
