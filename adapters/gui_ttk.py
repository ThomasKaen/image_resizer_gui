import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from typing import List, Optional

from ..core.models import ResizeResult, ResizeOptions
from ..core.io_utils import list_images
from ..core.resize_service import calc_target_size, resize_many

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}

class ImageResizerGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Batch Image Resizer")
        self.root.geometry("760x520")

        # UI state
        self.files: List[str] = []
        self.folder: Optional[str] = None
        self.output_folder: Optional[str] = None

        self.mode = tk.StringVar(value="percent")  # 'percent' | 'dimensions'
        self.percent_val = tk.IntVar(value=50)
        self.width_val = tk.IntVar(value=0)
        self.height_val = tk.IntVar(value=0)
        self.keep_aspect = tk.BooleanVar(value=True)

        self.format_choice = tk.StringVar(value="keep")  # keep | jpg | png | webp
        self.jpg_quality = tk.IntVar(value=85)
        self.append_suffix = tk.BooleanVar(value=True)

        self.status = tk.StringVar(value="Select files or a folder to begin")
        self._build_ui()

    # ---------- UI ----------
    def _build_ui(self):
        top = tk.Frame(self.root); top.pack(fill="x", padx=10, pady=(10,6))
        tk.Label(top, text="Input:").pack(side="left")
        tk.Button(top, text="Choose Files", command=self.choose_files).pack(side="left", padx=5)
        tk.Button(top, text="Choose Folder", command=self.choose_folder).pack(side="left", padx=5)
        self.input_label = tk.Label(top, text="No files selected", anchor="w"); self.input_label.pack(side="left", padx=10)

        out = tk.Frame(self.root); out.pack(fill="x", padx=10, pady=(0,8))
        tk.Label(out, text="Output folder:").pack(side="left")
        tk.Button(out, text="Select", command=self.choose_output).pack(side="left", padx=5)
        self.output_label = tk.Label(out, text="default: creates 'output' next to source", anchor="w"); self.output_label.pack(side="left", padx=10)

        opts = tk.LabelFrame(self.root, text="Resize Options"); opts.pack(fill="x", padx=10, pady=10)
        row = tk.Frame(opts); row.pack(fill="x", pady=4)
        tk.Radiobutton(row, text="Percentage", variable=self.mode, value="percent", command=self._toggle_mode).pack(side="left")
        self.percent_entry = tk.Entry(row, textvariable=self.percent_val, width=6); self.percent_entry.pack(side="left", padx=(6,0))
        tk.Label(row, text="%").pack(side="left", padx=(2,10))
        tk.Radiobutton(row, text="Dimensions (px)", variable=self.mode, value="dimensions", command=self._toggle_mode).pack(side="left", padx=(10,4))
        tk.Label(row, text="Width:").pack(side="left")
        self.width_entry = tk.Entry(row, textvariable=self.width_val, width=6); self.width_entry.pack(side="left", padx=(4,10))
        tk.Label(row, text="Height:").pack(side="left")
        self.height_entry = tk.Entry(row, textvariable=self.height_val, width=6); self.height_entry.pack(side="left", padx=(4,10))
        self.keep_chk = tk.Checkbutton(row, text="Keep aspect ratio", variable=self.keep_aspect); self.keep_chk.pack(side="left", padx=(10,0))

        fmt = tk.LabelFrame(self.root, text="Format & Naming"); fmt.pack(fill="x", padx=10, pady=6)
        fr1 = tk.Frame(fmt); fr1.pack(fill="x", pady=4)
        tk.Label(fr1, text="Output format:").pack(side="left")
        self.format_cb = ttk.Combobox(fr1, textvariable=self.format_choice, values=["keep","jpg","png","webp"], state="readonly", width=7)
        self.format_cb.pack(side="left", padx=(6,10))
        tk.Label(fr1, text="JPEG quality:").pack(side="left")
        self.q_scale = ttk.Scale(fr1, from_=50, to=100, orient="horizontal", command=self._sync_quality_label)
        self.q_scale.set(self.jpg_quality.get()); self.q_scale.pack(side="left", fill="x", expand=True, padx=(6,6))
        self.q_label = tk.Label(fr1, text=str(self.jpg_quality.get())); self.q_label.pack(side="left")
        self.format_cb.bind("<<ComboboxSelected>>", lambda _e: self._toggle_quality_enabled())

        fr2 = tk.Frame(fmt); fr2.pack(fill="x", pady=2)
        self.append_chk = tk.Checkbutton(fr2, text="Append '_resized' to filenames (recommended)", variable=self.append_suffix)
        self.append_chk.pack(side="left")

        actions = tk.Frame(self.root); actions.pack(fill="x", padx=10, pady=(4,6))
        tk.Button(actions, text="Preview", command=self.preview).pack(side="left")
        tk.Button(actions, text="Resize Images", command=self.run).pack(side="left", padx=8)

        self.progress = ttk.Progressbar(self.root, mode="determinate"); self.progress.pack(fill="x", padx=10, pady=(2,4))
        tk.Label(self.root, textvariable=self.status, anchor="w").pack(fill="x", padx=10)
        self.preview_box = tk.Text(self.root, height=12, wrap="none"); self.preview_box.pack(fill="both", expand=True, padx=10, pady=(4,10))

        self._toggle_mode(); self._toggle_quality_enabled()

    def _toggle_mode(self):
        is_pct = (self.mode.get() == "percent")
        self.percent_entry.configure(state="normal" if is_pct else "disabled")
        self.width_entry.configure(state="disabled" if is_pct else "normal")
        self.height_entry.configure(state="disabled" if is_pct else "normal")

    def _toggle_quality_enabled(self):
        # (Keep slider enabled; only matters for JPEG output)
        pass

    def _sync_quality_label(self, _evt=None):
        self.jpg_quality.set(int(float(self.q_scale.get())))
        self.q_label.config(text=str(self.jpg_quality.get()))

    # ---------- inputs ----------
    def choose_files(self):
        paths = filedialog.askopenfilenames(
            title="Select image files",
            filetypes=[("Images", "*.jpg;*.jpeg;*.png;*.webp;*.bmp;*.tiff"), ("All files", "*.*")]
        )
        if paths:
            self.files = list(paths); self.folder = None
            self.input_label.config(text=f"{len(self.files)} files selected")

    def choose_folder(self):
        folder = filedialog.askdirectory(title="Select folder containing images")
        if folder:
            self.folder = folder; self.files = []
            count = len([p for p in list_images(folder)])
            self.input_label.config(text=f"Folder selected ({count} images)")

    def choose_output(self):
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            self.output_folder = folder
            self.output_label.config(text=folder)

    # ---------- actions ----------
    def preview(self):
        files = self._gather_inputs()
        if not files:
            messagebox.showwarning("No images", "Please select files or a folder with images")
            return

        self.preview_box.delete("1.0", tk.END)
        self.preview_box.insert(tk.END, f"Selected {len(files)} images.\n\nTarget sizes (first 10):\n")

        mode = self.mode.get()
        pct = _safe_float(self.percent_val.get(), default=50.0)
        w = _safe_int(self.width_val.get())
        h = _safe_int(self.height_val.get())
        keep = self.keep_aspect.get()

        for fp in files[:10]:
            try:
                from PIL import Image  # safe import here for preview metadata only
                with Image.open(fp) as im:
                    sw, sh = im.size
                tw, th = calc_target_size(sw, sh, ResizeOptions(mode=mode, percent=pct, width_px=w, height_px=h, keep_aspect=keep))
                self.preview_box.insert(tk.END, f"- {os.path.basename(fp)} ({sw}x{sh}) -> ({tw}x{th})\n")
            except Exception as e:
                self.preview_box.insert(tk.END, f"- {os.path.basename(fp)} [error: {e}]\n")

        self.status.set("Preview generated. Ready to resize.")

    def run(self):
        files = self._gather_inputs()
        if not files:
            messagebox.showwarning("No images", "Please select files or a folder with images")
            return

        # default output = '<source>/output'
        out = self.output_folder
        if not out:
            base_root = os.path.dirname(files[0]) if self.files else (self.folder or os.getcwd())
            out = os.path.join(base_root, "output")
        os.makedirs(out, exist_ok=True)

        opts = ResizeOptions(
            mode=self.mode.get(),
            percent=_safe_float(self.percent_val.get(), default=50.0),
            width_px=_safe_int(self.width_val.get()),
            height_px=_safe_int(self.height_val.get()),
            keep_aspect=self.keep_aspect.get(),
            format_choice=self.format_choice.get(),
            append_suffix=self.append_suffix.get(),
            jpg_quality=int(self.jpg_quality.get()),
        )

        self.progress.configure(value=0, maximum=len(files))
        t = threading.Thread(target=self._worker, args=(files, out, opts), daemon=True)
        t.start()

    def _worker(self, files: List[str], out: str, opts: ResizeOptions):
        ok = err = 0

        def on_progress(done: int, total: int):
            self.progress.configure(value=done)
            self.root.update_idletasks()

        def on_log(msg: str):
            self._append(msg)

        for res in resize_many(files, out, opts, progress=on_progress, log=on_log):
            if isinstance(res, ResizeResult) and res.ok:
                ok += 1
            else:
                err += 1

        self.status.set(f"Done. Success: {ok}, Errors: {err}. Output: {out}")
        self._append(f"\nFinished.\nSuccess: {ok}\nErrors: {err}\nOutput: {out}")

    # ---------- helpers ----------
    def _gather_inputs(self) -> List[str]:
        if self.files:
            return [f for f in self.files if os.path.splitext(f)[1].lower() in SUPPORTED_EXTS]
        if self.folder:
            return list(list_images(self.folder))
        return []

    def _append(self, text: str):
        self.preview_box.insert(tk.END, text + "\n"); self.preview_box.see(tk.END)


def _safe_int(v):
    try:
        return int(str(v).strip())
    except Exception:
        return None

def _safe_float(v, default):
    try:
        return float(str(v).strip())
    except Exception:
        return default


def main():
    root = tk.Tk()
    ImageResizerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()