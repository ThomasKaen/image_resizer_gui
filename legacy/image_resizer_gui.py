import os
import sys
import math
import threading
import tkinter as tk
from email.policy import default
from tkinter import ttk, filedialog, messagebox
from typing import List, Iterable, Tuple, Optional

try:
    from PIL import Image
except ImportError:
    messagebox.showerror(
        "Missing dependency",
        "Pillow (PIL) is required.\n\nInstall with:\n\npip install pillow"
    )
    raise  SystemExit(1)

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}

EXT_TO_PIL = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
    "bmp": "BMP",
    "tiff": "TIFF",
}

# ------------ #
# ----Core---- #
# ------------ #

def list_images_in_folder(folder: str) -> List[str]:
    """Recursively list supported images in a folder."""
    out: List[str] = []
    for root, _, names in os.walk(folder):
        for n in names:
            if os.path.splitext(n)[1] in SUPPORTED_EXTS:
                out.append(os.path.join(root, n))
    return out

def gather_inputs(files: Iterable[str], folder: Optional[str]) -> List[str]:
    """Combine explicit files and/or a folder's images into a final list"""
    if files:
        valid = [
            f for f in files
            if os.path.splitext(f)[1].lower() in SUPPORTED_EXTS
        ]
        return valid
    if folder:
        return list_images_in_folder(folder)
    return []

def calc_target_size(
    src_w: int,
    src_h: int,
    mode: str,                 # 'percent' | 'dimensions'
    percent: float = 50.0,
    width_px: Optional[int] = None,
    height_px: Optional[int] = None,
    keep_aspect: bool = True
) -> Tuple[Optional[int], Optional[int]]:
    """Decide target width/height based on requested mode."""
    if mode == "percent":
        pct = max(1.0, percent)
        tw = max(1, int(round(src_w * (pct / 100.0))))
        th = max(1, int(round(src_h * (pct / 100.0))))
        return tw, th

    # dimensions mode
    w, h = width_px, height_px
    if keep_aspect:
        if w and not h:
            scale = w / float(src_w)
            return w, max(1, int(round(src_h * scale)))
        if h and not w:
            scale = h / float(src_h)
            return max(1, int(round(src_w * scale))), h
        if w and h:
            scale = min(w / float(src_w), h / float(src_h))
            return max(1, int(round(src_w * scale))), max(1, int(round(src_h * scale)))
        return src_w, src_h # nothing provided
    else:
        return (w or src_w), (h or src_h)

def next_available_name(path: str) -> str:
    """If path exists, append _2, _3, ... to avoid override"""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    n = 2
    while True:
        candidate = f"{base}_{n}{ext}"
        if not os.path.exists(candidate):
            return candidate
        n += 1

def save_image(im: Image.Image, dst: str, pil_format: str, jpg_quality: int) -> None:
        """
        Save image with chose format/quality
        fmt_choice: 'keep' | 'jpg' | 'png' | 'webp'
        """
        if pil_format == "JPEG" and im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGB")

        save_kwargs = {}
        if pil_format == "JPEG":
            save_kwargs["quality"] = int(jpg_quality)
            save_kwargs["optimize"] = True

        im.save(dst, format=pil_format, **save_kwargs)

def resize_one(
        src_path: str,
        out_folder: str,
        mode: str,
        percent: float,
        width_px: Optional[int],
        height_px: Optional[int],
        keep_aspect: bool,
        format_choice: str, # keep, jpg, png, webp
        append_suffix: bool,
        jpg_quality: int,
) -> Tuple[int, int]:
    """
    Resize a single image. Returns (success, message_or_error).
    On success, message is output path; on failure, it's an error string.
    """
    try:
        with Image.open(src_path) as im:
            src_w, src_h = im.size
            tw, th = calc_target_size(src_w, src_h, mode, percent, width_px, height_px, keep_aspect)

            # pick resample: LANCZOS for downscale, BICUBIC otherwise
            if (tw, th) != (src_w, src_h):
                resample = Image.LANCZOS if (tw < src_w or th < src_h) else Image.BICUBIC
                im = im.resize((tw, th), resample=resample)

            base = os.path.splitext(os.path.basename(src_path))[0]
            in_ext = os.path.splitext(src_path)[1].lower().lstrip(".")
            out_ext = in_ext if format_choice == "keep" else format_choice
            pil_fmt = EXT_TO_PIL.get(out_ext)
            if not pil_fmt:
                return False, f"{os.path.basename(src_path)} -> unknown file extension: .{out_ext}"

            out_name = f"{base}{'_resized' if append_suffix else ''}.{out_ext}"
            dst = os.path.join(out_folder, out_name)

            if append_suffix:
                dst = next_available_name(dst)

            save_image(im, dst, pil_fmt, jpg_quality)
            return True, dst

    except Exception as e:
        return False, f"{os.path.basename(src_path)} -> {e}"

