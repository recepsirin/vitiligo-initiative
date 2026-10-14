# Automatic forecasts — unreported JAK trials (2026-10-14)

Produced by `vitiligo discover forecast-pending` (scenario model v0.2) from each trial's **registered** design; no results for these trials were consulted. Each `.json` is sealed (SHA-256 of its content), and its predictive draws (`.npz`) are hash-sealed inside it. All are in the discovery ledger as pending tier-2 entries; `vitiligo discover resolve` scores them once results are posted. Trials skipped, and why, are printed by the command (e.g. undisclosed doses for povorcitinib's and zasocitinib's Phase 3s).

| Trial | Arm | Endpoint | Active, median (80% PI) | Control | P(active > control) | Assumptions / extrapolation | Seal |
|---|---|---|---|---|---:|---|---|
| NCT06072183 | Arm 1- Ritlecitinib 100 milligrams (mg) | F-VASI75 wk 52 | 56.0% (18.8–90.7) | 9.5% (1.6–28.5) | 0.99 | dose outside studied range 10-50; week 52 beyond this agent's data (max week 24): relies on its route's time course; placebo/vehicle data end at week 24: control response at week 52 is extrapolated | `ca08c4d9e98f…` |
| NCT06072183 | Arm 1- Ritlecitinib 100 milligrams (mg) | T-VASI50 wk 52 | 15.0% (2.2–52.9) | 15.5% (8.6–28.8) | 0.49 | dose outside studied range 10-50; week 52 beyond this agent's data (max week 24): relies on its route's time course; placebo/vehicle data end at week 24: control response at week 52 is extrapolated | `cbccd6618d9d…` |
| NCT06072183 | Arm 2- Ritlecitinib 50mg | F-VASI75 wk 52 | 45.8% (13.8–84.0) | 9.5% (1.6–28.5) | 0.99 | week 52 beyond this agent's data (max week 24): relies on its route's time course; placebo/vehicle data end at week 24: control response at week 52 is extrapolated | `264884712ed8…` |
| NCT06072183 | Arm 2- Ritlecitinib 50mg | T-VASI50 wk 52 | 11.2% (1.8–40.7) | 15.5% (8.6–28.8) | 0.37 | week 52 beyond this agent's data (max week 24): relies on its route's time course; placebo/vehicle data end at week 24: control response at week 52 is extrapolated | `b15c11807ea2…` |
| NCT06118411 | Study 1, Period A: Group 1 | F-VASI75 wk 48 | 37.9% (9.5–77.1) | 8.6% (1.4–26.4) | 0.98 | week 48 beyond this agent's data (max week 24): relies on its route's time course; placebo/vehicle data end at week 24: control response at week 48 is extrapolated | `e4345b1a0f23…` |
| NCT06118411 | Study 1, Period A: Group 1 | T-VASI50 wk 48 | 15.1% (1.8–60.9) | 14.5% (8.1–26.1) | 0.52 | agent has no data: prediction is the oral-route class prior, very uncertain; placebo/vehicle data end at week 24: control response at week 48 is extrapolated | `c8095c963650…` |
| NCT06118411 | Study 2, Period A: Group 1 | F-VASI75 wk 48 | 37.9% (9.5–77.1) | 8.6% (1.4–26.4) | 0.98 | week 48 beyond this agent's data (max week 24): relies on its route's time course; placebo/vehicle data end at week 24: control response at week 48 is extrapolated | `812539cc4684…` |
| NCT06118411 | Study 2, Period A: Group 1 | T-VASI50 wk 48 | 15.1% (1.8–60.9) | 14.5% (8.1–26.1) | 0.52 | agent has no data: prediction is the oral-route class prior, very uncertain; placebo/vehicle data end at week 24: control response at week 48 is extrapolated | `d29b45f90f38…` |
| NCT06548360 | Ruxolitinib 1.5 % Cream | F-VASI75 wk 24 | 24.0% (6.0–57.4) | 2.8% (0.4–11.4) | 1.00 | dosing frequency not stated in the registry: equal QD/BID mixture | `c8d64ec32b35…` |
| NCT06804811 | Ruxolitinib 0.75 % Cream | F-VASI75 wk 24 | 20.3% (4.6–52.9) | 2.8% (0.4–11.4) | 1.00 | dosing frequency not stated in the registry: equal QD/BID mixture | `36c555113882…` |
| NCT06804811 | Ruxolitinib 1.5 % Cream | F-VASI75 wk 24 | 24.0% (6.0–57.4) | 2.8% (0.4–11.4) | 1.00 | dosing frequency not stated in the registry: equal QD/BID mixture | `289b81690e34…` |

## Post-freeze notes

Written 2026-10-14T13:01:31.053295+00:00, after sealing; the sealed files are unchanged.

1. **T-VASI50 forecasts (ritlecitinib, upadacitinib) are low confidence.**
   - They show little or no separation from placebo because Phase 2 data to week 24 showed little or no T-VASI50 separation.
   - The model cannot represent a benefit that only appears later.
   - Same caveat as the Tranquillo assessment (`../2026-10-14-tranquillo/post-freeze-assessment.md`).
2. **Week 48–52 forecasts extrapolate beyond the data** (oral agents have no controlled data beyond week 24). In the only check available, the model over-predicted TRuE-V's week-52 results; expect F-VASI75 forecasts at these weeks to err high.
3. **Ritlecitinib 100 mg is above the highest studied dose (50 mg):** a dose-response extrapolation.
4. **Ruxolitinib cream trials don't state the dosing frequency** in the registry. Those forecasts are an equal once-/twice-daily mixture, an assumption sealed into each record.
5. **Upadacitinib's two sub-studies (Study 1 and Study 2) have identical forecasts.** They share one registered regimen, and the model has no study-specific information. Their two results will test the between-trial spread.

## Topline check (added 2026-10-14, after sealing)

See [`../TOPLINE-CHECK-2026-10-14.md`](../TOPLINE-CHECK-2026-10-14.md): topline results for some of these trials were public before sealing, so those forecasts are not prospective.
