# test_mic_playback.py
from reachy_mini import ReachyMini
import numpy as np
import soundfile as sf
import noisereduce as nr
import threading
import time

chunks = []

def collect_audio(reachy, duration=4):
    end_time = time.time() + duration
    while time.time() < end_time:
        sample = reachy.media.get_audio_sample()
        if sample is not None:
            chunks.append(sample)

with ReachyMini(connection_mode="localhost_only") as reachy:
    sr = reachy.media.get_input_audio_samplerate()
    print(f"Sample rate: {sr}")

    # Step 1 - capture noise profile (2 seconds of silence)
    print("Capturing noise profile - stay silent for 2 seconds...")
    reachy.media.start_recording()
    noise_chunks = []
    end_time = time.time() + 2
    while time.time() < end_time:
        sample = reachy.media.get_audio_sample()
        if sample is not None:
            noise_chunks.append(sample)
    reachy.media.stop_recording()
    noise_profile = np.concatenate(noise_chunks, axis=0)[:, 0]  # mono
    print(f"Noise profile captured: {noise_profile.shape}")

    # Step 2 - record voice
    chunks = []
    print("Recording 4 seconds... say something!")
    reachy.media.start_recording()
    t = threading.Thread(target=collect_audio, args=(reachy, 4))
    t.start()
    t.join()
    reachy.media.stop_recording()

    if chunks:
        audio = np.concatenate(chunks, axis=0)
        mono = audio[:, 0]  # use left channel

        # Apply noise reduction
        print("Applying noise reduction...")
        cleaned = nr.reduce_noise(
            y=mono,
            sr=sr,
            y_noise=noise_profile,
            prop_decrease=0.9,  # aggressiveness 0-1
            stationary=False
        )

        sf.write("/tmp/recorded_clean.wav", cleaned, sr)
        print("Playing cleaned audio...")
        reachy.media.play_sound("/tmp/recorded_clean.wav")
        time.sleep(5)