# --------- #
# ---GUI--- #
# --------- #

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Batch Image Resizer")
        self.root.geometry("760x520")

        # UI state
        self.files: List[str] = []
        self.folder: Optional[str] = None
        self.output_folder: Optional[str] = None

        self.mode = tk.StringVar(value="percent") # percent or dimension
        self.percent_val = tk.IntVar(value=50)
        self.width_val = tk.IntVar(value=0)
        self.height_val = tk.IntVar(value=0)
        self.keep_aspect = tk.BooleanVar(value=True)

        self.format_choice = tk.StringVar(value="keep") # keep or ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"
        self.jpg_quality = tk.IntVar(value=85)
        self.append_suffix = tk.BooleanVar(value=True) #append _resized

        self.status = tk.StringVar(value="Select files or a folder to begin")

        self._build_ui()

    #--- UI ---
    def _build_ui(self):
        # Inputs
        top = tk.Frame(self.root)
        top.pack(fill="x", padx=10, pady=(10,6))

        tk.Label(top, text="Input:").pack(side="left")
        tk.Button(top, text="Choose Files", command=self.choose_files).pack(side="left", padx=5)
        tk.Button(top, text="Choose Folder", command=self.choose_folder).pack(side="left", padx=5)

        self.input_label = tk.Label(top, text="No files selected", anchor="w")
        self.input_label.pack(side="left", padx=10)

        # Output
        out = tk.Frame(self.root)
        out.pack(fill="x", padx=10, pady=(0,8))
        tk.Label(out, text="Output folder:").pack(side="left")
        tk.Button(out, text="Select", command=self.choose_output).pack(side="left", padx=5)
        self.output_label = tk.Label(out, text="default: creates 'output' in source", anchor="w")
        self.output_label.pack(side="left", padx=10)

        # Options: size
        opts = tk.LabelFrame(self.root, text="Resize Options"); opts.pack(fill="x", padx=10,pady=10)
        row = tk.Frame(opts); row.pack(fill="x", pady=4)
        tk.Radiobutton(row, text="Percentage", variable=self.mode, value="percent",
                       command=self._toggle_mode).pack(side="left")
        self.percent_entry = tk.Entry(row, textvariable=self.percent_val, width=6);
        self.percent_entry.pack(side="left", padx=(6, 0))
        tk.Label(row, text="%").pack(side="left", padx=(2, 10))

        tk.Radiobutton(row, text="Dimensions (px)", variable=self.mode, value="dimensions",
                       command=self._toggle_mode).pack(side="left", padx=(10, 4))
        tk.Label(row, text="Width:").pack(side="left")
        self.width_entry = tk.Entry(row, textvariable=self.width_val, width=6);
        self.width_entry.pack(side="left", padx=(4, 10))
        tk.Label(row, text="Height:").pack(side="left")
        self.height_entry = tk.Entry(row, textvariable=self.height_val, width=6);
        self.height_entry.pack(side="left", padx=(4, 10))
        self.keep_chk = tk.Checkbutton(row, text="Keep aspect ratio", variable=self.keep_aspect);
        self.keep_chk.pack(side="left", padx=(10, 0))

        # Options: format
        fmt = tk.LabelFrame(self.root, text="Format & Naming");
        fmt.pack(fill="x", padx=10, pady=6)
        fr1 = tk.Frame(fmt);
        fr1.pack(fill="x", pady=4)
        tk.Label(fr1, text="Output format:").pack(side="left")
        self.format_cb = ttk.Combobox(fr1, textvariable=self.format_choice,
                                      values=["keep", "jpg", "png", "webp"],
                                      state="readonly", width=7)
        self.format_cb.pack(side="left", padx=(6, 10))
        tk.Label(fr1, text="JPEG quality:").pack(side="left")

        self.q_scale = ttk.Scale(fr1, from_=50, to=100, orient="horizontal")
        self.q_scale.set(self.jpg_quality.get())
        self.q_scale.pack(side="left", fill="x", expand=True, padx=(6, 6))

        self.q_label = tk.Label(fr1, text=str(self.jpg_quality.get()));
        self.q_label.pack(side="left")

        self.q_scale.configure(command=self._sync_quality_label)

        fr2 = tk.Frame(fmt);
        fr2.pack(fill="x", pady=2)
        self.append_chk = tk.Checkbutton(fr2, text="Append '_resized' to filenames (recommended)",
                                         variable=self.append_suffix)
        self.append_chk.pack(side="left")

        # Actions
        actions = tk.Frame(self.root);
        actions.pack(fill="x", padx=10, pady=(4, 6))
        tk.Button(actions, text="Preview", command=self.preview).pack(side="left")
        tk.Button(actions, text="Resize Images", command=self.run).pack(side="left", padx=8)

        # Progress + status + preview area
        self.progress = ttk.Progressbar(self.root, mode="determinate");
        self.progress.pack(fill="x", padx=10, pady=(2, 4))
        tk.Label(self.root, textvariable=self.status, anchor="w").pack(fill="x", padx=10)
        self.preview_box = tk.Text(self.root, height=12, wrap="none");
        self.preview_box.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        # wiring
        self._toggle_mode()
        self._toggle_quality_enabled()
        self.format_cb.bind("<<ComboboxSelected>>", lambda _e: self._toggle_quality_enabled())

    def _toggle_mode(self):
        is_pct = (self.mode.get() == "percent")
        self.percent_entry.configure(state="normal" if is_pct else "disabled")
        self.width_entry.configure(state="disabled" if is_pct else "normal")
        self.height_entry.configure(state="disabled" if is_pct else "normal")

    def _toggle_quality_enabled(self):
        fmt = self.format_choice.get()
        if fmt == "jpg":
            self.q_scale.state(['!disabled'])
        else:
            self.q_scale.state(['!disabled'])

    def _sync_quality_label(self, _evt=None):
        self.jpg_quality.set(self.q_scale.get())
        self.q_label.config(text=str(self.jpg_quality.get()))

    # --- file/folder selectors ---
    def choose_files(self):
        paths = filedialog.askopenfilenames(
            title="Select image files",
            filetypes=[("Images", "*.jpg;*.jpeg;*.png;*.webp;*.bmp;*.tiff"), ("All files", "*.*")]
        )
        if paths:
            self.files = list(paths)
            self.folder = None
            self.input_label.config(text=f"{len(self.files)} files selected")

    def choose_folder(self):
        folder = filedialog.askdirectory(title="Select folder containing images")
        if folder:
            self.folder = folder
            self.files = []
            count = len(list_images_in_folder(folder))
            self.input_label.config(text=f"Folder selected ({count} images)")

    def choose_output(self):
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            self.output_folder = folder
            self.output_label.config(text=folder)

    # --- Actions ---
    def preview(self):
        files = gather_inputs(self.files, self.folder)
        if not files:
            messagebox.showwarning("No images", "Please select files or a folder with images")
            return

        self.preview_box.delete("1.0", tk.END)
        self.preview_box.insert(tk.END, f"Selected {len(files)} images.\n\nTarget sizes(first 10):\n")

        samples = files[:10]
        mode = self.mode.get()
        pct = _safe_float(self.percent_val.get(), default=50.0)
        w = _safe_int(self.width_val.get())
        h = _safe_int(self.height_val.get())
        keep = self.keep_aspect.get()

        for fp in samples:
            try:
                with Image.open(fp) as im:
                    sw, sh = im.size
                tw, th = calc_target_size(sw, sh, mode, pct, w, h, keep)
                self.preview_box.insert(tk.END, f"- {os.path.basename(fp)} ({sw}x{sh}) -> ({tw}x{th})\n")
            except Exception as e:
                self.preview_box.insert(tk.END, f"- {os.path.basename(fp)} [error: {e}]\n")

        self.status.set("Preview generated. Ready to resize.")

    def run(self):
        files = gather_inputs(self.files, self.folder)
        if not files:
            messagebox.showwarning("No images", "Please select files or a folder with images")
            return

        # decide output folder (default next to source)
        out = self.output_folder
        if not out:
            base_root = os.path.dirname(files[0] if self.files else (self.folder or os.getcwd()))
            out = os.path.join(base_root, "output")
        os.makedirs(out, exist_ok=True)

        args = dict(
            mode=self.mode.get(),
            percent=_safe_float(self.percent_val.get(), default=50.0),
            width_px=_safe_int(self.width_val.get()),
            height_px=_safe_int(self.height_val.get()),
            keep_aspect=self.keep_aspect.get(),
            format_choice=self.format_choice.get(),
            append_suffix=self.append_suffix.get(),
            jpg_quality=self.jpg_quality.get(),
        )

        t = threading.Thread(target=self._worker, args=(files, out, args), daemon=True)
        t.start()

    def _worker(self, files: List[str], out: str, args: dict):
        ok = err = 0
        for i, fp in enumerate(files, start=1):
            success, msg = resize_one(fp, out, **args)
            if success:
                ok += 1
            else:
                err += 1
                self._append(f"[ERROR] {msg}")
            self.progress.configure(value=i)
            self.root.update_idletasks()

        self.status.set(f"Done. Success: {ok}, Errors: {err}. Output: {out}")
        self._append(f"\nFinished.\nSuccess: {ok},\nErrors: {err}\nOutput: {out}")

    def _append(self, text: str):
        self.preview_box.insert(tk.END, text + "\n")
        self.preview_box.see(tk.END)

def _safe_int(v):
    """Return int(v) if possible, else None. Accepts str/int/None."""
    if v is None:
        return None
    if isinstance(v, int):
        return v
    s = str(v).strip()
    try:
        return int(s)
    except Exception:
        return None

def _safe_float(v, default):
    """Return float(v) if possible, else default. Accepts str/float/int/None."""
    if v is None:
        return default
    try:
        return float(str(v).strip())
    except Exception:
        return default

# ---------- #
# ---Main--- #
# ---------- #

def main():
    root = tk.Tk()
    app = App(root)
    root.mainloop()

if __name__ == "__main__":
    main()



