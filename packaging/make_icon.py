#!/usr/bin/env python3
"""Render AppIcon.icns: a gauge on a rounded square, drawn with AppKit.

Run from the packaging/ directory:  python3 make_icon.py
Requires pyobjc-framework-Cocoa and the `iconutil` tool (ships with macOS).
"""
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

from AppKit import (
    NSBezierPath,
    NSBitmapImageRep,
    NSCalibratedRGBColorSpace,
    NSColor,
    NSGradient,
    NSGraphicsContext,
    NSLineCapStyleRound,
    NSPNGFileType,
)

HERE = Path(__file__).resolve().parent
OUT = HERE / "AppIcon.icns"


def rgb(r, g, b, a=1.0):
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(r / 255, g / 255, b / 255, a)


def render(size):
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, size, size, 8, 4, True, False, NSCalibratedRGBColorSpace, 0, 0
    )
    ctx = NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(ctx)

    s = size / 1024  # design on a 1024 grid
    # Big Sur style tile: 824pt square inset 100pt, corner radius ~185pt.
    tile = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        ((100 * s, 100 * s), (824 * s, 824 * s)), 185 * s, 185 * s
    )
    NSGradient.alloc().initWithStartingColor_endingColor_(
        rgb(58, 52, 48), rgb(28, 25, 23)
    ).drawInBezierPath_angle_(tile, -90)

    cx, cy, r = 512 * s, 455 * s, 270 * s
    width = 70 * s

    def arc(start, end, color):
        p = NSBezierPath.bezierPath()
        p.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_clockwise_(
            (cx, cy), r, start, end, True
        )
        p.setLineWidth_(width)
        p.setLineCapStyle_(NSLineCapStyleRound)
        color.setStroke()
        p.stroke()

    # Gauge track spans 210° → -30° (clockwise); fill to ~68%.
    arc(210, -30, rgb(255, 255, 255, 0.14))
    fill_end = 210 - 240 * 0.68
    arc(210, fill_end, rgb(232, 129, 92))

    # Needle + hub.
    ang = math.radians(fill_end)
    needle = NSBezierPath.bezierPath()
    needle.moveToPoint_((cx, cy))
    needle.lineToPoint_((cx + math.cos(ang) * (r - 95 * s), cy + math.sin(ang) * (r - 95 * s)))
    needle.setLineWidth_(30 * s)
    needle.setLineCapStyle_(NSLineCapStyleRound)
    rgb(245, 240, 232).setStroke()
    needle.stroke()
    rgb(245, 240, 232).setFill()
    NSBezierPath.bezierPathWithOvalInRect_(((cx - 42 * s, cy - 42 * s), (84 * s, 84 * s))).fill()

    NSGraphicsContext.restoreGraphicsState()
    return rep.representationUsingType_properties_(NSPNGFileType, None)


def main():
    tmp = Path(tempfile.mkdtemp())
    iconset = tmp / "AppIcon.iconset"
    iconset.mkdir()
    for base in (16, 32, 128, 256, 512):
        render(base).writeToFile_atomically_(str(iconset / f"icon_{base}x{base}.png"), True)
        render(base * 2).writeToFile_atomically_(str(iconset / f"icon_{base}x{base}@2x.png"), True)
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(OUT)], check=True)
    render(1024).writeToFile_atomically_(str(HERE / "AppIcon-preview.png"), True)
    shutil.rmtree(tmp)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
