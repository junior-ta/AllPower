# Data, assumptions, and limits

The worker forecasts regional **demand** and compares it with assumed supply after reserve. A tight regional margin does not establish that a particular hospital will lose power. The local interruption in the hospital backup plan is a separate, fictional scenario bridge. No live utility, facility, or camera feed is connected.

| Input | Current source or assumption | Limit |
|---|---|---|
| Regional demand | Synthetic series by default, or `data/ercot_hourly.csv` when explicitly configured | The saved run states its actual source and input timestamp. A historical CSV is not a live feed. |
| Demand model | Saved synthetic ridge coefficients by default; evaluated saved candidates and weekly baseline with configured ERCOT CSV | Demand error does not measure outage-prediction accuracy. No training occurs in the portal. |
| Available supply | 73,700 MW base less scenario derating | Simulated, not verified ERCOT spare capacity. |
| Reserve | 4,800 MW | Simulated. |
| Hospital | Fictional Bayou Regional Hospital and illustrative marker near Houston | No real hospital partnership or location is claimed. |
| Hospital critical load | 420 kW for each forecast hour | Fixed demo assumption. |
| Battery | 900 kWh nameplate, 720 kWh initial usable energy, 240 kW power limit | Actual charge and health are unknown. |
| Generator | 330 kW, 1,800 kWh fuel-equivalent budget | Reactive baseline assumes one startup hour is lost. |
| Solar | Fixed illustrative hourly curve | Storm scenario scales it to 35%. |
| Local interruption | Begins at first modeled regional tight-margin hour | A fictional linkage, not a local outage prediction. |
| Supplier facility states | Stable illustrative records | Their operational labels and displayed confidence are fictional. |
| Glass-insulator image result | Saved HOG/logistic classifier on a cropped InsPLAD example or uploaded image | Assesses a missing-cap defect, not whole-facility operation. Its score is not a calibrated failure probability; the uncertain band requires review. |
| Preparation advice | Saved-run summary, demo checklist, optional Gemini or local llama.cpp text | Explanatory only. The checklist is not hospital-approved and cannot operate equipment. |

The converted ERCOT CSV is documented in `data/ercot_hourly.quality.json` and `data/source_notes.txt`. The demand evaluation is in `artifacts/demand/evaluation.json`. It selected saved candidates for horizons 1–5 and the pure weekly baseline for horizon 6 on validation data. The vision evaluation is in `artifacts/vision/evaluation.json`; the HOG model's held-out demo subset had 59 images, 69.8% balanced accuracy, and 50% defect recall. This small dataset does not establish deployment reliability or physical-asset independence. The image source is InsPLAD, Vieira-e-Silva et al. (2023), CC BY-NC 3.0.

The backup calculation simplifies battery charge efficiency, solar uncertainty, generator ramping, and network constraints. It estimates modeled critical energy served, not patient outcomes. Live use would require fresh timestamped inputs, equipment telemetry, authorization, and validation on the actual site.
