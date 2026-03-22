from transformers import AutoModelForCausalLM, AutoTokenizer
from PIL import Image
from reachy_mini import ReachyMini
import cv2
import torch

print("Loading Moondream2 locally...")
model_path = "/home/seeed/reachy_mini/models/moondream2"

tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    trust_remote_code=True,
    torch_dtype=torch.float32,  # float32 for CPU/Jetson
    device_map="cpu"
)
model.eval()
print("Model loaded!")

with ReachyMini(connection_mode="localhost_only") as reachy:
    frame = reachy.media.get_frame()
    cv2.imwrite("/tmp/current_frame.jpg", frame)
    image = Image.open("/tmp/current_frame.jpg")

    enc_image = model.encode_image(image)
    answer = model.answer_question(
        enc_image,
        "Is there a wheeled robot or vehicle in this image?",
        tokenizer
    )
    print(f"Answer: {answer}")
