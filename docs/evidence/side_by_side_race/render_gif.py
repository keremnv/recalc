"""Render the side-by-side race GIF (documentation/evidence only).

Replays the byte-timed captures (see capture.py) frame by frame: output bytes,
timers, and line counts are sampled from the real recordings — nothing is
acted. Skin follows the sibling design-project DNA (gray chrome, Jost + Spline
Sans Mono via vendored TTF conversion, square plates, one spent colour).

Usage: python3 docs/evidence/side_by_side_race/render_gif.py [--font-dir D]
Requires: PIL, fontTools+brotli (woff2->TTF at build time), ffmpeg.
Output: docs/assets/recalc-side-by-side.gif (+ frame PNGs in /tmp/race_frames).
"""
import bisect
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
OUT_GIF = ROOT / "docs" / "assets" / "recalc-side-by-side.gif"
FRAMES = Path("/tmp/race_frames")

FIELD, PLATE, RULE = "#f9f9f9", "#f0f0f0", "#d9d9d9"
INK, MUT, PAPER, JADE = "#202020", "#8d8d8d", "#ffffff", "#208368"
FPS, HOLD_S, TERM_LINES = 12, 2.2, 11
TOTAL_LINES = 3550

PANEL_CMDS = {
    "base": "$ python workload.py",
    "recalc": "$ recalc-agent run --workdir . ./workload.py",
}
PANEL_TITLES = {
    "base": ("BASE — plain Python", "reading + parsing workbook…"),
    "recalc": ("Recalc — warm, DIRECT_RUNTIME", "loading validated state…"),
}


_CMAP = {}


def load_font(name, size, ttf_dir="/tmp/race_fonts"):
    from fontTools.ttLib import TTFont
    path = str(Path(ttf_dir) / name)
    font = ImageFont.truetype(path, size)
    if path not in _CMAP:
        _CMAP[path] = set(TTFont(path).getBestCmap())
    _CMAP[id(font)] = _CMAP[path]
    return font


def _dejavu():
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if p not in _CMAP:
        from fontTools.ttLib import TTFont
        _CMAP[p] = set(TTFont(p).getBestCmap())
    f = ImageFont.truetype(p, 14)
    _CMAP[id(f)] = _CMAP[p]
    return f


def setup_fonts():
    from fontTools.ttLib import TTFont
    d = Path("/tmp/race_fonts")
    d.mkdir(exist_ok=True)
    src = ROOT / "docs/evidence/readme_vignette/fonts"
    for w in ("jost-latin-400-normal.woff2", "jost-latin-600-normal.woff2",
              "spline-sans-mono-latin-400-normal.woff2"):
        out = d / w.replace(".woff2", ".ttf")
        if not out.exists():
            f = TTFont(str(src / w))
            f.flavor = None
            f.save(str(out))


class Arm:
    def __init__(self, tag, wall):
        self.tag = tag
        self.wall = wall
        raw = (HERE / "captures" / f"{tag}.typescript").read_bytes()
        self.body_off = raw.index(b"\n") + 1  # skip `script` header line
        self.raw = raw
        ct, cb, self.times, self.counts = 0.0, 0, [0.0], [0]
        for line in (HERE / "captures" / f"{tag}.timing").read_text().splitlines():
            dt, nb = line.split()
            ct += float(dt)
            cb += int(nb)
            self.times.append(ct)
            self.counts.append(cb)
        self.first_byte_t = float(open(HERE / "captures" / f"{tag}.timing").readline().split()[0])

    def snapshot(self, t):
        """(text_lines_including_partial, newlines_shown, done)."""
        n = self.counts[bisect.bisect_right(self.times, t) - 1]
        chunk = self.raw[self.body_off:self.body_off + n]
        text = chunk.decode("utf-8", errors="ignore").replace("\r\n", "\n")
        if text.endswith("\n"):
            text = text[:-1]
        lines = text.split("\n") if text else []
        done = t >= self.wall
        shown_nl = min(text.count("\n") + (1 if text and not text.endswith("\n") else 0), TOTAL_LINES)
        if done:
            shown_nl = TOTAL_LINES
        return lines, shown_nl, done


