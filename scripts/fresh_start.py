"""Start again from the Opportunity stage (D-157).

Moves every production made after the Opportunity Gate, and the gate's own
choice, into ``.archive/fresh_start_<time>/`` so the next run begins at
Opportunities with nothing chosen. Nothing is deleted: to undo, close the UI
and move the archived folders back to where they were.

Kept: discovery and radar data, the opportunity inbox (saved, rejected and
watched items stay as they are), saved ideas (.idea_bank), job logs, and all
code and configuration.

    python scripts/fresh_start.py          # show what would move
    python scripts/fresh_start.py --yes    # move it

Close the UI first; the script refuses while it is running.
"""

from __future__ import annotations

import argparse
import shutil
import socket
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = ROOT / ".archive"
UI_PORT = 8765

# The Opportunity Gate's choice: removing these returns approved
# opportunities to "needs review".
OPPORTUNITY_CHOICE = (
    "experiment_01_discovery/output/experiment_01_5/human_opportunity_decision.json",
    "experiment_01_discovery/output/experiment_01_5/approved_study_set.json",
    "opportunity_engine/output/active_study_source.json",
)

# Everything produced from that choice onwards.
PRODUCTION_OUTPUTS = (
    "experiment_02_analysis/output",
    "experiment_02_analysis/evidence",
    "transformation_engine/output",
    "research_engine/output",
    "packaging_engine/output",
    "story_script_engine/output",
    "format_engine/output",
    "production_engine/output",
)

TARGETS = OPPORTUNITY_CHOICE + PRODUCTION_OUTPUTS


def ui_running(port: int = UI_PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def present(root: Path = ROOT) -> list[Path]:
    return [root / rel for rel in TARGETS if (root / rel).exists()]


def archive(root: Path = ROOT, stamp: str | None = None) -> Path:
    """Move every present target under a new archive folder and return it."""
    destination = root / ".archive" / f"fresh_start_{stamp or datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if destination.exists():
        raise SystemExit(f"Archive folder already exists: {destination}")
    for source in present(root):
        target = destination / source.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Start again from the Opportunity stage")
    parser.add_argument("--yes", action="store_true", help="move the files (otherwise only list them)")
    args = parser.parse_args()

    found = present()
    if not found:
        print("Nothing to archive: no opportunity choice or production output exists.")
        return
    print("These will move to .archive/ (nothing is deleted):")
    for path in found:
        print(f"  {path.relative_to(ROOT)}")
    if not args.yes:
        print("\nDry run. Run again with --yes to move them.")
        return
    if ui_running():
        raise SystemExit("The UI is running. Close it first, then run this again.")
    destination = archive()
    print(f"\nArchived to {destination.relative_to(ROOT)}")
    print("Start the UI and choose a new opportunity under Opportunities.")


if __name__ == "__main__":
    main()
