"""
IslandsPillowRenderer — Pillow + ffmpeg renderer for islands-grid problems (LC 200 style).

Visual aesthetic: neon glow, CRT scanlines, dark BG, per-island accent colors.
Output: H.264 MP4, 1920x1080, CRF 18.
"""
import os
import subprocess
from math import sin, pi

from PIL import Image, ImageDraw, ImageFont

from . import BaseRenderer
from ..core.event import Snapshot

# ──────────────────────────────────────────────
#  DESIGN CONSTANTS
# ──────────────────────────────────────────────

IMG_W = 1920
IMG_H = 1080
FPS   = 30

BG        = (8,  10,  18)
BG_PANEL  = (18, 20,  32)
BG_HEADER = (14, 16,  26)
GRID_LINE = (32, 36,  50)

WHITE  = (230, 230, 240)
GRAY   = (100, 105, 120)
DIM    = (55,  58,  72)
CYAN   = (70,  215, 235)
GREEN  = (70,  215, 110)
YELLOW = (255, 215, 50)
BLUE   = (70,  135, 255)
ORANGE = (255, 150, 50)

# Cell state integer codes
WATER    = 0
LAND     = 1
VISITING = 2

CELL_FILL = {
    WATER:    (10,  20,  40),
    LAND:     (40,  180, 80),
    VISITING: (255, 200, 50),
}
CELL_BORDER = {
    WATER:    (20,  40,  80),
    LAND:     (60,  210, 100),
    VISITING: (255, 235, 100),
}

ISLAND_PALETTE = [
    (50,  200, 255),   # island 0 — cyan-blue
    (255, 140, 30),    # island 1 — amber
    (180, 80,  255),   # island 2 — violet
    (0,   230, 180),   # island 3 — teal
]
ISLAND_BORDER_PALETTE = [
    (100, 230, 255),
    (255, 180, 80),
    (210, 120, 255),
    (50,  255, 200),
]


# ──────────────────────────────────────────────
#  HELPERS
# ──────────────────────────────────────────────

def _cell_fill(state):
    if state in CELL_FILL:
        return CELL_FILL[state]
    if state >= 10:
        return ISLAND_PALETTE[(state - 10) % len(ISLAND_PALETTE)]
    return CELL_FILL[WATER]


def _cell_border(state):
    if state in CELL_BORDER:
        return CELL_BORDER[state]
    if state >= 10:
        return ISLAND_BORDER_PALETTE[(state - 10) % len(ISLAND_BORDER_PALETTE)]
    return CELL_BORDER[WATER]


