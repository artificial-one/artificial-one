#!/usr/bin/env python3
"""
Generate OG images programmatically using Pillow.
Creates 1200x630px images with tool names, ratings, and branding.
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import re
import os

# Try to import fonts, use default if not available
try:
    # Try to use system fonts
    title_font_path = None
    body_font_path = None
    
    # Windows font paths
    if os.name == 'nt':
        font_dirs = [
            'C:/Windows/Fonts/arial.ttf',
            'C:/Windows/Fonts/arialbd.ttf',
            'C:/Windows/Fonts/calibri.ttf',
        ]
        for font_path in font_dirs:
            if os.path.exists(font_path):
                title_font_path = font_path
                body_font_path = font_path
                break
except:
    pass

def create_gradient_background(width, height, color1, color2):
    """Create a gradient background."""
    img = Image.new('RGB', (width, height), color1)
    draw = ImageDraw.Draw(img)
    
    # Simple gradient effect
    for i in range(height):
        ratio = i / height
        r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
        g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
        b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
        draw.line([(0, i), (width, i)], fill=(r, g, b))
    
    return img

def hex_to_rgb(hex_color):
    """Convert hex color to RGB."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def create_tool_og_image(tool_name, rating, category, output_path):
    """Create OG image for a tool review."""
    width, height = 1200, 630
    
    # Color scheme based on category
    color_schemes = {
        'writing': (hex_to_rgb('#6366f1'), hex_to_rgb('#8b5cf6')),  # Indigo to purple
        'design': (hex_to_rgb('#ec4899'), hex_to_rgb('#f43f5e')),  # Pink to red
        'video': (hex_to_rgb('#3b82f6'), hex_to_rgb('#06b6d4')),   # Blue to cyan
        'coding': (hex_to_rgb('#10b981'), hex_to_rgb('#059669')),  # Green
        'productivity': (hex_to_rgb('#f59e0b'), hex_to_rgb('#d97706')),  # Orange
        'voice': (hex_to_rgb('#8b5cf6'), hex_to_rgb('#a855f7')),   # Purple
        'marketing': (hex_to_rgb('#ef4444'), hex_to_rgb('#dc2626')),  # Red
        'data': (hex_to_rgb('#06b6d4'), hex_to_rgb('#0891b2')),    # Cyan
        'research': (hex_to_rgb('#6366f1'), hex_to_rgb('#4f46e5')),  # Indigo
    }
    
    # Default gradient
    color1, color2 = (hex_to_rgb('#6366f1'), hex_to_rgb('#8b5cf6'))
    
    # Match category
    category_lower = category.lower() if category else ''
    for key, colors in color_schemes.items():
        if key in category_lower:
            color1, color2 = colors
            break
    
    # Create gradient background
    img = create_gradient_background(width, height, color1, color2)
    draw = ImageDraw.Draw(img)
    
    # Try to load fonts
    try:
        if title_font_path:
            title_font = ImageFont.truetype(title_font_path, 72)
            subtitle_font = ImageFont.truetype(title_font_path, 36)
            rating_font = ImageFont.truetype(title_font_path, 48)
        else:
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()
            rating_font = ImageFont.load_default()
    except:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
        rating_font = ImageFont.load_default()
    
    # Add logo/brand text (top left)
    brand_text = "artificial.one"
    try:
        brand_font = ImageFont.truetype(title_font_path, 32) if title_font_path else ImageFont.load_default()
    except:
        brand_font = ImageFont.load_default()
    
    draw.text((60, 40), brand_text, fill=(255, 255, 255), font=brand_font)
    
    # Add tool name (center, large)
    tool_name_clean = tool_name.replace(' Review', '').replace(' review', '').strip()
    # Wrap text if too long
    if len(tool_name_clean) > 25:
        words = tool_name_clean.split()
        lines = []
        current_line = []
        for word in words:
            test_line = ' '.join(current_line + [word])
            if len(test_line) <= 25:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        if current_line:
            lines.append(' '.join(current_line))
        tool_name_clean = '\n'.join(lines[:2])  # Max 2 lines
    
    # Calculate text position (centered)
    bbox = draw.textbbox((0, 0), tool_name_clean, font=title_font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (width - text_width) // 2
    y = height // 2 - 80
    
    # Add shadow for text readability
    draw.text((x + 3, y + 3), tool_name_clean, fill=(0, 0, 0, 128), font=title_font)
    draw.text((x, y), tool_name_clean, fill=(255, 255, 255), font=title_font)
    
    # Add rating
    if rating:
        rating_text = f"{rating}/5"
        stars = "⭐" * min(5, int(float(rating)))
        rating_display = f"{rating_text} {stars}"
        
        bbox = draw.textbbox((0, 0), rating_display, font=rating_font)
        text_width = bbox[2] - bbox[0]
        x_rating = (width - text_width) // 2
        y_rating = y + text_height + 30
        
        draw.text((x_rating + 2, y_rating + 2), rating_display, fill=(0, 0, 0, 128), font=rating_font)
        draw.text((x_rating, y_rating), rating_display, fill=(255, 255, 255), font=rating_font)
    
    # Add category badge (bottom)
    if category:
        category_text = category.replace('&', '&').strip()
        bbox = draw.textbbox((0, 0), category_text, font=subtitle_font)
        text_width = bbox[2] - bbox[0]
        x_cat = (width - text_width) // 2
        y_cat = height - 100
        
        # Draw badge background
        padding = 20
        draw.rounded_rectangle(
            [(x_cat - padding, y_cat - 10), (x_cat + text_width + padding, y_cat + bbox[3] - bbox[1] + 10)],
            radius=10,
            fill=(255, 255, 255, 200)
        )
        draw.text((x_cat, y_cat), category_text, fill=(50, 50, 50), font=subtitle_font)
    
    # Save image
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, 'JPEG', quality=85, optimize=True)
    return True

