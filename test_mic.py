# test_mic.py
from reachy_mini import ReachyMini
import time

with ReachyMini(connection_mode="localhost_only") as reachy:
    print("Starting recording...")
    reachy.media.start_recording()
    
    print("Say something into the Jabra mic...")
    time.sleep(3)
    
    sample = reachy.media.get_audio_sample()
    reachy.media.stop_recording()
    
    print(f"Got sample: {sample}")
    print(f"Sample shape: {sample.shape if sample is not None else 'None'}")
