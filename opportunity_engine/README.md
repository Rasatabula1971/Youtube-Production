# Opportunity Engine v2

Turns every opportunity source into one **canonical Opportunity Packet** so the
Human Opportunity Gate reviews evidence the same way whatever the source.

Spec: [`OPPORTUNITY_DISCOVERY_SPEC.md`](OPPORTUNITY_DISCOVERY_SPEC.md) (v2.1 —
read the *v2.1 Revisions* section first).

## Built so far (slices O1 + O2)

| Module | Role |
|---|---|
| `models.py` | Shared vocabulary: source types, evidence levels, the four breakout axes, routes, gate decisions |
| `provenance.py` | Stable opportunity ids, content hashes, source-artifact records |
| `packet_schema.py` | `build_packet()` / `validate_packet()` — the one packet shape all lanes produce |
| `channel_scope.py` | Routes an idea to Science Inside, a future-channel shelf, or an exclusion (with the rule) |
| `historical_adapter.py` | Wraps the Experiment 01.5 study set as packets; 01.3–01.5 are unchanged |
| `config.json` | Active channel, future channels, exclusion rules, written evidence rules |

Run the historical adapter:

```
python opportunity_engine/historical_adapter.py
```

It reads `experiment_01_discovery/output/experiment_01_5/study_set.json` and
writes `opportunity_engine/output/opportunities/historical.json`. Nothing in
the UI reads it yet; the existing Opportunity Gate is unchanged until O12.

## Rules the contract enforces

- No virality or opportunity score. Evidence dimensions stay separate, and any
  level above UNASSESSED/HYPOTHESIS must name the written rule that set it.
- Viral evidence is four independent axes: strength, trajectory, breadth and
  historical alignment.
- Every packet states where it belongs: `ACTIVE_CHANNEL`, `FUTURE_CHANNEL`,
  `EXCLUDED` (with rule id) or `UNSCOPED`.
- Packet identity is stable across rebuilds; `packet_sha256` changes only when
  the evidence changes.
