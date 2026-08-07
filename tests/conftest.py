from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Os testes abaixo validam apenas regras puras; a UI real usa Streamlit no app.
if "streamlit" not in sys.modules:
    sys.modules["streamlit"] = types.ModuleType("streamlit")
