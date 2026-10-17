# Five-minute demonstration

1. Show `uname -m` and `docker compose ps` on LinuxONE. Say which capabilities are measured there.
2. Open the website through the SSH tunnel. The banner says **Simulated demo**. Show normal operation first: no urgent advisory.
3. Select **Supply loss** and run. Point to forecast demand, assumed supply after reserve, first tight-margin hour, and the hospital advisory.
4. Point to prepared versus reactive modeled critical energy. Explain that the comparison depends on fictional battery, generator, solar and startup assumptions. Acknowledge the advisory, refresh, and show persistence.
5. Switch to Inspection. Explain that the displayed concern is a scenario finding and the image model requires a licensed training subset. Do not call it a live classifier.
6. Stop the worker, queue a new run, restart the worker, and watch completion. This proves durable recovery on one host.
7. Close on Evidence: current runtime architecture and clear real/simulated/production-design boundaries.

## Evidence to capture on the actual VM

- Lab-completion records from the event platform.
- `uname -m`, image digest, Docker and package versions.
- Running web and worker containers; browser and backend on the VM.
- A full run with result ID, advisory and acknowledgment after restart.
- Queued job while worker stopped and completed job after restart.
- Model evaluation JSON only after a real dataset has been trained there.
- Access via SSH tunnel and loopback binding; do not show the token.

## Presentation fallback

If the live VM is unavailable, run both Python processes locally and state that the fallback is local. The dashboard still shows the deterministic scenarios, but do not claim that fallback as LinuxONE evidence. Keep screenshots of the actual VM run separately.
