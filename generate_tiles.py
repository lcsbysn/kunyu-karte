"""
Tile-Generator für die Kunyu Wanguo Quantu Karte.
Fügt 6 TIFF-Panels zusammen und erzeugt Deep Zoom Image (DZI) Tiles.
"""

import os
import sys
import math
import json
from PIL import Image

Image.MAX_IMAGE_PIXELS = None  # Allow huge images

TIFF_DIR = os.path.join(os.path.dirname(__file__), '..')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'tiles')
TILE_SIZE = 256
OVERLAP = 1
FORMAT = 'jpg'
QUALITY = 85

def stitch_panels():
    """Load and stitch 6 TIFF panels left-to-right into one large image."""
    print("=== Stitching 6 panels ===")
    panels = []
    total_width = 0
    max_height = 0

    for i in range(1, 7):
        path = os.path.join(TIFF_DIR, f'TIFF {i}.tif')
        print(f"  Loading Panel {i}: {path}")
        img = Image.open(path)
        img.load()
        panels.append(img)
        total_width += img.width
        max_height = max(max_height, img.height)
        print(f"    Size: {img.width} x {img.height}")

    print(f"  Combined size: {total_width} x {max_height}")
    combined = Image.new('RGB', (total_width, max_height), (26, 18, 8))

    x_offset = 0
    for i, panel in enumerate(panels):
        print(f"  Pasting Panel {i+1} at x={x_offset}")
        combined.paste(panel, (x_offset, 0))
        x_offset += panel.width
        panel.close()

    print("  Stitching complete!")
    return combined


def generate_dzi(image):
    """Generate Deep Zoom Image tiles from a PIL Image."""
    width, height = image.size
    max_level = math.ceil(math.log2(max(width, height)))

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Write DZI descriptor
    dzi_path = os.path.join(OUTPUT_DIR, 'kunyu.dzi')
    dzi_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Image xmlns="http://schemas.microsoft.com/deepzoom/2008"
       Format="{FORMAT}"
       Overlap="{OVERLAP}"
       TileSize="{TILE_SIZE}">
    <Size Width="{width}" Height="{height}"/>
</Image>'''

    with open(dzi_path, 'w') as f:
        f.write(dzi_xml)
    print(f"  DZI descriptor: {dzi_path}")

    # Write metadata for the viewer
    meta = {
        'width': width,
        'height': height,
        'tileSize': TILE_SIZE,
        'overlap': OVERLAP,
        'maxLevel': max_level,
        'format': FORMAT
    }
    with open(os.path.join(OUTPUT_DIR, 'meta.json'), 'w') as f:
        json.dump(meta, f, indent=2)

    tiles_base = os.path.join(OUTPUT_DIR, 'kunyu_files')

    print(f"=== Generating tiles (levels 0-{max_level}) ===")

    # Generate from highest resolution (max_level) down to 0
    current = image
    for level in range(max_level, -1, -1):
        level_dir = os.path.join(tiles_base, str(level))
        os.makedirs(level_dir, exist_ok=True)

        lw, lh = current.size
        cols = math.ceil(lw / TILE_SIZE)
        rows = math.ceil(lh / TILE_SIZE)
        tile_count = 0

        for col in range(cols):
            for row in range(rows):
                # Calculate crop bounds with overlap
                x = col * TILE_SIZE - (OVERLAP if col > 0 else 0)
                y = row * TILE_SIZE - (OVERLAP if row > 0 else 0)
                x2 = min(lw, (col + 1) * TILE_SIZE + OVERLAP)
                y2 = min(lh, (row + 1) * TILE_SIZE + OVERLAP)
                x = max(0, x)
                y = max(0, y)

                tile = current.crop((x, y, x2, y2))
                tile_path = os.path.join(level_dir, f'{col}_{row}.{FORMAT}')
                tile.save(tile_path, 'JPEG', quality=QUALITY)
                tile_count += 1

        print(f"  Level {level}: {lw}x{lh} -> {cols}x{rows} = {tile_count} tiles")

        # Scale down for next level
        if level > 0:
            new_w = max(1, lw // 2)
            new_h = max(1, lh // 2)
            current = current.resize((new_w, new_h), Image.LANCZOS)

    current.close()
    print(f"\n=== Done! Tiles saved to: {tiles_base} ===")


if __name__ == '__main__':
    print("Kunyu Wanguo Quantu - Tile Generator")
    print("=" * 50)
    combined = stitch_panels()
    generate_dzi(combined)
    combined.close()
    print("\nReady! Start the server with: python server.py")