def _lerp(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def _bell(t):
    return sin(max(0.0, min(1.0, t)) * pi)


def _load_font(size, bold=False):
    paths = [
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/SFMono-Regular.otf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                idx = 1 if bold else 0
                return ImageFont.truetype(p, size, index=idx)
            except Exception:
                pass
    return ImageFont.load_default()


# ──────────────────────────────────────────────
#  DRAW PRIMITIVES
# ──────────────────────────────────────────────

def _rrect(draw, bbox, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(bbox, radius=radius, fill=fill, outline=outline, width=width)


def _draw_cell(draw, x, y, size, state):
    """Draw a single grid cell with optional neon glow."""
    fill   = _cell_fill(state)
    border = _cell_border(state)

    # Neon glow for visiting and island cells
    if state == VISITING:
        for g in range(6, 0, -1):
            gc = _lerp(BG, (255, 235, 80), g / 8)
            pad = g * 3
            draw.rounded_rectangle(
                [x - pad, y - pad, x + size + pad, y + size + pad],
                radius=5 + pad, outline=gc, width=2
            )
    elif state >= 10:
        idx = (state - 10) % len(ISLAND_PALETTE)
        glow_col = ISLAND_PALETTE[idx]
        for g in range(3, 0, -1):
            gc = _lerp(BG, glow_col, g / 6)
            pad = g * 2
            draw.rounded_rectangle(
                [x - pad, y - pad, x + size + pad, y + size + pad],
                radius=5 + pad, outline=gc, width=1
            )

    draw.rounded_rectangle([x, y, x + size, y + size],
                           radius=5, fill=fill, outline=border, width=2)

    cx, cy = x + size // 2, y + size // 2

    # Icons inside cell
    if state == LAND:
        mh = max(5, size // 5)
        mw = max(7, size // 4)
        pts = [(cx, cy - mh), (cx - mw, cy + mh // 2), (cx + mw, cy + mh // 2)]
        draw.polygon(pts, fill=(65, 210, 95), outline=(90, 240, 120))
    elif state == VISITING:
        r = max(3, size // 8)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 240, 100))
    elif state >= 10:
        r = max(4, size // 7)
        idx = (state - 10) % len(ISLAND_PALETTE)
        c_inner = tuple(min(255, v + 60) for v in ISLAND_PALETTE[idx])
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c_inner)


def _apply_scanlines(img):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for y in range(0, img.size[1], 3):
        d.line([(0, y), (img.size[0], y)], fill=(0, 0, 0, 28))
    base = img.convert("RGBA")
    base.alpha_composite(overlay)
    return base.convert("RGB")


# ──────────────────────────────────────────────
#  PANEL DRAW FUNCTIONS
# ──────────────────────────────────────────────

def _draw_grid_panel(draw, x, y, w, h, grid, font_sm, font_xs):
    _rrect(draw, (x, y, x + w, y + h), 8, BG_PANEL, GRID_LINE, 1)
    draw.text((x + 12, y + 8), "ISLAND GRID", fill=GREEN, font=font_sm)

    rows = len(grid)
    cols = len(grid[0]) if rows > 0 else 0
    if rows == 0 or cols == 0:
        return

    avail_w   = w - 50
    avail_h   = h - 50
    cell_size = min(avail_w // cols, avail_h // rows, 90)
    cell_gap  = 4

    total_w = cols * (cell_size + cell_gap) - cell_gap
    total_h = rows * (cell_size + cell_gap) - cell_gap
    gx0     = x + (w - total_w) // 2
    gy0     = y + 32 + (h - 32 - total_h) // 2

    for r in range(rows):
        for c in range(cols):
            cx = gx0 + c * (cell_size + cell_gap)
            cy = gy0 + r * (cell_size + cell_gap)
            _draw_cell(draw, cx, cy, cell_size, grid[r][c])

    # Row/col coordinate labels
    for r in range(rows):
        cy = gy0 + r * (cell_size + cell_gap) + cell_size // 2
        draw.text((gx0 - 20, cy - 6), str(r), fill=DIM, font=font_xs)
    for c in range(cols):
        cx = gx0 + c * (cell_size + cell_gap) + cell_size // 2
        draw.text((cx - 3, gy0 - 16), str(c), fill=DIM, font=font_xs)


def _draw_queue_panel(draw, x, y, w, h, queue_contents, font, font_sm):
    _rrect(draw, (x, y, x + w, y + h), 8, BG_PANEL, GRID_LINE, 1)
    draw.text((x + 12, y + 8), "QUEUE  (BFS FRONTIER)", fill=CYAN, font=font_sm)

    box_w        = 80
    box_h        = 44
    arrow_w      = 16
    gap          = arrow_w + 4
    qx           = x + 14
    qy           = y + 32
    items_per_row = max(1, (w - 20) // (box_w + gap))
    visible       = queue_contents[: items_per_row * 2]

    for i, item in enumerate(visible):
        row_idx = i // items_per_row
        col_idx = i % items_per_row
        bx = qx + col_idx * (box_w + gap)
        by = qy + row_idx * (box_h + 10)
        if by + box_h > y + h - 6:
            break

        is_front   = (i == 0)
        fill_col   = (28, 95, 195) if is_front else (18, 60, 125)
        border_col = (75, 175, 255) if is_front else BLUE

        if is_front:
            for g in range(3, 0, -1):
                gc = _lerp(BG, (75, 175, 255), g / 5)
                draw.rounded_rectangle(
                    [bx - g, by - g, bx + box_w + g, by + box_h + g],
                    radius=6 + g, outline=gc, width=1
                )

        draw.rounded_rectangle([bx, by, bx + box_w, by + box_h],
                               radius=6, fill=fill_col, outline=border_col, width=2)

        if is_front:
            draw.text((bx + 4, by + 2), "FRONT", fill=(75, 195, 255), font=font_sm)

        # Render item — support tuples or scalars
        if isinstance(item, (tuple, list)):
            text = "(" + ", ".join(str(v) for v in item) + ")"
        else:
            text = str(item)

        bb   = draw.textbbox((0, 0), text, font=font)
        tw   = bb[2] - bb[0]
        th   = bb[3] - bb[1]
        ty   = by + (box_h - th) // 2 + (6 if is_front else 0)
        draw.text((bx + box_w // 2 - tw // 2, ty), text, fill=WHITE, font=font)

        if i < len(visible) - 1 and (i + 1) % items_per_row != 0:
            ax = bx + box_w + 4
            ay = by + box_h // 2
            draw.text((ax, ay - 8), "→", fill=BLUE, font=font)

    if not queue_contents:
        draw.text((qx, qy + 10), "(empty)", fill=DIM, font=font)


def _draw_stats_panel(draw, x, y, w, h, count, queue_size, desc, font, font_sm, font_lg):
    _rrect(draw, (x, y, x + w, y + h), 8, BG_PANEL, GRID_LINE, 1)
    draw.text((x + 12, y + 8), "STATUS", fill=CYAN, font=font_sm)

    entries = [
        ("Islands Found", str(count),      GREEN  if count > 0 else GRAY),
        ("Queue Size",    str(queue_size),  CYAN),
    ]

    sy = y + 34
    for label, val, color in entries:
        draw.text((x + 14, sy), label + ":", fill=GRAY,  font=font_sm)
        sy += 20
        draw.text((x + 22, sy), val,         fill=color, font=font_lg)
        sy += 36

    # Step description
    if sy + 30 < y + h - 6:
        draw.text((x + 14, sy), "Step:", fill=GRAY, font=font_sm)
        sy += 20
        # Word-wrap description
        words   = desc.split()
        line    = ""
        line_h  = 18
        max_px  = w - 28
        for word in words:
            test = (line + " " + word).strip()
            bb   = draw.textbbox((0, 0), test, font=font_sm)
            if bb[2] - bb[0] <= max_px:
                line = test
            else:
                if line and sy + line_h < y + h - 6:
                    draw.text((x + 14, sy), line, fill=WHITE, font=font_sm)
                    sy += line_h
                line = word
        if line and sy + line_h < y + h - 6:
            draw.text((x + 14, sy), line, fill=WHITE, font=font_sm)


def _draw_code_panel(draw, x, y, w, h, source_lines, current_line, font_code, font_sm):
    """Syntax-highlighted code panel with sliding highlight bar."""
    _rrect(draw, (x, y, x + w, y + h), 8, BG_PANEL, GRID_LINE, 1)
    draw.text((x + 12, y + 8), "CODE", fill=CYAN, font=font_sm)

    # Token colors
    import re
    KW   = (190, 120, 255)
    BLT  = (80,  190, 255)
    NUM  = (255, 200, 70)
    OP   = (80,  230, 220)
    STR  = (80,  200, 110)
    CMT  = (80,  140, 80)
    _KW  = {"def","return","if","else","elif","for","while","in","not","and","or",
             "True","False","None","import","from","as","class","with","yield","nonlocal"}
    _BLT = {"len","range","print","int","str","list","dict","set","min","max","enumerate","zip"}
    _TOK = re.compile(
        r'(#[^\n]*|"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|'
        r'\b(?:def|return|if|else|elif|for|while|in|not|and|or|True|False|None|import|from|as|class|with|yield|nonlocal)\b|'
        r'\b(?:len|range|print|int|str|list|dict|set|min|max|enumerate|zip)\b|'
        r'\b\d+\b|[+\-*/=<>!&|%^~]+|.)'
    )

    def tokenize(text):
        tokens = []
        for m in _TOK.finditer(text):
            t = m.group()
            if t.startswith('#'):            c = CMT
            elif t.startswith('"') or t.startswith("'"): c = STR
            elif t in _KW:                  c = KW
            elif t in _BLT:                 c = BLT
            elif t.isdigit():               c = NUM
            elif re.match(r'^[+\-*/=<>!&|%^~]+$', t): c = OP
            else:                           c = WHITE
            tokens.append((t, c))
        return tokens

    line_h   = 22
    pad_x    = 14
    code_top = y + 30
    visible  = max(1, (h - 36) // line_h)

    # Center visible window around current line
    total = len(source_lines)
    half  = visible // 2
    start = max(0, min(current_line - half, total - visible))
    end   = min(total, start + visible)

    # Highlight bar
    hi_y = code_top + (current_line - start) * line_h - 2
    if 0 <= current_line - start < visible:
        draw.rounded_rectangle(
            [x + 4, hi_y, x + w - 4, hi_y + line_h],
            radius=4, fill=(30, 45, 70)
        )
        # Neon left edge
        draw.rounded_rectangle(
            [x + 4, hi_y, x + 10, hi_y + line_h],
            radius=2, fill=CYAN
        )

    for i, li in enumerate(range(start, end)):
        ly   = code_top + i * line_h
        line = source_lines[li] if li < len(source_lines) else ""

        # Line number + pointer
        lnum_color = CYAN if li == current_line else DIM
        draw.text((x + pad_x, ly + 2), f"{li+1:3d}", fill=lnum_color, font=font_code)
        if li == current_line:
            draw.text((x + pad_x + 36, ly + 2), "►", fill=CYAN, font=font_code)

        # Tokenized code
        cx = x + pad_x + 58
        for tok, col in tokenize(line.rstrip()):
            if cx > x + w - 8:
                break
            tc = YELLOW if li == current_line and col == WHITE else col
            draw.text((cx, ly + 2), tok, fill=tc, font=font_code)
            try:
                bb = draw.textbbox((0, 0), tok, font=font_code)
                cx += bb[2] - bb[0]
            except Exception:
                cx += len(tok) * 10


def _draw_legend(draw, x, y, w, h, font_xs):
    _rrect(draw, (x, y, x + w, y + h), 8, BG_PANEL, GRID_LINE, 1)
    items = [
        (CELL_FILL[WATER],    "Water"),
        (CELL_FILL[LAND],     "Unvisited Land"),
        (CELL_FILL[VISITING], "Visiting (BFS)"),
        (ISLAND_PALETTE[0],   "Island 1"),
        (ISLAND_PALETTE[1],   "Island 2"),
        (ISLAND_PALETTE[2],   "Island 3"),
        (ISLAND_PALETTE[3],   "Island 4"),
    ]
    lx = x + 16
    ly = y + (h - 18) // 2
    for color, label in items:
        draw.rounded_rectangle([lx, ly, lx + 18, ly + 18], radius=3, fill=color)
        draw.text((lx + 24, ly + 1), label, fill=GRAY, font=font_xs)
        lx += 155


# ──────────────────────────────────────────────
#  RENDERER CLASS
# ──────────────────────────────────────────────

class IslandsPillowRenderer(BaseRenderer):
    """Pillow + ffmpeg renderer for LC 200 Number of Islands."""

    def render(self, snapshots: list, output: str, **meta):
        problem      = meta.get("problem", "")
        title        = meta.get("title", "")
        self._source = meta.get("source_lines", [])

        os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)

        # Launch ffmpeg process to receive rawvideo frames via stdin
        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{IMG_W}x{IMG_H}",
            "-pix_fmt", "rgb24",
            "-r", str(FPS),
            "-i", "pipe:0",
            "-vcodec", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "18",
            output,
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        total = len(snapshots)
        for i, snap in enumerate(snapshots):
            img = self.render_frame(snap, i, total, problem, title)
            raw = img.tobytes()
            n_frames = max(1, round(snap.duration * FPS))
            for _ in range(n_frames):
                proc.stdin.write(raw)

            print(f"  frame {i+1}/{total}", end="\r", flush=True)

        proc.stdin.close()
        proc.wait()
        print(f"\nSaved -> {output}")

    def render_frame(self, snapshot: Snapshot, frame_idx: int = 0,
                     total_frames: int = 1,
                     problem: str = "", title: str = "") -> Image.Image:
        img  = Image.new("RGB", (IMG_W, IMG_H), BG)
        draw = ImageDraw.Draw(img)

        font_lg   = _load_font(28, bold=True)
        font_md   = _load_font(20)
        font_sm   = _load_font(16)
        font_xs   = _load_font(13)
        font_code = _load_font(17)

        data  = snapshot.data
        grid  = data.get("grid", [[]])
        queue = data.get("queue", [])
        count = data.get("count", 0)
        desc  = snapshot.description
        line  = snapshot.line

        # ── Header ──────────────────────────────────
        draw.rectangle([0, 0, IMG_W, 54], fill=BG_HEADER)
        header_text = f"{problem} — {title}" if problem and title else (title or problem)
        draw.text((18, 14), header_text, fill=GREEN, font=font_lg)
        draw.text((IMG_W - 220, 18), f"Frame {frame_idx+1}/{total_frames}", fill=GRAY, font=font_sm)

        draw.rectangle([0, 54, IMG_W, 90], fill=(14, 18, 28))
        draw.rectangle([0, 54, 6, 90], fill=CYAN)
        draw.text((16, 64), desc, fill=WHITE, font=font_md)

        # ── Layout ──────────────────────────────────
        margin = 12
        top    = 96
        bottom = IMG_H - 70

        left_w  = int(IMG_W * 0.52)
        right_x = left_w + margin * 2
        right_w = IMG_W - right_x - margin
        col_h   = bottom - top

        # Grid — full left
        _draw_grid_panel(draw, margin, top, left_w, col_h, grid, font_sm, font_xs)

        # Code panel — top 60% of right
        code_h  = int(col_h * 0.60)
        source  = getattr(self, "_source", [])
        _draw_code_panel(draw, right_x, top, right_w, code_h, source, line, font_code, font_sm)

        # Queue — next 22%
        queue_y = top + code_h + margin
        queue_h = int(col_h * 0.22)
        _draw_queue_panel(draw, right_x, queue_y, right_w, queue_h, queue, font_sm, font_xs)

        # Stats — remaining
        stats_y = queue_y + queue_h + margin
        stats_h = bottom - stats_y
        _draw_stats_panel(draw, right_x, stats_y, right_w, stats_h,
                          count, len(queue), desc, font_sm, font_xs, font_md)

        # Legend
        legend_y = bottom + 4
        _draw_legend(draw, margin, legend_y, IMG_W - margin * 2,
                     IMG_H - legend_y - 4, font_xs)

        return _apply_scanlines(img)
