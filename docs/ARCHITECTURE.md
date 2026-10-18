# Architecture and claim boundary

```text
Browser on laptop --SSH tunnel--> LinuxONE loopback web container
                                   | API + static UI
                                   v
                            SQLite durable queue
                                   |
                            separate worker container
                                   |
                      forecast + scenario + backup plan
                                   |
                         saved run and advisory record
```

Each job is committed before the worker claims it. Claim uses `BEGIN IMMEDIATE`; a running job has a 30-second lease. If a worker stops, the lease expires and another worker can reclaim it. A result and advisory are saved in one SQLite transaction, keyed by the job ID so a repeat claim cannot show duplicate advisories. Failures retry up to three times, then remain visible as failed. Acknowledgments are persistent.

The app uses same-origin HTTP and an `X-AllPower-Token` header when configured. Container port 8080 binds to VM loopback in Compose. A browser reaches it through an SSH tunnel. The token is entered into an inline page field and kept in tab session storage. The master token can access both portals; optional scoped tokens restrict hospital and supplier APIs. This remains prototype access control, not production identity management.

The hospital and supplier outlooks read the same saved run. SQLite also stores advice conversations and returns previous acknowledgments through a history endpoint. The frontend restores a selected saved run after refresh and resumes polling an unfinished job. Worker stoppage does not erase completed runs or acknowledgment records.

The web container hosts the image classifier and the optional hospital text-generation call. Image inference uses the saved HOG classifier. Gemini requests use a private backend key and a small summary retrieved from the saved run; the browser cannot supply authoritative forecast values. If generation fails, the backend returns a deterministic demo checklist. The demand worker and vision classifier do not call Gemini.

Production design may add an accelerator-equipped LinuxONE, platform encryption, stronger identity management, redundant nodes, monitored storage, and an operational data agreement. None of those are demonstrated by this repository until separately verified on the target system.
