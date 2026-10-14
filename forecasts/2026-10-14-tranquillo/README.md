# Frozen forecasts — Tranquillo (NCT05583526)

Ritlecitinib 50 mg QD vs placebo; registered ~400 vs ~200 participants. Produced by `vitiligo model predict --freeze` with scenario model v0.2 (`docs/jak-scenario-model.md`).
**No Tranquillo results were consulted before freezing.** Verify a seal: SHA-256 of the record's canonical JSON (sorted keys, no whitespace) without its `sha256` field. The back-test files referenced by each record are included here and match the hashes sealed inside the records.

| File | Endpoint | Frozen at (UTC) | Active — median (80% PI) | Placebo | Difference | P(active > placebo) |
|---|---|---|---|---|---|---:|
| `tranquillo-fvasi75-w24-secondary.json` | fvasi75-w24-secondary | 2026-10-14T10:44:02 | 16.6% (3.3–49.1) | 2.9% (0.4–11.9) | 12.8% (2.1–36.5) | 0.986 |
| `tranquillo-fvasi75-w52-primary.json` | fvasi75-w52-primary | 2026-10-14T10:40:38 | 45.8% (13.8–84.0) | 9.5% (1.6–28.5) | 33.3% (8.8–60.7) | 0.986 |
| `tranquillo-tvasi50-w24-secondary.json` | tvasi50-w24-secondary | 2026-10-14T10:45:41 | 5.0% (1.0–17.7) | 6.9% (3.8–10.8) | -1.5% (-6.2–8.6) | 0.369 |
| `tranquillo-tvasi50-w52-us-coprimary.json` | tvasi50-w52-us-coprimary | 2026-10-14T10:42:37 | 11.2% (1.8–40.7) | 15.5% (8.6–28.8) | -3.5% (-15.5–19.5) | 0.369 |

SHA-256 seals:

- `tranquillo-fvasi75-w24-secondary.json`: `c5e5aa6c25812ccae236fcb15a4dcd42ea628fc78d4308f2b9e58bc666ff9e27`
- `tranquillo-fvasi75-w52-primary.json`: `f8ecedfcb47a33687151dc57058807341aec8a75a29c1463f0a9997b7b637d36`
- `tranquillo-tvasi50-w24-secondary.json`: `b643e6fdca778bd286421dd093194d6a32e3d070d1a0e0a6b5d969323664d498`
- `tranquillo-tvasi50-w52-us-coprimary.json`: `cd33a4ac13010aeff27835dc0f0005444378194c143886eb3c2ac75246070bbc`

## Topline check (added 2026-10-14, after sealing)

See [`../TOPLINE-CHECK-2026-10-14.md`](../TOPLINE-CHECK-2026-10-14.md): topline results for some of these trials were public before sealing, so those forecasts are not prospective.
