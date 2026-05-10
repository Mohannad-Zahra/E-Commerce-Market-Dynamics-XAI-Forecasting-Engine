from PIL import Image
import os

folder = 'FrontEnd/app/src/assets/images/'
files = ['banner_Hero1', 'banner_Hero2', 'banner_Hero3']
target_size = (1300, 500)

for f in files:
    png_path = os.path.join(folder, f + '.png')
    if not os.path.exists(png_path):
        continue
        
    with Image.open(png_path) as img:
        print(f"Processing {f}.png...")
        # 1. Crop to target aspect ratio (2.6:1)
        # Current is 1:1, so we need to take a horizontal slice
        w, h = img.size
        new_h = int(w * (target_size[1] / target_size[0]))
        top = (h - new_h) // 2
        bottom = top + new_h
        
        cropped = img.crop((0, top, w, bottom))
        
        # 2. Resize to 1300x500
        resized = cropped.resize(target_size, Image.Resampling.LANCZOS)
        
        # 3. Save as JPG (overwriting the previous JPGs to restore .jpg imports)
        jpg_path = os.path.join(folder, f + '.jpg')
        resized.convert('RGB').save(jpg_path, 'JPEG', quality=85, optimize=True)
        print(f"  Saved to {f}.jpg: {resized.size} ({os.path.getsize(jpg_path)} bytes)")

# Cleanup: remove the PNGs to keep it clean and restore JPG consistency
for f in files:
    png_path = os.path.join(folder, f + '.png')
    if os.path.exists(png_path):
        os.remove(png_path)
