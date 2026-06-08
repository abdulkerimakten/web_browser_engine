from PIL import Image

INPUT_FILE = "1F600_color.png"
OUTPUT_FILE = "emoji_grinning_16.png"

img = Image.open(INPUT_FILE)
img = img.resize((16, 16))
img.save(OUTPUT_FILE)