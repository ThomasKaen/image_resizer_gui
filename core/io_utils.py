import os
from typing import List

SUPPORTED_EXTS = {".jpg",".jpeg",".png",".webp",".bmp",".tiff"}

def list_images(folder: str) -> List[str]:
    out: List[str] = []
    for root, _, files in os.walk(folder):
        for n in files:
            if os.path.splitext(n)[1] in SUPPORTED_EXTS:
                out.append(os.path.join(root, n))
    return out

def next_available(path: str) -> str:
    if not os.path.exists(path): return path
    base, ext = os.path.splitext(path); i = 2
    while True:
        cand = f"{base}_{i}{ext}"
        if not os.path.isfile(cand): return cand
        i += 1