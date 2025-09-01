"""Smoke-test the Streamlit dashboard by stubbing streamlit calls and executing
the app module. Catches runtime errors in the dashboard logic without needing a
browser or a live server.
"""

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ---- Build a streamlit stub that records calls ----
class _Metric:
    def __init__(self, *a, **k): pass
class _Col:
    def metric(self, *a, **k): return None
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def selectbox(self, *a, **k): return (a[1][0] if len(a) > 1 else None)
    def number_input(self, *a, **k): return k.get('value', (a[2] if len(a) > 2 else (a[1] if len(a)>1 else 0)))
    def slider(self, *a, **k): return k.get('value', (a[2] if len(a) > 2 else (a[1] if len(a) > 1 else 0)))
    def subheader(self, *a, **k): return None
    def metric(self, *a, **k): return None


def _noop(*a, **k): return None

st = types.ModuleType("streamlit")
st.set_page_config = _noop
st.sidebar = types.SimpleNamespace(
    title=_noop, caption=_noop, radio=lambda *a, **k: "Overview",
    slider=lambda *a, **k: 140, info=_noop, selectbox=lambda *a, **k: (a[1][0] if len(a) > 1 and a[1] else "Overview"))
st.title = _noop
st.markdown = _noop
st.caption = _noop
st.metric = _noop
st.info = _noop
st.success = _noop
st.subheader = _noop
st.image = _noop
st.line_chart = _noop
st.dataframe = _noop
st.columns = lambda *a, **k: [_Col() for _ in range(a[0])]
st.selectbox = lambda *a, **k: (a[1][0] if len(a) > 1 else None)
st.slider = lambda *a, **k: (a[2] if len(a) > 2 else (a[1] if len(a) > 1 else 0))
st.number_input = lambda *a, **k: (a[2] if len(a) > 2 else a[1])
st.empty = lambda *a, **k: _Col()


def _cache(fn=None, **kwargs):
    def deco(f):
        return f
    return deco if fn is None else fn
st.cache = _cache

sys.modules["streamlit"] = st

# Stub pandas styling
import pandas as pd
_orig_style = pd.DataFrame.style
class _Style:
    def map(self, *a, **k): return None
pd.DataFrame.style = property(lambda self: _Style())


def run_page(page_name):
    import importlib.util
    spec = importlib.util.spec_from_file_location("dashboard_module", str(ROOT / "dashboard" / "app.py"))
    app = importlib.util.module_from_spec(spec)
    # Patch the sidebar radio to select each page
    class Sidebar:
        def title(self, *a, **k): pass
        def caption(self, *a, **k): pass
        def info(self, *a, **k): pass
        def radio(self, *a, **k): return page_name
        def slider(self, *a, **k): return 140
        def selectbox(self, *a, **k): return "Overview"
    st.sidebar = Sidebar()
    spec.loader.exec_module(app)
    return "ok"


pages = ["Overview", "Batch Testing", "SPC Control Charts", "Conformity (Guard Bands)",
         "Calibration", "HACCP", "Audit & CAPA"]

for p in pages:
    try:
        run_page(p)
        print(f"{p:25} OK")
    except Exception as e:
        import traceback
        print(f"{p:25} FAILED: {e}")
        traceback.print_exc()