def create_homepage_og_image(output_path):
    """Create homepage OG image."""
    width, height = 1200, 630
    
    # Purple/indigo gradient
    color1 = hex_to_rgb('#6366f1')
    color2 = hex_to_rgb('#8b5cf6')
    
    img = create_gradient_background(width, height, color1, color2)
    draw = ImageDraw.Draw(img)
    
    try:
        if title_font_path:
            title_font = ImageFont.truetype(title_font_path, 80)
            subtitle_font = ImageFont.truetype(title_font_path, 40)
            stats_font = ImageFont.truetype(title_font_path, 36)
        else:
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()
            stats_font = ImageFont.load_default()
    except:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
        stats_font = ImageFont.load_default()
    
    # Brand
    brand_text = "artificial.one"
    try:
        brand_font = ImageFont.truetype(title_font_path, 42) if title_font_path else ImageFont.load_default()
    except:
        brand_font = ImageFont.load_default()
    draw.text((60, 50), brand_text, fill=(255, 255, 255), font=brand_font)
    
    # Main title
    title = "Find the Right AI Tool\nin 5 Minutes"
    bbox = draw.textbbox((0, 0), title, font=title_font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (width - text_width) // 2
    y = height // 2 - 100
    
    draw.text((x + 3, y + 3), title, fill=(0, 0, 0, 128), font=title_font)
    draw.text((x, y), title, fill=(255, 255, 255), font=title_font)
    
    # Stats
    stats = "220+ Tools Reviewed | Zero BS | Honest Reviews"
    bbox = draw.textbbox((0, 0), stats, font=stats_font)
    text_width = bbox[2] - bbox[0]
    x_stats = (width - text_width) // 2
    y_stats = y + text_height + 40
    
    draw.text((x_stats + 2, y_stats + 2), stats, fill=(0, 0, 0, 128), font=stats_font)
    draw.text((x_stats, y_stats), stats, fill=(255, 255, 255), font=stats_font)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, 'JPEG', quality=85, optimize=True)
    return True

def create_category_og_image(category_name, tool_count, output_path):
    """Create OG image for category page."""
    width, height = 1200, 630
    
    color1 = hex_to_rgb('#6366f1')
    color2 = hex_to_rgb('#8b5cf6')
    
    img = create_gradient_background(width, height, color1, color2)
    draw = ImageDraw.Draw(img)
    
    try:
        if title_font_path:
            title_font = ImageFont.truetype(title_font_path, 72)
            count_font = ImageFont.truetype(title_font_path, 48)
        else:
            title_font = ImageFont.load_default()
            count_font = ImageFont.load_default()
    except:
        title_font = ImageFont.load_default()
        count_font = ImageFont.load_default()
    
    # Category name
    category_clean = category_name.replace(' AI Tools', '').replace(' Tools', '').strip()
    bbox = draw.textbbox((0, 0), category_clean, font=title_font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (width - text_width) // 2
    y = height // 2 - 60
    
    draw.text((x + 3, y + 3), category_clean, fill=(0, 0, 0, 128), font=title_font)
    draw.text((x, y), category_clean, fill=(255, 255, 255), font=title_font)
    
    # Tool count
    count_text = f"{tool_count} Tools Reviewed"
    bbox = draw.textbbox((0, 0), count_text, font=count_font)
    text_width = bbox[2] - bbox[0]
    x_count = (width - text_width) // 2
    y_count = y + text_height + 40
    
    draw.text((x_count + 2, y_count + 2), count_text, fill=(0, 0, 0, 128), font=count_font)
    draw.text((x_count, y_count), count_text, fill=(255, 255, 255), font=count_font)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, 'JPEG', quality=85, optimize=True)
    return True

def create_default_og_image(output_path):
    """Create default OG image."""
    width, height = 1200, 630
    
    color1 = hex_to_rgb('#6366f1')
    color2 = hex_to_rgb('#8b5cf6')
    
    img = create_gradient_background(width, height, color1, color2)
    draw = ImageDraw.Draw(img)
    
    try:
        if title_font_path:
            title_font = ImageFont.truetype(title_font_path, 64)
        else:
            title_font = ImageFont.load_default()
    except:
        title_font = ImageFont.load_default()
    
    title = "artificial.one\nAI Tool Reviews"
    bbox = draw.textbbox((0, 0), title, font=title_font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    
    draw.text((x + 3, y + 3), title, fill=(0, 0, 0, 128), font=title_font)
    draw.text((x, y), title, fill=(255, 255, 255), font=title_font)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, 'JPEG', quality=85, optimize=True)
    return True

