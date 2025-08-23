from dataclasses import dataclass
from typing import Optional, Tuple

@dataclass(frozen=True)
class ResizeOptions:
    mode: str
    percent: float=50.0
    width_px: Optional[int]=None
    height_px: Optional[int]=None
    keep_aspect: bool=True
    format_choice: str="keep"
    append_suffix: bool=True
    jpg_quality: int=85

@dataclass
class ResizeResult:
    src_path: str
    dst_path: Optional[str]
    ok: bool
    error: Optional[str] = None
    in_size: Optional[Tuple[int, int]] = None
    out_size: Optional[Tuple[int, int]] = None