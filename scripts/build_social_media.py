#!/usr/bin/env python3
"""Build branded social cards and Bluesky profile artwork."""

from __future__ import annotations

import argparse
from pathlib import Path
from textwrap import shorten

from PIL import Image, ImageDraw, ImageFont, ImageOps

import distribute_content


ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "images" / "social" / "artificial-one-social-master.png"
SOCIAL_DIR = ROOT / "images" / "social"
CARD_DIR = ROOT / "images" / "social-cards"
AVATAR = SOCIAL_DIR / "bluesky-avatar.png"
BANNER = SOCIAL_DIR / "bluesky-banner.jpg"
CARD_SIZE = (1200, 630)


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = (
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    )
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name, size=size)
    return ImageFont.load_default(size=size)


def wrapped_lines(draw: ImageDraw.ImageDraw, text: str, face: ImageFont.ImageFont, width: int, limit: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=face)[2] <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) == limit - 1:
            break
    if current and len(lines) < limit:
        lines.append(current)
    if len(" ".join(lines)) < len(text):
        lines[-1] = shorten(lines[-1], width=max(12, len(lines[-1]) - 1), placeholder="…")
    return lines


def logo_mark(image: Image.Image, box: tuple[int, int, int, int]) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    x0, y0, x1, y1 = box
    draw.ellipse(box, fill=(124, 58, 237, 255), outline=(167, 139, 250, 255), width=max(2, (x1 - x0) // 28))
    face = font(int((y1 - y0) * 0.62), bold=True)
    label = "A"
    bounds = draw.textbbox((0, 0), label, font=face)
    x = x0 + ((x1 - x0) - (bounds[2] - bounds[0])) / 2
    y = y0 + ((y1 - y0) - (bounds[3] - bounds[1])) / 2 - bounds[1] - 2
    draw.text((x, y), label, font=face, fill=(255, 255, 255, 255))


def base_image(size: tuple[int, int], *, centering: tuple[float, float] = (0.5, 0.5)) -> Image.Image:
    if not MASTER.exists():
        raise FileNotFoundError(f"Missing generated social artwork: {MASTER}")
    with Image.open(MASTER) as source:
        return ImageOps.fit(source.convert("RGB"), size, method=Image.Resampling.LANCZOS, centering=centering)


def build_profile_assets() -> None:
    SOCIAL_DIR.mkdir(parents=True, exist_ok=True)

    avatar = Image.new("RGB", (800, 800), "#111827")
    pixels = avatar.load()
    for y in range(800):
        for x in range(800):
            distance = ((x - 260) ** 2 + (y - 220) ** 2) ** 0.5 / 920
            mix = min(1.0, distance)
            pixels[x, y] = (
                int(37 + (17 - 37) * mix),
                int(99 + (24 - 99) * mix),
                int(235 + (39 - 235) * mix),
            )
    logo_mark(avatar, (105, 105, 695, 695))
    avatar.save(AVATAR, format="PNG", optimize=True)

    banner = base_image((1500, 500))
    overlay = Image.new("RGBA", banner.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    draw.rounded_rectangle((70, 72, 895, 428), radius=42, fill=(7, 12, 38, 190), outline=(167, 139, 250, 105), width=2)
    logo_mark(overlay, (112, 130, 332, 350))
    draw.text((370, 142), "artificial.one", font=font(70, bold=True), fill="white")
    draw.text((372, 245), "Compare smarter. Buy with confidence.", font=font(30), fill=(224, 231, 255, 255))
    draw.text((372, 305), "Independent AI tool guides and free decision tools", font=font(24), fill=(196, 181, 253, 255))
    banner = Image.alpha_composite(banner.convert("RGBA"), overlay).convert("RGB")
    banner.save(BANNER, format="JPEG", quality=88, optimize=True, progressive=True)


def build_card(item: dict[str, str], index: int) -> Path:
    CARD_DIR.mkdir(parents=True, exist_ok=True)
    centering = (0.42 + ((index % 3) * 0.08), 0.5)
    card = base_image(CARD_SIZE, centering=centering)
    overlay = Image.new("RGBA", card.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    draw.rectangle((0, 0, 1200, 630), fill=(4, 8, 30, 55))
    draw.rounded_rectangle((56, 50, 855, 580), radius=38, fill=(7, 12, 38, 214), outline=(167, 139, 250, 115), width=2)
    draw.rounded_rectangle((86, 82, 320, 126), radius=22, fill=(99, 102, 241, 235))
    labels = {
        "free-tool": "FREE DECISION TOOL",
        "ai-news": "CURATED AI NEWS",
        "offer-update": "VERIFIED OFFER WATCH",
        "partner-guide": "INDEPENDENT TOOL GUIDE",
    }
    label = labels.get(item["kind"], "ARTIFICIAL.ONE EDITORIAL")
    draw.text((108, 91), label, font=font(18, bold=True), fill="white")

    title_face = font(57, bold=True)
    title_lines = wrapped_lines(draw, item["title"], title_face, 700, 3)
    y = 160
    for line in title_lines:
        draw.text((86, y), line, font=title_face, fill="white")
        y += 68

    description_face = font(27)
    description = item["description"].replace("Best for: ", "Best for ")
    for line in wrapped_lines(draw, description, description_face, 700, 3):
        draw.text((88, y + 8), line, font=description_face, fill=(224, 231, 255, 255))
        y += 39

    logo_mark(overlay, (88, 493, 148, 553))
    draw.text((166, 501), "artificial.one", font=font(27, bold=True), fill="white")
    draw.text((166, 536), "Compare smarter. Buy with confidence.", font=font(17), fill=(196, 181, 253, 255))

    card = Image.alpha_composite(card.convert("RGBA"), overlay).convert("RGB")
    output = CARD_DIR / f"{item.get('image_key', item['id'])}.jpg"
    card.save(output, format="JPEG", quality=86, optimize=True, progressive=True)
    return output


def validate(items: list[dict[str, str]]) -> list[str]:
    errors = []
    for item in items:
        card = CARD_DIR / f"{item.get('image_key', item['id'])}.jpg"
        if not card.exists():
            errors.append(f"missing card: {card.relative_to(ROOT)}")
        elif card.stat().st_size > 1_000_000:
            errors.append(f"card exceeds 1 MB: {card.relative_to(ROOT)}")
        page = ROOT / item["page_path"]
        if item.get("daily") != "true" and page.exists() and item["image"] not in page.read_text(encoding="utf-8"):
            errors.append(f"page does not reference card: {page.relative_to(ROOT)}")
    for asset in (AVATAR, BANNER):
        if not asset.exists():
            errors.append(f"missing profile asset: {asset.relative_to(ROOT)}")
        elif asset.stat().st_size > 1_000_000:
            errors.append(f"profile asset exceeds 1 MB: {asset.relative_to(ROOT)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    items = distribute_content.queue()
    if not args.check:
        build_profile_assets()
        for index, item in enumerate(items):
            build_card(item, index)
        print(f"Built {len(items)} social cards and branded Bluesky profile artwork.")
    errors = validate(items)
    if errors:
        for error in errors:
            print(error)
        return 1
    if args.check:
        print(f"Social media artwork is current ({len(items)} cards).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