def draw_text(draw, xy, text, font, fill, fallback):
    """Draw with per-glyph fallback for symbols Jost/Spline lack (→ ✓ ↓)."""
    x, y = xy
    cmap_p = _CMAP.get(id(font), set())
    fb_cmap = _CMAP.get(id(fallback), set())
    spans = []
    for ch in text:
        f = font if ord(ch) in cmap_p or ord(ch) not in fb_cmap else fallback
        if spans and spans[-1][0] is f:
            spans[-1][1] += ch
        else:
            spans.append([f, ch])
    for f, s in spans:
        draw.text((x, y), s, font=f, fill=fill)
        x += int(draw.textlength(s, font=f))
    return x


def main():
    setup_fonts()
    log = json.loads((HERE / "captures" / "captures.json").read_text())
    bw = log["BASE_selected"]["wall"]
    rw = log["RECALC_selected"]["wall"]
    base, recalc = Arm("base", bw), Arm("recalc", rw)
    # Parity re-check on full outputs (normalized).
    import re as _re
    outs = []
    for a in (base, recalc):
        full = a.raw[a.body_off:]
        full = full[:full.index(b"\nScript done on ")]
        outs.append(_re.sub(rb"0x[0-9a-fA-F]+", b"0xADDR",
                            full.replace(b"\r\n", b"\n")))
    assert outs[0] == outs[1], "arm outputs diverged"
    assert outs[0].count(b"\n") == TOTAL_LINES, "line total changed"

    j400 = load_font("jost-latin-400-normal.ttf", 14)
    j400s = load_font("jost-latin-400-normal.ttf", 13)
    j600 = load_font("jost-latin-600-normal.ttf", 15)
    j600h = load_font("jost-latin-600-normal.ttf", 20)
    j600t = load_font("jost-latin-600-normal.ttf", 26)
    mono = load_font("spline-sans-mono-latin-400-normal.ttf", 13)
    dejavu = _dejavu()

    W = 1000
    PW, GAP, M = 476, 16, 16
    LX, RX = M, M + PW + GAP
    HDR_H, BOT_H = 76, 84
    TERM_LINE_H, TERM_PAD = 18, 10
    TERM_H = TERM_LINES * TERM_LINE_H + 2 * TERM_PAD
    PTITLE_H, CMD_H, STAT_H, TIMER_H = 40, 26, 26, 44
    PANEL_H = PTITLE_H + CMD_H + TERM_H + STAT_H + TIMER_H + 16
    H = M + HDR_H + 12 + PANEL_H + 12 + BOT_H + M

    t_end = max(bw, rw) + HOLD_S
    nframes = int(t_end * FPS) + 1
    FRAMES.mkdir(exist_ok=True)
    for f in FRAMES.glob("f*.png"):
        f.unlink()

    saved = bw - rw
    end_line = "BASE %.2f s \u2192 Recalc %.2f s \u00b7 %.2f s saved" % (bw, rw, saved)

    for fi in range(nframes):
        t = min(fi / FPS, t_end)
        img = Image.new("RGB", (W, H), FIELD)
        dr = ImageDraw.Draw(img)
        dr.rectangle([0, 0, W - 1, H - 1], outline=RULE)
        # Header
        draw_text(dr, (M + 8, M + 6), "Same script, same workbook — recorded live",
                  j600h, INK, dejavu)
        dr.text((M + 8, M + 36), "SpreadsheetBench-2 FM:08_02 · one read-only inspection step · "
                                 "one recorded run per arm", font=j400s, fill=MUT)
        py = M + HDR_H + 12
        both_done = True
        for ax, arm in ((LX, base), (RX, recalc)):
            title, parse_label = PANEL_TITLES[arm.tag]
            lines, shown_nl, done = arm.snapshot(t)
            both_done &= done
            dr.rectangle([ax, py, ax + PW - 1, py + PANEL_H - 1], fill=PLATE, outline=RULE)
            dr.text((ax + 12, py + 10), title, font=j600, fill=INK)
            dr.line([(ax, py + PTITLE_H), (ax + PW, py + PTITLE_H)], fill=RULE)
            dr.text((ax + 12, py + PTITLE_H + 5), PANEL_CMDS[arm.tag], font=mono, fill=MUT)
            ty = py + PTITLE_H + CMD_H + 8
            dr.rectangle([ax + 12, ty, ax + PW - 13, ty + TERM_H - 1], fill=PAPER, outline=RULE)
            vis = lines[-TERM_LINES:] if lines else []
            ly = ty + TERM_PAD
            maxw = PW - 12 - 13 - 16
            for ln in vis:
                full = ln
                while ln and dr.textlength(ln + "…", font=mono) > maxw:
                    ln = ln[:-1]
                if ln != full:
                    ln += "…"
                dr.text((ax + 20, ly), ln, font=mono, fill=INK)
                ly += TERM_LINE_H
            sy = ty + TERM_H + 6
            if done:
                stat, scol = ("done in %.2f s — findings identical" % arm.wall, JADE)
            elif t < arm.first_byte_t:
                stat, scol = (parse_label, MUT)
            else:
                stat, scol = ("streaming findings…", MUT)
            dr.text((ax + 12, sy), stat, font=j400, fill=scol)
            counter = "%s / %s lines" % (f"{shown_nl:,}", f"{TOTAL_LINES:,}")
            dr.text((ax + PW - 13 - dr.textlength(counter, font=j400s), sy), counter,
                    font=j400s, fill=MUT)
            tshow = min(t, arm.wall)
            tstr = "%.2f s" % tshow
            dr.text((ax + 12, sy + TIMER_H - 8), tstr, font=j600t,
                    fill=JADE if done else INK)
        # Bottom band
        by = py + PANEL_H + 12
        dr.rectangle([M, by, W - M - 1, by + BOT_H - 1], fill=PLATE, outline=RULE)
        if both_done:
            draw_text(dr, (M + 16, by + 12), end_line + " · identical findings",
                      load_font("jost-latin-600-normal.ttf", 20), JADE, dejavu)
            dr.text((M + 16, by + 44), "Single recorded runs (median of 3 measured reps each) "
                                       "· local execution", font=j400s, fill=MUT)
        else:
            dr.text((M + 16, by + 16), "Same frozen script + workbook in · identical findings out · "
                                       "timers show real recorded time", font=j400, fill=MUT)
            dr.text((M + 16, by + 42), "Recalc arm: warm cache, DIRECT_RUNTIME, artifact REUSED",
                    font=j400s, fill=MUT)
        img.save(FRAMES / f"f{fi:04d}.png")

    pal = "/tmp/race_palette.png"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS),
                    "-i", str(FRAMES / "f%04d.png"), "-vf", "palettegen=max_colors=128",
                    pal], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS),
                    "-i", str(FRAMES / "f%04d.png"), "-i", pal,
                    "-lavfi", "paletteuse=dither=bayer:bayer_scale=4",
                    str(OUT_GIF)], check=True)
    size = OUT_GIF.stat().st_size
    print(f"frames={nframes} dur={t_end:.2f}s gif={OUT_GIF} ({size // 1024} KiB)")
    print(f"end timers: BASE {bw:.2f}s / Recalc {rw:.2f}s / saved {saved:.2f}s")
    assert nframes == int((max(bw, rw) + HOLD_S) * FPS) + 1
    # Keep review samples.
    for tag, fi in (("first", 0), ("mid", nframes // 3), ("last", nframes - 1)):
        Image.open(FRAMES / f"f{fi:04d}.png").save(f"/tmp/race_{tag}.png")
    print("samples: /tmp/race_first.png /tmp/race_mid.png /tmp/race_last.png")


if __name__ == "__main__":
    main()
