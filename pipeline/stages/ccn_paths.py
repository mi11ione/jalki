"""The only place paths are decided. run_all.py sets CCN_PACKAGE and CCN_OUT; every stage reads the unzipped package from
PACKAGE and writes only under OUT, so the code tree stays clean and a run can never touch the package."""
import os
import sys
from pathlib import Path

PACKAGE = Path(os.environ["CCN_PACKAGE"]).resolve()
OUT = Path(os.environ["CCN_OUT"]).resolve()

# The organisers' ccn_tools (MIT) ships inside the package. Appended last, so nothing in the package can shadow a module.
_tools = str(PACKAGE / "tools")
if _tools not in sys.path:
    sys.path.append(_tools)


def stage_dir(name):
    """Output folder of one stage, created on first use."""
    p = OUT / name
    p.mkdir(parents=True, exist_ok=True)
    return p
