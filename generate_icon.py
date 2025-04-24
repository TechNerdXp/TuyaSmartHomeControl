from PIL import Image, ImageDraw
from pathlib import Path
import colorsys

def create_base_image(size):
    # Create a new image with dark blue background
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Colors
    primary = (41, 98, 255)    # Smart blue
    secondary = (0, 150, 255)  # Light blue
    accent = (255, 255, 255)   # White
    
    # Calculate dimensions
    center = size // 2
    radius = size // 3
    thickness = max(size // 20, 1)
    
    # Draw outer circle (connection ring)
    draw.ellipse(
        [(center - radius, center - radius),
         (center + radius, center + radius)],
        outline=secondary,
        width=thickness
    )
    
    # Draw inner home shape
    home_size = radius * 1.2
    points = [
        (center - home_size//2, center + home_size//3),  # Bottom left
        (center + home_size//2, center + home_size//3),  # Bottom right
        (center, center - home_size//2),                 # Top
    ]
    draw.polygon(points, fill=primary)
    
    # Draw connection dots
    dot_radius = thickness
    angles = [30, 150, 270]
    for angle in angles:
        x = center + int(radius * 1.2 * (angle/360))
        y = center + int(radius * 1.2 * (angle/360))
        draw.ellipse(
            [(x - dot_radius, y - dot_radius),
             (x + dot_radius, y + dot_radius)],
            fill=accent
        )
    
    return img

def generate_app_icon():
    output_ico = Path('assets/app.ico')
    output_ico.parent.mkdir(exist_ok=True)
    
    # Generate different sizes
    sizes = [16, 32, 48, 64, 128, 256]
    icons = []
    
    for size in sizes:
        icons.append(create_base_image(size))
    
    # Save as ICO with multiple sizes
    icons[0].save(
        output_ico,
        format='ICO',
        sizes=[(i.width, i.height) for i in icons],
        append_images=icons[1:]
    )
    print(f"App icon generated: {output_ico}")

if __name__ == "__main__":
    generate_app_icon()
