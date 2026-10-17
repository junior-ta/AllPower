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

The app uses same-origin HTTP and an `X-AllPower-Token` header when configured. Container port 8080 binds to VM loopback in Compose. A browser reaches it through an SSH tunnel. The token is in session storage, so use a dedicated demonstration browser profile. This is an access control for a prototype, not a complete production identity system. The current server is Python standard library, not Tornado; that choice keeps the demo running when local package access is limited.

Production design may add an accelerator-equipped LinuxONE, platform encryption, stronger identity management, redundant nodes, monitored storage, and an operational data agreement. None of those are demonstrated by this repository until separately verified on the target system.
