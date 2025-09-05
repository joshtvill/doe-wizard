"""Lightweight CSV I/O for MVP tests."""
from __future__ import annotations
import pandas as pd
from typing import Union, IO

def read_csv_lite(src: Union[str, bytes, IO]) -> pd.DataFrame:
    """Read a CSV using pandas defaults (UTF-8)."""
    return pd.read_csv(src)
