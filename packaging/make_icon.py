#!/usr/bin/env python3
"""Render AppIcon.icns and the website icons, drawn with AppKit.

Three usage meters (the 5-hour, weekly and per-model rows of the dropdown) on
the espresso tile with an amber glyph, the house style shared with Quoth,
Plainview, Gaugeline and Staple. Geometry and colors were sampled from the
1024 px Quoth icon.

Run from anywhere:  python3 packaging/make_icon.py
Requires pyobjc-framework-Cocoa and `iconutil` (ships with macOS).
"""
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

from AppKit import (
    NSAffineTransform,
    NSBezierPath,
    NSBitmapImageRep,
    NSCalibratedRGBColorSpace,
    NSColor,
    NSGradient,
    NSGraphicsContext,
    NSPNGFileType,
    NSShadow,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "AppIcon.icns"
DOCS = ROOT / "docs"

TILE_TOP = (70, 50, 31)
TILE_BOTTOM = (29, 21, 15)
GLYPH_TOP = (255, 198, 106)
GLYPH_BOTTOM = (239, 140, 40)
TRACK = (255, 255, 255, 0.09)
FILLS = (0.80, 0.55, 0.32)  # top to bottom


def rgb(r, g, b, a=1.0):
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(r / 255, g / 255, b / 255, a)


def squircle(s):
    """macOS-style continuous-corner tile: a superellipse, 824 pt on a 1024 grid."""
    cx = cy = 512 * s
    a = 412 * s
    n = 4.7
    path = NSBezierPath.bezierPath()
    steps = 720
    for i in range(steps):
        t = 2 * math.pi * i / steps
        c, si = math.cos(t), math.sin(t)
        x = cx + a * math.copysign(abs(c) ** (2 / n), c)
        y = cy + a * math.copysign(abs(si) ** (2 / n), si)
        (path.moveToPoint_ if i == 0 else path.lineToPoint_)((x, y))
    path.closePath()
    return path


def capsule(x, y, w, h):
    return NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        ((x, y), (w, h)), h / 2, h / 2
    )


def render(size):
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, size, size, 8, 4, True, False, NSCalibratedRGBColorSpace, 0, 0
    )
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(
        NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    )
    s = size / 1024  # design on a 1024 grid; AppKit's y axis points up
    tile = squircle(s)

    # Soft drop shadow under the tile.
    NSGraphicsContext.saveGraphicsState()
    shadow = NSShadow.alloc().init()
    shadow.setShadowOffset_((0, -10 * s))
    shadow.setShadowBlurRadius_(24 * s)
    shadow.setShadowColor_(NSColor.colorWithCalibratedWhite_alpha_(0, 0.45))
    shadow.set()
    rgb(*TILE_BOTTOM).setFill()
    tile.fill()
    NSGraphicsContext.restoreGraphicsState()

    # Espresso body, lighter at the top.
    NSGradient.alloc().initWithStartingColor_endingColor_(
        rgb(*TILE_TOP), rgb(*TILE_BOTTOM)
    ).drawInBezierPath_angle_(tile, -90)

    # Light rim along the top edge, fading out by mid-height.
    NSGraphicsContext.saveGraphicsState()
    NSBezierPath.clipRect_(((0, 600 * s), (1024 * s, 424 * s)))
    NSGradient.alloc().initWithStartingColor_endingColor_(
        NSColor.colorWithCalibratedWhite_alpha_(1, 0.55),
        NSColor.colorWithCalibratedWhite_alpha_(1, 0.0),
    ).drawInBezierPath_angle_(_rim(tile, 5 * s), -90)
    NSGraphicsContext.restoreGraphicsState()

    # Three meters: dim tracks with amber fills.
    left, width = 252 * s, 520 * s
    bar_h, gap = 92 * s, 50 * s
    total = 3 * bar_h + 2 * gap
    top = 520 * s + total / 2  # glyph centre sits slightly below the tile centre
    glyph = NSBezierPath.bezierPath()
    for i, frac in enumerate(FILLS):
        y = top - bar_h - i * (bar_h + gap)
        rgb(*TRACK).setFill()
        capsule(left, y, width, bar_h).fill()
        glyph.appendBezierPath_(capsule(left, y, max(bar_h, width * frac), bar_h))
    NSGradient.alloc().initWithStartingColor_endingColor_(
        rgb(*GLYPH_TOP), rgb(*GLYPH_BOTTOM)
    ).drawInBezierPath_angle_(glyph, -90)

    NSGraphicsContext.restoreGraphicsState()
    return rep


def _rim(path, width):
    """A band `width` thick just inside the edge of a centred tile path."""
    b = path.bounds()
    cx = b.origin.x + b.size.width / 2
    cy = b.origin.y + b.size.height / 2
    t = NSAffineTransform.transform()
    t.translateXBy_yBy_(cx, cy)
    t.scaleBy_((b.size.width - 2 * width) / b.size.width)
    t.translateXBy_yBy_(-cx, -cy)
    band = NSBezierPath.bezierPath()
    band.appendBezierPath_(path)
    band.appendBezierPath_(t.transformBezierPath_(path).bezierPathByReversingPath())
    return band


def png(rep):
    return rep.representationUsingType_properties_(NSPNGFileType, None)


def opaque(rep, size, background=TILE_BOTTOM):
    """Flatten onto a solid colour (apple-touch-icon must not be transparent)."""
    out = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, size, size, 8, 4, True, False, NSCalibratedRGBColorSpace, 0, 0
    )
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(
        NSGraphicsContext.graphicsContextWithBitmapImageRep_(out)
    )
    rgb(*background).setFill()
    NSBezierPath.fillRect_(((0, 0), (size, size)))
    rep.drawInRect_(((0, 0), (size, size)))
    NSGraphicsContext.restoreGraphicsState()
    return out


def main():
    tmp = Path(tempfile.mkdtemp())
    iconset = tmp / "AppIcon.iconset"
    iconset.mkdir()
    for base in (16, 32, 128, 256, 512):
        png(render(base)).writeToFile_atomically_(str(iconset / f"icon_{base}x{base}.png"), True)
        png(render(base * 2)).writeToFile_atomically_(str(iconset / f"icon_{base}x{base}@2x.png"), True)
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(OUT)], check=True)
    shutil.rmtree(tmp)
    png(render(1024)).writeToFile_atomically_(str(HERE / "AppIcon-preview.png"), True)
    print(f"wrote {OUT}")

    if DOCS.is_dir():
        png(render(256)).writeToFile_atomically_(str(DOCS / "icon.png"), True)
        png(render(64)).writeToFile_atomically_(str(DOCS / "favicon.png"), True)
        png(opaque(render(180), 180)).writeToFile_atomically_(str(DOCS / "apple-touch-icon.png"), True)
        print(f"wrote icons in {DOCS}")


if __name__ == "__main__":
    main()
