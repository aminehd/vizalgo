"""
InteractiveRenderer — local step-through viewer using Tkinter + Pillow.
No new dependencies: tkinter is stdlib, Pillow already installed.

Controls:
  → / Space / Click Next  — next snapshot
  ←           / Click Prev  — previous snapshot
  Home                     — first snapshot
  End                       — last snapshot
  Escape / Q               — quit
"""

import tkinter as tk
from PIL import ImageTk

from . import BaseRenderer
from .pillow import IslandsPillowRenderer   # reuse existing frame renderer


class InteractiveRenderer(BaseRenderer):
    """Step-through viewer. Reuses IslandsPillowRenderer for each frame."""

    def __init__(self, frame_renderer=None, scale: float = 1.0):
        # Default to islands renderer; swap for any other PillowRenderer subclass
        self.frame_renderer = frame_renderer or IslandsPillowRenderer()
        self.scale          = scale   # shrink for smaller screens, e.g. 0.7

    def render(self, snapshots: list, output: str = None, **meta):
        if not snapshots:
            print("No snapshots to display.")
            return

        # Pre-render all frames to PIL Images
        print(f"  Rendering {len(snapshots)} frames for interactive viewer...")
        total   = len(snapshots)
        problem = meta.get("problem", "")
        title   = meta.get("title", "")
        source  = meta.get("source_lines", [])
        self.frame_renderer._source = source

        images = []
        for i, snap in enumerate(snapshots):
            img = self.frame_renderer.render_frame(snap, i, total, problem, title)
            if self.scale != 1.0:
                w = int(img.width  * self.scale)
                h = int(img.height * self.scale)
                img = img.resize((w, h))
            images.append(img)
            print(f"  pre-render {i+1}/{total}", end="\r", flush=True)
        print()

        self._run_viewer(images, snapshots, title or problem)

    def _run_viewer(self, images, snapshots, title):
        root = tk.Tk()
        root.title(f"vizalgo — {title}")
        root.configure(bg="#080a12")
        root.resizable(False, False)

        img_w, img_h = images[0].width, images[0].height

        # ── Canvas ──────────────────────────────────────────────────────────
        canvas = tk.Canvas(root, width=img_w, height=img_h,
                           bg="#080a12", highlightthickness=0)
        canvas.pack()

        # ── Controls bar ────────────────────────────────────────────────────
        ctrl = tk.Frame(root, bg="#0e1020", pady=6)
        ctrl.pack(fill="x")

        btn_style = dict(bg="#1a2040", fg="#e0e8ff", activebackground="#2a3060",
                         activeforeground="#00e6e6", relief="flat",
                         font=("Menlo", 13), padx=16, pady=4, cursor="hand2")

        btn_prev  = tk.Button(ctrl, text="◀  Prev",  **btn_style)
        btn_next  = tk.Button(ctrl, text="Next  ▶",  **btn_style)
        btn_reset = tk.Button(ctrl, text="⟳  Reset", **btn_style)
        lbl_step = tk.Label(ctrl, text="", bg="#0e1020", fg="#6070a0",
                            font=("Menlo", 12))
        lbl_desc = tk.Label(ctrl, text="", bg="#0e1020", fg="#c0d0ff",
                            font=("Menlo", 12), wraplength=img_w - 40)

        btn_prev.pack(side="left",   padx=12)
        btn_next.pack(side="right",  padx=12)
        btn_reset.pack(side="right", padx=4)
        lbl_step.pack(side="left",  padx=20)
        lbl_desc.pack(side="left",  expand=True)

        # ── State ────────────────────────────────────────────────────────────
        state = {"idx": 0}
        tk_images = [ImageTk.PhotoImage(img) for img in images]
        canvas_img = canvas.create_image(0, 0, anchor="nw", image=tk_images[0])

        def show(idx):
            idx = max(0, min(len(images) - 1, idx))
            state["idx"] = idx
            canvas.itemconfig(canvas_img, image=tk_images[idx])
            snap = snapshots[idx]
            lbl_step.config(text=f"Step {idx + 1} / {len(images)}")
            lbl_desc.config(text=snap.description or "")
            btn_prev.config(state="normal" if idx > 0 else "disabled")
            btn_next.config(state="normal" if idx < len(images) - 1 else "disabled")

        def next_snap(_=None):  show(state["idx"] + 1)
        def prev_snap(_=None):  show(state["idx"] - 1)
        def reset_snap(_=None): show(0)

        btn_next.config(command=next_snap)
        btn_prev.config(command=prev_snap)
        btn_reset.config(command=reset_snap)

        root.bind("<Right>",  next_snap)
        root.bind("<space>",  next_snap)
        root.bind("<Left>",   prev_snap)
        root.bind("<Home>",   reset_snap)
        root.bind("<End>",    lambda _: show(len(images) - 1))
        root.bind("<Escape>", lambda _: root.destroy())
        root.bind("q",        lambda _: root.destroy())

        show(0)
        root.mainloop()
