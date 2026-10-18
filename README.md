# AllPower

AllPower is a LinuxONE-hosted prototype for six-hour electricity demand and supply-risk planning. A Python worker creates a forecast and simulated supply scenario, saves the result in SQLite, and estimates backup coverage for a fictional hospital. The web app has two portals:

- **Hospital:** six-hour outlook, backup plan, persistent alert acknowledgments, and an outage-preparation assistant.
- **Power supplier:** regional outlook and a facility-inspection demo. The saved image model assesses a cropped glass insulator for a missing-cap defect; it does not determine whether an entire facility works.

Each portal shows an expected operational view above a scroll-down simulation section. The facility records, hospital, supply figures, and local outage scenario are illustrative. The repository retains the ERCOT historical demand data, licensed InsPLAD image subset, trained models, and evaluation results as research evidence. Historical demand is **not** a live feed or a validated local-outage prediction. See [data and limitations](docs/DATA_AND_LIMITATIONS.md) for exact claims.

## Run the web app on LinuxONE

You need LinuxONE SSH access, Docker with the Compose plugin, and the ability to build from the LinuxONE base image in `Dockerfile`. The commands below run **on LinuxONE** unless labeled Windows.

1. Clone the repository, or enter your existing checkout:

   ```bash
   git clone https://github.com/junior-ta/AllPower.git
   cd AllPower
   ```

   For an existing checkout, use `cd /path/to/AllPower` followed by `git pull origin main`. Keep your private `.env` and `data/allpower.sqlite3` when updating. Back up the database before your first deployment of a new version.

2. Configure the private environment file once:

   ```bash
   cp .env.example .env
   chmod 600 .env
   nano .env
   ```

   Replace `ALLPOWER_TOKEN=replace-with-a-random-token` with a token you choose. You will enter that token in the web page. For generated hospital advice, create a Gemini key in [Google AI Studio](https://aistudio.google.com/app/apikey) and set `GEMINI_API_KEY` in `.env`; without it, the app shows a prepared checklist. Do not commit `.env` or put either key in browser code. To use the bundled **historical** ERCOT demand CSV instead of synthetic history, set `ALLPOWER_DEMAND_CSV=/opt/allpower/data/ercot_hourly.csv` and `ALLPOWER_DEMAND_PROVENANCE=observed public data` after checking the input's provenance. The app labels each run's source.

3. Build and start the web app and worker:

   ```bash
   docker compose up -d --build --force-recreate
   docker compose ps
   ```

   Both `web` and `worker` should be running. The app listens on LinuxONE's loopback port **8080**. Compose mounts `./data` for the persistent SQLite database and `./artifacts` for saved models. A code update requires this rebuild; `git pull` alone does not change the running containers.

4. On your **Windows PC**, open PowerShell and start an SSH tunnel. Leave this window open while using the site:

   ```powershell
   ssh -L 18080:127.0.0.1:8080 YOUR_USERNAME@YOUR_LINUXONE_HOST
   ```

   Use your existing SSH alias in place of `YOUR_USERNAME@YOUR_LINUXONE_HOST` if you have one. Open [http://localhost:18080/](http://localhost:18080/) for the hospital portal and [http://localhost:18080/supplier.html](http://localhost:18080/supplier.html) for the supplier portal. Enter your AllPower token in the page's token field. The old `/vision-demo.html` URL redirects to supplier inspection.

To check a startup problem on LinuxONE, run `docker compose logs --tail=100 web worker`. To stop the app, run `docker compose down`; this does not delete the bind-mounted `./data` directory. If only the SSH tunnel closed, rerun step 4; the containers may still be running.

## Repository contents

`allpower/` contains the API, worker, forecasting, backup, image inference, and advice logic. `web/` contains the two portals. `data/` contains research inputs and the runtime SQLite database; `artifacts/` contains saved models and evaluations. `scripts/` and `notebooks/` preserve reproducible research steps; training is **not** needed to run the web app. `docs/` has the [architecture](docs/ARCHITECTURE.md), [data limits](docs/DATA_AND_LIMITATIONS.md), and [demo runbook](docs/DEMO_RUNBOOK.md).

Run the code checks from the repository root with `python3 -m unittest discover -s tests -v`.
