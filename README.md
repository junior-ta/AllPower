# AllPower

AllPower is a research prototype for a six-hour hospital energy-preparedness workflow. It serves a browser dashboard, a durable job queue, a separate inference worker, and a constrained backup-power plan. The bundled replay is **simulated**. It does not claim to forecast actual ERCOT shortages or inspect real assets.

## What is ready

The local demo runs with Python 3.9+ standard library. With SciPy present, the worker solves a linear program; without it, it uses a clearly named prepared dispatch heuristic. Both are compared with a reactive policy. The shipped demand model is a six-horizon ridge regression fitted to the **simulated** series; it selected against a weekly baseline on a chronological validation window. The saved test evaluation measures synthetic-series fit only. A separate script trains six direct XGBoost or scikit-learn candidates after an official hourly demand CSV is supplied. The image-training script requires a licensed, correctly split dataset and is not connected to the scripted finding.

The simulated hospital is Bayou Regional Hospital in southeast Texas. Its location, loads, backup resources, asset link, and all current demand and supply values are fictional. The normal, supply-loss, and storm cases are deterministic. The storm case is a generic stress test, not a historical replay.

Rebuild the shipped synthetic model with `PYTHONPATH=. python3 scripts/train_synthetic.py`. This requires NumPy and writes `artifacts/synthetic_demand_ridge.json`. The runtime can read its JSON weights using standard Python. Synthetic test MAE spans 513–641 MW across the six horizons; this **does not estimate real ERCOT performance**.

## Run locally

From the repository root, use two terminals:

```bash
python3 -m allpower.server --host 127.0.0.1 --port 8080
python3 -m allpower.worker
```

Open `http://127.0.0.1:8080`, choose a scenario, and click **Run six-hour outlook**. The API can also be checked with `curl http://127.0.0.1:8080/api/status`.

Run tests with `python3 -m unittest discover -s tests -v`.

## Reproduce on LinuxONE

The [LinuxONE Jupyter Lab ML repository](https://github.com/linuxone-community-cloud/jupyter-lab-ml) documents the s390x image and its [published packages](https://raw.githubusercontent.com/linuxone-community-cloud/jupyter-lab-ml/main/packages.txt). These are published configuration details; inspect your actual VM and image before claiming an installed package or accelerator. This project was assembled off-instance and has **not yet been verified on the user's LinuxONE host**.

1. Copy the repository to the VM using `git clone` or `scp`. Keep your event-window Git history. If the datathon requires all code to be authored during its event window, verify that this work qualifies before submission.
2. Record the environment: `uname -m`, `docker version`, `docker compose version`, `free -h`, `df -h`, and `docker image inspect registry.linuxone.cloud.marist.edu/l1cc/jupyterlab-image-s390x:latest --format '{{index .RepoDigests 0}}'`. Save output in your private evidence folder. The base image in `.env.example` uses a mutable tag because its digest cannot be inspected from this workspace. Replace it with the digest you actually pull.
3. Copy `.env.example` to `.env`. Generate a token with `openssl rand -hex 24`; paste it into `ALLPOWER_TOKEN`. Keep `.env` out of Git. On the VM, `docker compose build` and `docker compose up -d`.
4. Check `docker compose ps`, `docker compose logs --tail=50 worker`, and `curl -H "X-AllPower-Token: YOUR_TOKEN" http://127.0.0.1:8080/api/status`. The website is bound to VM loopback only.
5. On your laptop, use `ssh -L 8080:127.0.0.1:8080 USER@VM_HOST`, then open `http://127.0.0.1:8080`. Enter the token when prompted. Use a fresh browser profile if an older token is stored in session storage.
6. Run supply loss, inspect the forecast and backup comparison, acknowledge the advisory, and refresh. Confirm acknowledgment remains.
7. Recovery demonstration: `docker compose stop worker`; click **Run six-hour outlook** so a queued job is visible; then `docker compose start worker`. The dashboard should complete the same job. `docker compose restart web` and confirm the acknowledgment remains. This demonstrates one-host worker recovery, not site failover.

If port 8080 is occupied on your laptop, use `ssh -L 18080:127.0.0.1:8080 USER@VM_HOST` and open `http://127.0.0.1:18080`.

## Official demand data and ML evaluation

Preferred official sources: [ERCOT hourly load archives](https://www.ercot.com/gridinfo/load/load_hist) and [EIA-930](https://www.eia.gov/electricity/930-content/about.html). Download an archive yourself on LinuxONE or your laptop, preserve the source URL, date, license/terms, original file hash, timezone, and original file in `data/raw/`. The supplied workspace could not reach the source host, so **no official rows are bundled**.

Prepare a `data/ercot_hourly.csv` with two columns: `timestamp` as continuous ISO 8601 hourly instants with timezone (UTC recommended), and `demand_mw` as numeric MW. Handle duplicate daylight-saving hours by converting to UTC before import. Do not fill gaps with invented observations. Run:

```bash
python3 scripts/train_demand.py data/ercot_hourly.csv --out artifacts/demand
```

This produces six model files and `evaluation.json` with chronological train, validation, and test windows, six-hour gaps, weekly and persistence baselines, MAE/RMSE by horizon, validation-selected candidates, and interval coverage. Review results before enabling official-demand mode. With an official CSV mounted in `./data`, set in `.env`:

```text
ALLPOWER_DEMAND_CSV=/opt/allpower/data/ercot_hourly.csv
ALLPOWER_DEMAND_PROVENANCE=observed public data
```

Then run `docker compose up -d --force-recreate worker`. The supply, reserve, hospital, and local interruption remain simulated. The current app uses the fitted demand model only if the evaluation report selects it on the validation window; otherwise it uses the weekly baseline. Model files are trusted local artifacts; do not load untrusted pickle files.

The [ERCOT adequacy report](https://www.ercot.com/mp/data-products/data-product-details?id=NP3-763-CD) can supply capacity context if you preserve publication timestamps and validate how it maps to the forecast origin. EIA net generation is not spare capacity. Do not substitute one for the other.

## Vision work

[InsPLAD](https://github.com/andreluizbvs/InsPLAD) has power-line inspection labels and a noncommercial license. Obtain it under its current terms. Stage one binary category as `data/vision/{train,val,test}/{normal,defect}/`. Keep all crops from one source image within one partition and preserve publisher splits when provided. The script trains a HOG logistic baseline and compact CNN and writes balanced accuracy, defect recall, and a confusion matrix:

```bash
python3 scripts/train_vision.py data/vision --out artifacts/vision
```

The script cannot independently prove source-image grouping from filenames. Record a manifest and verify grouping before citing its test score. The website responds `503` for image uploads until `artifacts/vision/hog_logistic.pkl` is present. Once trained, the image input uses that model and labels its output separately from the scripted scenario finding. A classifier score is not a calibrated failure probability.

## Submission map

- `notebooks/01_demand_and_scenarios.ipynb`: data checks, benchmark and ML training instructions, resource plan.
- `docs/DATA_AND_LIMITATIONS.md`: source and assumption inventory.
- `docs/DEMO_RUNBOOK.md`: click sequence, screenshot checklist, recovery demo and fallback.
- `docs/ARCHITECTURE.md`: queue, API and security boundaries.
- `tests/`: executable core checks.
- `web/`: static, offline, responsive interface.

The deck is delivered separately beside the repository. Record lab-completion screenshots and actual LinuxONE evidence before submission. There are no claimed accelerator measurements, encryption proofs, hospital partners, or operational alerts in this prototype.
