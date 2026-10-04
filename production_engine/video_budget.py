"""One budget per video: every paid step reserves and records here (D-136).

Vision: one combined budget for the whole video (proposed US$5 target and
US$10 ceiling, still to be confirmed by the human). Before this module each
paid step kept its own figures: visual authorizations under a workflow-wide
cap, narration quotes with no dollar cap, thumbnail images under their own
cap, and final sound with no cap at all.

The ledger is an append-only JSONL file. A video is ``concept_id:format``.
Every paid item has a category and a reference (shot, narration branch,
thumbnail, sound requirement) and three kinds of event:

  RESERVE  the most a human authorized for the item (replaces earlier ones)
  RELEASE  the authorization was withdrawn
  ACTUAL   the total actually spent on the item so far (replaces earlier ones)

An item's exposure is the larger of its live reservation and its actual
spend, so an authorization counts before the money is spent and an overrun
counts after. A video's committed total is the sum over its items.
A reservation that would take the committed total above the ceiling is
refused; above the target it is allowed and flagged. Actual spend is always
recorded, because it has already happened; an overrun shows as such.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline_integrity import append_jsonl, named_lock, read_jsonl

HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE / "video_budget_config.json"
LEDGER_FILE = HERE / "output" / "video_budget_ledger.jsonl"
LEDGER_NAME = "video_budget_ledger.jsonl"
CATEGORIES = ("narration", "visual", "thumbnail_image", "sound")

# Shared even if this module is imported twice (as video_budget and as
# production_engine.video_budget): check-then-append must be atomic.
_LOCK = named_lock("video_budget")


def money(value: Any, *, label: str = "amount") -> float:
    """A finite, non-negative US-dollar amount; NaN and infinity are refused.

    NaN compares false with everything, so one NaN in a sum would silently
    disable every ceiling check that follows.
    """
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a number of US dollars")
    try:
        amount = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number of US dollars") from exc
    if not math.isfinite(amount) or amount < 0:
        raise ValueError(f"{label} must be a finite, non-negative number of US dollars")
    return round(amount, 4)


def load_config() -> dict[str, Any]:
    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    for key in ("target_usd", "ceiling_usd"):
        value = config.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
            raise ValueError(f"Video budget config needs a non-negative {key}")
    if config["target_usd"] > config["ceiling_usd"]:
        raise ValueError("The budget target cannot exceed the ceiling")
    return config


def ledger_in(output_dir: Path) -> Path:
    """The ledger beside a stage's output folders.

    Every paid stage keeps its folders directly under production_engine/output,
    so in use they all name the same file; a test that moves a stage's folders
    moves its ledger with them.
    """
    return Path(output_dir) / LEDGER_NAME


def _ledger(ledger: Path | None) -> Path:
    return Path(ledger) if ledger is not None else LEDGER_FILE


def video_id(concept_id: Any, fmt: Any) -> str:
    return f"{str(concept_id or '').strip()}:{str(fmt or '').strip()}"


def _items(video: str, ledger: Path | None = None) -> dict[tuple[str, str], dict[str, float]]:
    items: dict[tuple[str, str], dict[str, float]] = {}
    for event in read_jsonl(_ledger(ledger)):
        if event.get("video_id") != video:
            continue
        key = (str(event.get("category") or ""), str(event.get("ref") or ""))
        item = items.setdefault(key, {"reserved": 0.0, "actual": 0.0})
        kind = event.get("event")
        try:
            amount = float(event.get("amount_usd") or 0)
        except (TypeError, ValueError):
            amount = math.inf
        if not math.isfinite(amount) or amount < 0:
            # A corrupt line must never loosen the budget: it blocks instead.
            amount = math.inf
        if kind == "RESERVE":
            item["reserved"] = amount
        elif kind == "RELEASE":
            item["reserved"] = 0.0
        elif kind == "ACTUAL":
            item["actual"] = amount
    return items


def _exposure(item: dict[str, float]) -> float:
    return max(item["reserved"], item["actual"])


def summary(
    video: str, config: dict[str, Any] | None = None, ledger: Path | None = None
) -> dict[str, Any]:
    config = config or load_config()
    items = _items(video, ledger)
    by_category = {category: {"committed_usd": 0.0, "actual_usd": 0.0} for category in CATEGORIES}
    for (category, _ref), item in items.items():
        row = by_category.setdefault(category, {"committed_usd": 0.0, "actual_usd": 0.0})
        row["committed_usd"] = round(row["committed_usd"] + _exposure(item), 4)
        row["actual_usd"] = round(row["actual_usd"] + item["actual"], 4)
    committed = round(sum(_exposure(item) for item in items.values()), 4)
    actual = round(sum(item["actual"] for item in items.values()), 4)
    return {
        "video_id": video,
        "target_usd": float(config["target_usd"]),
        "ceiling_usd": float(config["ceiling_usd"]),
        "confirmed_by_human": bool(config.get("confirmed_by_human")),
        "committed_usd": committed,
        "actual_usd": actual,
        "remaining_usd": round(float(config["ceiling_usd"]) - committed, 4),
        "over_target": committed > float(config["target_usd"]),
        "over_ceiling": committed > float(config["ceiling_usd"]),
        "by_category": by_category,
    }


def _record(
    event: str, *, video: str, category: str, ref: str, amount: float, actor: str, note: str,
    ledger: Path | None,
) -> None:
    if category not in CATEGORIES:
        raise ValueError(f"Unknown budget category {category!r}")
    append_jsonl(
        _ledger(ledger),
        {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "video_id": video,
            "category": category,
            "ref": ref,
            "amount_usd": round(float(amount), 4),
            "actor": actor,
            "note": note,
        },
    )


def reserve(
    *, video: str, category: str, ref: str, amount_usd: float, actor: str = "", note: str = "",
    ledger: Path | None = None,
) -> dict[str, Any]:
    """Authorize up to ``amount_usd`` for one item; refused above the ceiling."""
    with _LOCK:
        config = load_config()
        amount = money(amount_usd, label="A reservation")
        items = _items(video, ledger)
        current = items.get((category, ref), {"reserved": 0.0, "actual": 0.0})
        others = sum(_exposure(item) for key, item in items.items() if key != (category, ref))
        after = round(others + max(amount, current["actual"]), 4)
        if after > float(config["ceiling_usd"]):
            raise ValueError(
                f"This would commit ${after:.2f} for {video}, above the per-video ceiling "
                f"${float(config['ceiling_usd']):.2f} (already committed ${others:.2f} elsewhere)"
            )
        _record("RESERVE", video=video, category=category, ref=ref, amount=amount, actor=actor, note=note, ledger=ledger)
        return summary(video, config, ledger)


def release(
    *, video: str, category: str, ref: str, actor: str = "", note: str = "", ledger: Path | None = None
) -> dict[str, Any]:
    with _LOCK:
        if _items(video, ledger).get((category, ref), {}).get("reserved"):
            _record("RELEASE", video=video, category=category, ref=ref, amount=0, actor=actor, note=note, ledger=ledger)
        return summary(video, ledger=ledger)


def record_actual(
    *, video: str, category: str, ref: str, total_usd: float, actor: str = "", note: str = "",
    ledger: Path | None = None,
) -> dict[str, Any]:
    """Record the total actually spent on one item (money already spent)."""
    with _LOCK:
        amount = money(total_usd, label="Actual cost")
        current = _items(video, ledger).get((category, ref), {}).get("actual")
        if current is None or round(current, 4) != amount:
            _record("ACTUAL", video=video, category=category, ref=ref, amount=amount, actor=actor, note=note, ledger=ledger)
        return summary(video, ledger=ledger)


def all_videos() -> list[str]:
    return sorted({str(event.get("video_id")) for event in read_jsonl(LEDGER_FILE) if event.get("video_id")})


def snapshot() -> dict[str, Any]:
    config = load_config()
    return {
        "target_usd": float(config["target_usd"]),
        "ceiling_usd": float(config["ceiling_usd"]),
        "confirmed_by_human": bool(config.get("confirmed_by_human")),
        "videos": [summary(video, config) for video in all_videos()],
    }
