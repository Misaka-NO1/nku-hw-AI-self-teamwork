"""Generate a neutral, non-branded icon for the temporary MCP test plugin."""

from pathlib import Path

from PIL import Image, ImageDraw


SCALE = 4
SIZE = 512
OUTPUT = Path(__file__).with_name("campus-tools-dev-test-icon.png")


def box(coords: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    return tuple(value * SCALE for value in coords)


image = Image.new("RGB", (SIZE * SCALE, SIZE * SCALE), "#f5f8fb")
draw = ImageDraw.Draw(image)

# A simple plug represents a test connection; the small dot marks it as a probe.
draw.rounded_rectangle(box((28, 28, 484, 484)), radius=108 * SCALE, fill="#174b66")
draw.rounded_rectangle(box((189, 212, 323, 334)), radius=34 * SCALE, fill="#ffffff")
draw.rounded_rectangle(box((210, 158, 235, 235)), radius=12 * SCALE, fill="#ffffff")
draw.rounded_rectangle(box((277, 158, 302, 235)), radius=12 * SCALE, fill="#ffffff")
draw.line([(256 * SCALE, 327 * SCALE), (256 * SCALE, 380 * SCALE)], fill="#ffffff", width=26 * SCALE)
draw.arc(box((256, 343, 363, 431)), 0, 180, fill="#ffffff", width=24 * SCALE)
draw.ellipse(box((353, 375, 384, 406)), fill="#ffffff")
draw.ellipse(box((361, 102, 424, 165)), fill="#f2b65d")

image.resize((SIZE, SIZE), Image.Resampling.LANCZOS).save(OUTPUT, optimize=True)
print(OUTPUT)
