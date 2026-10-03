"""Wrap the Experiment 01.5 handoff as canonical Opportunity Packets (slice O2).

The historical engine (01.3 -> 01.4 -> 01.5) is not changed. This adapter only
reads its study set and writes canonical packets beside it, grouped the same
way the existing Human Opportunity Gate groups them (niche:topic:format), so
both views always describe the same opportunities.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from opportunity_engine import channel_scope, models  # noqa: E402
from opportunity_engine.packet_schema import build_packet, evidence  # noqa: E402
from opportunity_engine.provenance import (  # noqa: E402
    canonical_sha256,
    opportunity_id,
    source_artifact,
)

HERE = Path(__file__).resolve().parent
EXPERIMENT_01_5_DIR = _ROOT / "experiment_01_discovery" / "output" / "experiment_01_5"
STUDY_SET_FILE = EXPERIMENT_01_5_DIR / "study_set.json"
OUTPUT_FILE = HERE / "output" / "opportunities" / "historical.json"
GENERATOR = "opportunity_engine.historical_adapter"


def _group(study_set: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for item in study_set:
        topic = str(item.get("topic") or "").strip()
        fmt = str(item.get("format_candidate") or "").strip()
        if not topic or not fmt:
            continue
        key = (str(item.get("niche") or "").strip(), topic, fmt)
        grouped.setdefault(key, []).append(item)
    return [
        {"niche": niche, "topic": topic, "format": fmt, "items": items}
        for (niche, topic, fmt), items in grouped.items()
    ]


def _historical_demand(items: list[dict[str, Any]]) -> dict[str, Any]:
    passing = [item for item in items if item.get("gate_status") == "PASS"]
    if passing:
        return evidence(
            "STRONG",
            "HD-01.5-PASS",
            [f"{len(passing)} Experiment 01.5 PASS packet(s)"],
        )
    if any(item.get("gate_status") == "REVIEW" for item in items):
        return evidence("MODERATE", "HD-01.5-REVIEW", ["topic evidence ready, depth or view reference unmet"])
    return evidence("UNASSESSED")


def _replication(
    topic_evidence: dict[str, Any] | None, config: dict[str, Any]
) -> dict[str, Any]:
    channels = int((topic_evidence or {}).get("unique_channels") or 0)
    if channels <= 0:
        return evidence("UNASSESSED")
    rules = sorted(
        config["evidence_rules"]["cross_channel_replication"],
        key=lambda rule: -int(rule["minimum_unique_channels"]),
    )
    for rule in rules:
        if channels >= int(rule["minimum_unique_channels"]):
            return evidence(
                rule["level"],
                rule["rule_id"],
                [f"{channels} independent channels in the topic/format cell"],
            )
    return evidence("UNASSESSED")


def _candidate_video(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "video_id": item.get("video_id"),
        "youtube_url": item.get("youtube_url"),
        "title": item.get("title"),
        "channel_id": item.get("channel_id"),
        "channel_title": item.get("channel_title"),
        "format": models.FORMAT_ALIASES.get(str(item.get("format_candidate") or "")),
        "published_at": item.get("published_at"),
        "views": item.get("views"),
        "measurement_source": "YOUTUBE_DATA_API",
    }


def packets_from_study_set(
    study_set: list[dict[str, Any]],
    *,
    source_artifacts: list[dict[str, str]],
    config: dict[str, Any],
    created_at: str | None = None,
) -> list[dict[str, Any]]:
    packets = []
    for group in _group(study_set):
        items = group["items"]
        topic, niche, fmt = group["topic"], group["niche"], group["format"]
        try:
            packet_format = models.normalize_format(fmt)
        except ValueError:
            continue
        label = topic.replace("_", " ")
        titles = " ".join(str(item.get("title") or "") for item in items)
        channel = channel_scope.route(f"{label} {titles}", niche=niche, config=config)
        topic_evidence = items[0].get("topic_evidence")
        metric = (items[0].get("primary_metric") or {}).get("value")
        packets.append(
            build_packet(
                opportunity_id=opportunity_id(models.SOURCE_HISTORICAL, niche, topic, fmt),
                source_type=models.SOURCE_HISTORICAL,
                title=f"{label.title()} ({packet_format.replace('_', '-')})",
                summary=(
                    f"Historical demand for {label} in {niche or 'an unlabelled niche'}: "
                    f"{len(items)} study video(s); age-matched velocity index {metric}."
                ),
                channel=channel,
                topic=topic,
                niche=niche,
                formats=[packet_format],
                evidence_state={
                    "historical_demand": _historical_demand(items),
                    "cross_channel_replication": _replication(topic_evidence, config),
                },
                historical_evidence={
                    # Same key the existing Human Opportunity Gate uses.
                    "gate_opportunity_id": f"{niche}:{topic}:{fmt}" if niche else f"{topic}:{fmt}",
                    "experiment_01_5_handoff_ids": [item.get("handoff_id") for item in items],
                    "gate_statuses": sorted({str(item.get("gate_status")) for item in items}),
                    "age_matched_velocity_index": metric,
                    "replicated_families": sorted(
                        {f for item in items for f in item.get("replicated_families") or []}
                    ),
                    "topic_unique_channels": (topic_evidence or {}).get("unique_channels"),
                },
                candidate_videos=[_candidate_video(item) for item in items],
                source_artifacts=source_artifacts,
                generator=GENERATOR,
                created_at=created_at,
            )
        )
    return packets


def build(study_set_file: Path | None = None) -> dict[str, Any]:
    study_set_file = study_set_file or STUDY_SET_FILE
    if not study_set_file.is_file():
        return {"status": "WAITING_FOR_01_5", "packets": []}
    study_set = json.loads(study_set_file.read_text(encoding="utf-8"))
    if not isinstance(study_set, list):
        raise ValueError(f"{study_set_file} must contain a list")
    artifacts = [source_artifact(study_set_file, "experiment_01_5_study_set")]
    # The study set's own timestamp, so rebuilding never makes old packets "new".
    built_at = datetime.fromtimestamp(study_set_file.stat().st_mtime, tz=timezone.utc)
    packets = packets_from_study_set(
        study_set,
        source_artifacts=artifacts,
        config=channel_scope.load_config(),
        created_at=built_at.isoformat(),
    )
    return {
        "status": "READY" if packets else "NO_HISTORICAL_OPPORTUNITIES",
        "source_study_set_sha256": artifacts[0]["sha256"],
        "packets_sha256": canonical_sha256([p["packet_sha256"] for p in packets]),
        "packets": packets,
    }


def write(result: dict[str, Any], output_file: Path = OUTPUT_FILE) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, output_file)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-set", type=Path, default=None)
    args = parser.parse_args()
    result = build(args.study_set)
    # Always write, so an emptied or missing study set never leaves stale packets.
    write(result)
    print(f"{result['status']}: {len(result['packets'])} historical opportunity packet(s)")
    for packet in result["packets"]:
        print(f"  {packet['opportunity_id']}  -> {packet['channel']['route']}")


if __name__ == "__main__":
    main()
