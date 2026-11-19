import sys
from pathlib import Path


def before_all(context):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integration"))
    from test_text_postgresql import require_local_fixture

    require_local_fixture()
