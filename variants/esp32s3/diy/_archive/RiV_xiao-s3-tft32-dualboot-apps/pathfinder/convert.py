import os
import struct
from PIL import Image

def convert_to_lvgl_bin(input_path, output_path):
    img = Image.open(input_path).convert('RGB')
    width, height = img.size
    
    # Header LVGL v8: cf=4 (True color), w, h
    # Bitmask: cf (5 bit), always_zero (3), reserved (2), w (11), h (11)
    header = 4 | (width << 10) | (height << 21)
    
    with open(output_path, 'wb') as f:
        f.write(struct.pack('<I', header))
        
        # Convert RGB888 to RGB565 (Swap bytes for Little Endian)
        for y in range(height):
            for x in range(width):
                r, g, b = img.getpixel((x, y))
                color565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                f.write(struct.pack('<H', color565))

# Scan seluruh folder maps
for root, dirs, files in os.walk("maps"):
    for file in files:
        if file.endswith((".png", ".jpg")):
            in_path = os.path.join(root, file)
            out_path = in_path.rsplit('.', 1)[0] + '.bin'
            convert_to_lvgl_bin(in_path, out_path)
            os.remove(in_path) # Hapus PNG lama
            print(f"Converted: {out_path}")
            
print("✅ SELESAI! Copy folder 'maps' ke SD Card kamu.")