#!/usr/bin/env python3
"""Analyze, crop, de-background, rename, and validate screenshot-derived sprites."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("ERROR: Pillow is required. Install it with: python -m pip install Pillow", file=sys.stderr)
    raise SystemExit(2)


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}


def natural_key(path: Path):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name)]


def image_files(folder: Path):
    return sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS), key=natural_key)


def parse_rect(text: str):
    values = [int(v.strip()) for v in text.split(",")]
    if len(values) != 4 or values[2] <= 0 or values[3] <= 0:
        raise argparse.ArgumentTypeError("Expected x,y,width,height with positive width and height")
    return tuple(values)


def parse_size(text: str):
    values = [int(v.strip()) for v in text.split(",")]
    if len(values) != 2 or min(values) <= 0:
        raise argparse.ArgumentTypeError("Expected width,height")
    return tuple(values)


def parse_color(text: str):
    value = text.strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        raise argparse.ArgumentTypeError("Expected a color such as 000000 or FFFFFF")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def foreground_bbox(image: Image.Image, roi, background: str, threshold: int, bg_color):
    x, y, width, height = roi
    if x < 0 or y < 0 or x + width > image.width or y + height > image.height:
        raise ValueError(f"ROI {roi} exceeds image size {image.size}")
    crop = image.convert("RGBA").crop((x, y, x + width, y + height))
    pixels = crop.load()
    min_x, min_y, max_x, max_y = width, height, -1, -1
    target = (0, 0, 0) if background == "black" else (255, 255, 255) if background == "white" else bg_color
    for py in range(height):
        for px in range(width):
            r, g, b, a = pixels[px, py]
            foreground = a > threshold if background == "alpha" else max(abs(r - target[0]), abs(g - target[1]), abs(b - target[2])) > threshold
            if foreground:
                min_x, min_y = min(min_x, px), min(min_y, py)
                max_x, max_y = max(max_x, px), max(max_y, py)
    return None if max_x < 0 else (x + min_x, y + min_y, x + max_x, y + max_y)


def clamp_padded_union(union, padding: int, size):
    left, top, right, bottom = union
    left, top = max(0, left - padding), max(0, top - padding)
    right, bottom = min(size[0] - 1, right + padding), min(size[1] - 1, bottom + padding)
    return (left, top, right - left + 1, bottom - top + 1)


def make_contact_sheet(files, output: Path, roi):
    x, y, width, height = roi
    thumb_width = min(480, width)
    thumb_height = max(1, round(height * thumb_width / width))
    label_height = 20
    columns = min(4, max(1, math.ceil(math.sqrt(len(files)))))
    rows = math.ceil(len(files) / columns)
    sheet = Image.new("RGB", (columns * thumb_width, rows * (thumb_height + label_height)), (42, 42, 42))
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(files):
        with Image.open(path) as image:
            tile = image.convert("RGB").crop((x, y, x + width, y + height)).resize((thumb_width, thumb_height))
        tx, ty = (index % columns) * thumb_width, (index // columns) * (thumb_height + label_height)
        sheet.paste(tile, (tx, ty))
        draw.text((tx + 3, ty + thumb_height + 2), path.name, fill=(255, 255, 0))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def cmd_analyze(args):
    files = image_files(args.input)
    if not files:
        raise ValueError(f"No supported images found in {args.input}")
    rows, union, source_size = [], None, None
    bg_color = args.bg_color or (0, 0, 0)
    for path in files:
        with Image.open(path) as image:
            source_size = source_size or image.size
            bbox = foreground_bbox(image, args.roi, args.background, args.threshold, bg_color)
        if bbox:
            union = bbox if union is None else (min(union[0], bbox[0]), min(union[1], bbox[1]), max(union[2], bbox[2]), max(union[3], bbox[3]))
        rows.append({"file": path.name, "bbox_inclusive": bbox})
    if union is None:
        raise ValueError("No foreground detected inside the ROI")
    recommended = clamp_padded_union(union, args.padding, source_size)
    report = {"file_count": len(files), "source_size": source_size, "roi_xywh": args.roi, "background": args.background,
              "threshold": args.threshold, "foreground_union_inclusive": union, "recommended_crop_xywh": recommended, "files": rows}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.contact_sheet:
        make_contact_sheet(files, args.contact_sheet, args.roi)
    print(json.dumps({k: report[k] for k in ("file_count", "source_size", "foreground_union_inclusive", "recommended_crop_xywh")}, ensure_ascii=False))


def load_names(path: Path | None):
    if not path:
        return {}, {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or "source" not in rows[0] or "output" not in rows[0]:
        raise ValueError("names CSV must contain source and output columns")
    mapping = {row["source"]: row["output"] for row in rows}
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("names CSV contains duplicate output names")
    return mapping, {row["source"]: row for row in rows}


def remove_background(image: Image.Image, mode: str, threshold: int, bg_color):
    rgba = image.convert("RGBA")
    if mode == "keep":
        return rgba
    output = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    source_pixels, output_pixels = rgba.load(), output.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, original_alpha = source_pixels[x, y]
            if mode.startswith("black-to-alpha"):
                alpha = max(r, g, b)
                if alpha <= threshold:
                    continue
                if mode == "black-to-alpha-white":
                    output_pixels[x, y] = (255, 255, 255, alpha)
                else:
                    rgb = tuple(min(255, round(channel * 255 / alpha)) for channel in (r, g, b))
                    output_pixels[x, y] = rgb + (alpha,)
            else:
                distance = max(abs(r - bg_color[0]), abs(g - bg_color[1]), abs(b - bg_color[2]))
                if distance > threshold:
                    output_pixels[x, y] = (r, g, b, max(original_alpha, distance))
    return output


def cmd_extract(args):
    files = image_files(args.input)
    if not files:
        raise ValueError(f"No supported images found in {args.input}")
    mapping, metadata = load_names(args.names_csv)
    missing = sorted(set(mapping) - {p.name for p in files})
    if missing:
        raise ValueError(f"names CSV references missing source files: {missing[:5]}")
    args.output.mkdir(parents=True, exist_ok=True)
    x, y, width, height = args.crop
    manifest, output_names = [], []
    for path in files:
        output_name = mapping.get(path.name, f"{path.stem}.png")
        output_names.append(output_name)
        with Image.open(path) as source:
            if x < 0 or y < 0 or x + width > source.width or y + height > source.height:
                raise ValueError(f"Crop {args.crop} exceeds {path.name} size {source.size}")
            result = remove_background(source.crop((x, y, x + width, y + height)), args.background, args.threshold, args.bg_color or (0, 0, 0))
            result.save(args.output / output_name, "PNG")
        row = {"source": path.name, "output": output_name, "width": width, "height": height}
        row.update(metadata.get(path.name, {})); manifest.append(row)
    if len(set(output_names)) != len(output_names):
        raise ValueError("Duplicate output names detected")
    with (args.output / "manifest.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        fields = list(dict.fromkeys(key for row in manifest for key in row))
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(manifest)
    if args.zip:
        args.zip.parent.mkdir(parents=True, exist_ok=True)
        created = Path(shutil.make_archive(str(args.zip.with_suffix("")), "zip", root_dir=args.output.parent, base_dir=args.output.name))
        if created != args.zip:
            created.replace(args.zip)
    print(json.dumps({"output_count": len(files), "size": [width, height], "output": str(args.output), "zip": str(args.zip) if args.zip else None}, ensure_ascii=False))


def cmd_validate(args):
    files, errors, sizes = image_files(args.input), [], set()
    if args.expected_count is not None and len(files) != args.expected_count:
        errors.append(f"expected {args.expected_count} images, found {len(files)}")
    for path in files:
        with Image.open(path) as image:
            rgba = image.convert("RGBA"); sizes.add(rgba.size)
            if args.expected_size and rgba.size != args.expected_size:
                errors.append(f"{path.name}: expected size {args.expected_size}, found {rgba.size}")
            if args.require_transparent_corners:
                corners = [rgba.getpixel(point)[3] for point in ((0, 0), (rgba.width - 1, 0), (0, rgba.height - 1), (rgba.width - 1, rgba.height - 1))]
                if any(corners): errors.append(f"{path.name}: one or more corners are not transparent")
    print(json.dumps({"file_count": len(files), "sizes": sorted(sizes), "errors": errors}, ensure_ascii=False))
    if errors: raise SystemExit(1)


def build_parser():
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    analyze = commands.add_parser("analyze")
    analyze.add_argument("--input", type=Path, required=True); analyze.add_argument("--roi", type=parse_rect, required=True)
    analyze.add_argument("--background", choices=("black", "white", "alpha", "color"), default="black")
    analyze.add_argument("--bg-color", type=parse_color); analyze.add_argument("--threshold", type=int, default=4)
    analyze.add_argument("--padding", type=int, default=10); analyze.add_argument("--report", type=Path, required=True)
    analyze.add_argument("--contact-sheet", type=Path); analyze.set_defaults(func=cmd_analyze)
    extract = commands.add_parser("extract")
    extract.add_argument("--input", type=Path, required=True); extract.add_argument("--output", type=Path, required=True)
    extract.add_argument("--crop", type=parse_rect, required=True)
    extract.add_argument("--background", choices=("keep", "black-to-alpha-white", "black-to-alpha-preserve", "color-to-alpha"), default="keep")
    extract.add_argument("--bg-color", type=parse_color); extract.add_argument("--threshold", type=int, default=2)
    extract.add_argument("--names-csv", type=Path); extract.add_argument("--zip", type=Path); extract.set_defaults(func=cmd_extract)
    validate = commands.add_parser("validate")
    validate.add_argument("--input", type=Path, required=True); validate.add_argument("--expected-count", type=int)
    validate.add_argument("--expected-size", type=parse_size); validate.add_argument("--require-transparent-corners", action="store_true")
    validate.set_defaults(func=cmd_validate)
    return root


def main():
    try:
        args = build_parser().parse_args(); args.func(args)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr); raise SystemExit(2)


if __name__ == "__main__":
    main()

