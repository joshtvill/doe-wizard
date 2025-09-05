import streamlit as st
from dataclasses import asdict
from ui.blocks import nav_bar, show_status, section_header

st.title("UI Blocks Smoke Test")
section_header("Navigation")
res = nav_bar(next_enabled=True, key_prefix="smoke")

# Replace st.write(res) with one of these:
st.code(repr(res))             # simple text
# OR:
# st.json(asdict(res))         # JSON (no dataframe heuristics)

show_status("info", "Status helpers OK")
