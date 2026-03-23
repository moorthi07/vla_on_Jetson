from reachy_mini import ReachyMini
import moondream as md
from PIL import Image
import cv2

print("Loading Moondream...")
model = md.vl(model="moondream-2b-int8.mf")

with ReachyMini(connection_mode="localhost_only") as reachy:
    print("Getting frame...")
    frame = reachy.media.get_frame()
    
    if frame is not None:
        cv2.imwrite("/tmp/current_frame.jpg", frame)
        print(f"Frame shape: {frame.shape}")
        
        # Load image with PIL
        image = Image.open("/tmp/current_frame.jpg")
        answer = model.query(image, "Is there a wheeled robot or vehicle in this image?")["answer"]
        print(f"VLA answer: {answer}")
    else:
        print("No frame!")