def extract_tool_info(content, filepath):
    """Extract tool information from HTML."""
    info = {}
    
    # Extract title
    title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
    if title_match:
        title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
        tool_match = re.search(r'^([^R]+?)\s+Review', title, re.IGNORECASE)
        if tool_match:
            info['name'] = tool_match.group(1).strip()
        else:
            info['name'] = title.split('Review')[0].strip()
    
    # Extract rating
    rating_match = re.search(r'(\d+\.?\d*)/10|(\d+\.?\d*)/5', content)
    if rating_match:
        rating = rating_match.group(1) or rating_match.group(2)
        info['rating'] = rating
    
    # Extract category
    cat_match = re.search(r'category["\']:\s*["\']([^"\']+)["\']', content, re.IGNORECASE)
    if not cat_match:
        # Try H1 or other patterns
        h1_match = re.search(r'<h1[^>]*>.*?([A-Z][a-z]+ & [A-Z][a-z]+).*?</h1>', content, re.IGNORECASE | re.DOTALL)
        if h1_match:
            info['category'] = h1_match.group(1)
    else:
        info['category'] = cat_match.group(1)
    
    return info

def main():
    """Generate OG images for all pages."""
    root = Path('.')
    images_dir = Path('images')
    
    # Create directory structure
    (images_dir / 'og-tools').mkdir(parents=True, exist_ok=True)
    (images_dir / 'og-categories').mkdir(parents=True, exist_ok=True)
    (images_dir / 'og-blog').mkdir(parents=True, exist_ok=True)
    
    print("Generating OG images...")
    print("Note: Install Pillow if not installed: pip install Pillow\n")
    
    # Check if Pillow is installed
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("ERROR: Pillow is not installed.")
        print("Install it with: pip install Pillow")
        return
    
    html_files = []
    for html_file in root.rglob('*.html'):
        if any(part.startswith('.') for part in html_file.parts):
            continue
        if '.git' in html_file.parts:
            continue
        html_files.append(html_file)
    
    print(f"Found {len(html_files)} HTML files\n")
    
    generated = 0
    skipped = 0
    default_created = False
    
    # Generate images
    for filepath in sorted(html_files):
        try:
            path_str = str(filepath).replace('\\', '/')
            
            if filepath.name == 'index.html':
                # Homepage
                output_path = images_dir / 'og-homepage.jpg'
                if not output_path.exists():
                    create_homepage_og_image(output_path)
                    print(f"[OK] Generated: {output_path}")
                    generated += 1
                else:
                    skipped += 1
            
            elif '/tools/' in path_str or filepath.parent.name == 'tools':
                # Tool review
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                info = extract_tool_info(content, filepath)
                tool_name = info.get('name', filepath.stem.replace('-review', '').replace('-', ' ').title())
                rating = info.get('rating', '')
                category = info.get('category', '')
                
                # Clean tool name for filename
                tool_name_clean = filepath.stem.replace('-review', '').replace('-', '-').lower()
                output_path = images_dir / 'og-tools' / f'{tool_name_clean}.jpg'
                
                if not output_path.exists():
                    create_tool_og_image(tool_name, rating, category, output_path)
                    if generated < 50:  # Show first 50
                        print(f"[OK] Generated: {output_path}")
                    generated += 1
                else:
                    skipped += 1
            
            elif '/category/' in path_str or filepath.parent.name == 'category':
                # Category page
                category_name = filepath.stem.replace('-', ' ').title()
                # Estimate tool count (you can improve this)
                tool_count = 25  # Default estimate
                
                output_path = images_dir / 'og-categories' / f'{filepath.stem}.jpg'
                if not output_path.exists():
                    create_category_og_image(category_name, tool_count, output_path)
                    print(f"[OK] Generated: {output_path}")
                    generated += 1
                else:
                    skipped += 1
            
            elif 'blog-' in filepath.name:
                # Blog post - use default for now
                if not default_created:
                    output_path = images_dir / 'og-default.jpg'
                    if not output_path.exists():
                        create_default_og_image(output_path)
                        print(f"[OK] Generated: {output_path}")
                        generated += 1
                        default_created = True
                    else:
                        default_created = True
            
            else:
                # Default image (create once)
                if not default_created:
                    output_path = images_dir / 'og-default.jpg'
                    if not output_path.exists():
                        create_default_og_image(output_path)
                        print(f"[OK] Generated: {output_path}")
                        generated += 1
                        default_created = True
                    else:
                        default_created = True
        
        except Exception as e:
            print(f"[ERROR] Failed to generate image for {filepath}: {e}")
    
    print(f"\nCompleted!")
    print(f"Generated: {generated} images")
    print(f"Skipped (already exist): {skipped} images")
    print(f"\nImages saved to: {images_dir}/")
    print("\nNext steps:")
    print("1. Review generated images")
    print("2. Replace with custom designs in Canva if desired")
    print("3. Optimize images (use TinyPNG)")
    print("4. Upload to your server")

if __name__ == '__main__':
    main()
