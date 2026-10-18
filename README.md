# AllPower

AllPower is a LinuxONE research prototype for six-hour regional power-risk awareness and fictional hospital backup planning. The browser talks to a Python web API through an SSH tunnel. A separate worker claims SQLite jobs, calculates saved demand forecasts and scenario margins, and commits hospital backup plans and advisories. Both containers share `./data` and read the saved models in `./artifacts`.

## Portals

- `/` and `/hospital.html`: hospital outlook, backup coverage, acknowledgment and history, real southeast Texas map with a fictional marker, and a preparation assistant.
- `/supplier.html`: total ERCOT outlook and illustrative facility inspection table. The first row runs fresh inference on a saved example insulator photo. The upload section accepts PNG/JPEG images under 2 MB.
- `/vision-demo.html`: compatibility shortcut to supplier inspection.

Each portal shows its expected operational view first. Scroll down for labeled demo simulation controls. The hospital and supplier outlooks use the same saved run. Regional demand is total ERCOT; available supply and reserve are scenario assumptions. The hospital location and resources, local interruption, and supplier facility records are fictional. The trained image model assesses a cropped glass insulator for a missing-cap defect. It cannot certify that an entire facility is operational. Model scores are not calibrated failure probabilities.

The repo contains `data/ercot_hourly.csv`, saved evaluated demand candidates, and a trained `artifacts/vision/hog_logistic.pkl`. No training is required for this portal update. The worker uses the supplied demand CSV only when `ALLPOWER_DEMAND_CSV` is configured. Otherwise it uses synthetic history and saved synthetic ridge weights. Every completed run states its actual source, model, and input timestamp. Historical inputs must not be described as a current forecast.

## Access and preparation assistant

Enter `ALLPOWER_TOKEN` in the inline field when configured. The browser keeps it in the current tab's session storage. Optional `ALLPOWER_HOSPITAL_TOKEN` and `ALLPOWER_SUPPLIER_TOKEN` restrict their respective portal APIs; the master token works on both. This is prototype access control, not production identity management.

The hospital assistant gets forecast and backup details from a saved run on the backend. It sends only a small structured summary and a bounded question to the configured text model. The default provider uses `GEMINI_API_KEY` and `gemini-3.5-flash-lite` through the LinuxONE web container. An optional local llama.cpp-compatible endpoint can be configured with `ALLPOWER_ADVICE_PROVIDER=llama` and `ALLPOWER_LLAMA_URL`. A model timeout, rate limit, missing key, or failure returns a deterministic demo preparation checklist from the saved run. The checklist is not hospital-approved. Keep patient information out of this prototype.

## Run locally

From the repository root in two terminals:

```bash
python3 -m allpower.server --host 127.0.0.1 --port 8080
python3 -m allpower.worker
```

Open `http://127.0.0.1:8080`. With no access token configured, local API requests are permitted. Run tests with `python3 -m unittest discover -s tests -v`. Local image inference requires Pillow, NumPy, scikit-image, and scikit-learn in the web environment; the baseline API and fallback assistant use the standard library.

## Update LinuxONE

1. Back up `data/allpower.sqlite3` using a consistent SQLite backup operation. Keep `./data`, `./artifacts`, and the private `.env` on the VM.
2. Pull the intended Git commit. Set `ALLPOWER_TOKEN` in the private `.env` and, if desired, `GEMINI_API_KEY`. See `.env.example`. Never commit keys or include them in the browser JavaScript.
3. Run `docker compose up -d --build --force-recreate`. A pull alone does not update the running site because the image copies source files during build.
4. Check `docker compose ps` and logs for both containers. Verify `GET /api/status` using the token header, then open the portal through an SSH tunnel. The Compose port binds to LinuxONE loopback.
5. Run supply loss, acknowledge, refresh, and confirm the saved timestamp and history. Stop the worker, queue another job, refresh, restart the worker, and confirm the same job completes. Test the saved example and an uploaded image in supplier inspection.

On Windows, if local port 8080 is occupied, use `ssh -L 18080:127.0.0.1:8080 USER@VM_HOST` and browse `http://localhost:18080/`. The web container must be able to reach Gemini over HTTPS for generated explanations; the prepared checklist works without that connection. Set `ALLPOWER_DEMAND_CSV=/opt/allpower/data/ercot_hourly.csv` and `ALLPOWER_DEMAND_PROVENANCE=observed public data` only when the mounted CSV is the intended validated input. Supply, reserve, and hospital values remain simulated.

## Records and recovery

SQLite stores jobs, completed runs, advisories, acknowledgment timestamps, and advice messages. Schema additions use `CREATE TABLE IF NOT EXISTS` and preserve existing records. A result and advisory are committed together. A worker job has a lease and may be reclaimed after an interruption. Acknowledgment keeps its first timestamp when repeated. The browser restores the selected run, reads acknowledgment history from SQLite, and resumes pending-job polling after refresh. While the worker is offline, the web API can still show saved results and accept acknowledgment.

See `docs/ARCHITECTURE.md`, `docs/DATA_AND_LIMITATIONS.md`, and `docs/DEMO_RUNBOOK.md` for the claim boundaries and demo sequence. The saved evaluation scores are research evidence, not a reliability claim for real outages or facility condition.
