# AllPower portal demo runbook

## Before the audience arrives

1. On LinuxONE, confirm the intended Git commit, `uname -m`, `docker compose ps`, mounted demand/model files, and web/worker logs. Keep the private `.env` and token out of recordings.
2. Back up the SQLite database before any first deployment of the updated code. Check that `./data` and `./artifacts` remain mounted.
3. Open the site through the Windows SSH tunnel. Use the inline token field to connect. Check both portals and the supplier example image. Confirm the preparation assistant either generates through the configured provider or presents the prepared checklist.
4. Confirm the displayed demand source, model version, and forecast origin match the actual saved run. Historical inputs are not current predictions.

## Suggested click sequence

1. Open the **Hospital portal**. Show the operational overview, six-hour horizon, real southeast Texas map, and clearly fictional hospital marker.
2. Scroll to **Demo simulation** and run **Supply loss**. Return to the top to show the regional margin, hospital backup coverage, and preparation alert. Regional tight margin is not a confirmed local outage.
3. Show the automatically opened preparation briefing. Open the full assistant view, ask a question about generator/battery checks, and point out that forecast numbers come from the saved AllPower record. If the provider is unavailable, show the labeled prepared checklist.
4. Acknowledge the advisory. Refresh and show the same timestamp in the advisory and **Previous acknowledgments** list.
5. Switch to **Power supplier**. Show the same saved run and total ERCOT demand versus assumed supply.
6. Open **Facility inspection**. Describe the table as illustrative. Use **View in real time** on the first glass-insulator row to run a new model request on its demo image. Other rows have no connected feed.
7. Scroll to the inspection simulation and upload a licensed PNG/JPEG crop. Explain that the result concerns a missing-cap defect on an insulator. It does not establish entire-facility operability.

## Recovery proof

Stop only the worker. Show that the saved forecast, acknowledgment, and advice remain readable. Queue a new scenario and refresh the portal; the pending job should remain visible. Restart the worker and show that the same job finishes. Restart the web container and verify acknowledgment history still loads from the persistent database.

If LinuxONE is unavailable, use the local Python web server and worker as a clearly labeled fallback. Do not present a local fallback as a LinuxONE runtime demonstration.
