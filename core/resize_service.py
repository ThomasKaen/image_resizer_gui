import os
from typing import Iterable, Callable, Iterator, Tuple
from PIL import Image
from .models import ResizeOptions, ResizeResult
from .io_utils import next_available

EXT_TO_PIL = {"jpg":"JPEG","jpeg":"JPEG","png":"PNG","webp":"WEBP","bmp":"BMP","tiff":"TIFF"}
ProgressCb = Callable[[int, int], None]
LogCb = Callable[[str], None]

def calc_target_size(sw:int, sh:int, opts:ResizeOptions) -> Tuple[int, int]:
    if opts.mode == "percent":
        f = max(1.0, opts.percent)/100.0
        return max(1, round(sw*f)), max(1, round(sh*f))
    w, h = opts.width_px, opts.height_px
    if opts.keep_aspect:
        if w and not h: return w, max(1, round(sh*(w/sw)))
        if h and not w: return max(1, round(sw*(h/sh))), h
        if w and h:
            s = min(w/sw, h/sh)
            return max(1, round(sw*s)), max(1, round(sh*s))
        return sw, sh
    return (w or sw), (h or sh)

def _save(im:Image.Image, dst:str, pil_fmt:str, jpg_quality:int):
    if pil_fmt == "JPEG" and im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGB")
    kw = {"quality": int(jpg_quality), "optimize": True} if pil_fmt == "JPEG" else {}
    im.save(dst, format=pil_fmt, **kw)

def resize_many(inputs: Iterable[str], out_dir: str, opts:ResizeOptions,
                progress:ProgressCb|None=None, log:LogCb|None=None) -> Iterator[ResizeResult]:
    os.makedirs(out_dir, exist_ok=True)
    files = list(inputs); total=len(files)
    for i, src in enumerate(files, 1):
        try:
            with Image.open(src) as im:
                sw, sh = im.size
                tw, th = calc_target_size(sw, sh, opts)
                resample = Image.LANCZOS if (tw<sw or th<sh) else Image.BICUBIC
                if (tw, th) != (sw, sh): im = im.resize((tw, th), resample=resample)

                base, in_ext = os.path.splitext(os.path.basename(src))
                out_ext = in_ext.lstrip(".").lower() if opts.format_choice=="keep" else opts.format_choice
                pil_fmt = EXT_TO_PIL.get(out_ext)
                if not pil_fmt: raise ValueError(f"Unknown output format .{out_ext}")

                name = f"{base}{'_resized' if opts.append_suffix else ''}.{out_ext}"
                dst = os.path.join(out_dir, name)
                if opts.append_suffix: dst = next_available(dst)

                _save(im, dst, pil_fmt, opts.jpg_quality)

            yield ResizeResult(src, dst, True, None, (sw,sh), (tw,th))
        except Exception as e:
            msg = f"[Error] {os.path.basename(src)} -> {e}"
            if log: log(msg)
            yield ResizeResult(src, None, False, str(e))
        finally:
            if progress: progress(i, total)
