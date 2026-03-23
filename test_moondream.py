import moondream as md
from PIL import Image
from reachy_mini import ReachyMini
import cv2

model = md.vl(api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJrZXlfaWQiOiJjMmU2ZjRkMy05NzBlLTQ2YzAtYjE4Zi00YTMwNzEwOGE1MDEiLCJvcmdfaWQiOiJlMDdYVTN1bXViTHdWMjVGZk5LZDg1Und3VUNxZ1k1WCIsImlhdCI6MTc3NDIxNjM0MywidmVyIjoxfQ.Q5bGFdPvXey98I-qnhOsPzU_21WOftDrybK2Y-iVjoA")

with ReachyMini(connection_mode="localhost_only") as reachy:
    frame = reachy.media.get_frame()
    cv2.imwrite("/tmp/current_frame.jpg", frame)
    image = Image.open("/tmp/current_frame.jpg")
    answer = model.query(image, "Is there a wheeled robot or vehicle in this image?")["answer"]
    print(f"Answer: {answer}")
