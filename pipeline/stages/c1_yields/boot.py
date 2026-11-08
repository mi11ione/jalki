"""Shared paths for the yield stages. Replaces the original bootstrap, which pinned one machine's interpreter."""
import os

from ccn_paths import PACKAGE, stage_dir

HERE = str(stage_dir("c1_yields"))
DATA = str(PACKAGE)
TOOLS = os.path.join(DATA, "tools")
os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
