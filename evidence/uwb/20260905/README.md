# 2026-09-05 UWB real-measurement evidence

The source files contain measured ranges from three physical anchors. The robot interface exposes six logical slots while preserving physical source identity, so duplicated slots do not increase geometry or confidence counts.

| Scenario | Frames | Accepted | Accepted rate | Rejected | Recovering | 2-source frames |
|---|---:|---:|---:|---:|---:|---:|
| static | 3000 | 2949 | 98.30% | 21 | 30 | 0 |
| move | 3000 | 2870 | 95.67% | 57 | 73 | 0 |
| anchor_fault | 1000 | 850 | 85.00% | 146 | 4 | 143 |

Reproduction chain: measured CSV -> six logical observations -> physical-source deduplication -> UwbQualityGate -> 2D estimator.

## Evidence boundary

The captures contain no independent position ground truth and no host-side per-frame timestamps. Residual RMS is an estimator internal-consistency value, not position error. The derived 25 Hz replay axis is not an end-to-end latency measurement. These files support parsing, gate-state, rejection/recovery, deduplication and estimator-execution claims only.

## Figures

- `figures/state_distribution.png`: gate-state distribution.
- `figures/measured_ranges.png`: three measured physical ranges.
- `figures/estimated_traces.png`: estimator output with the evidence boundary in the title.
- `figures/anchor_fault_timeline.png`: physical-source loss and gate response.
- `LONG_RUN_TERMINAL_RECORD.md`: secondary terminal record for the five-minute capture; the raw file is not bundled.

Exact parameters, source hashes and numeric statistics are in `summary.json`; per-frame decisions are in `frames/*.csv`.
