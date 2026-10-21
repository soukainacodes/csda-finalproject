# AL-GHUL danger demo: what the twin saw

Captured 2026-10-20 23:25 on the isolated lab. Victim device MAC on the twin: `62:39:e1:13:23:f0`.

The victim's traffic was fully **HTTPS-encrypted**. AL-GHUL (the evil twin) could not read any contents, but as the device's DNS server it logged **every domain the device reached**, its whole browsing map.

## Recognisable services this person uses
- Branch (deep-link tracking)
- Facebook
- Firebase/Google Analytics
- Google
- Miro
- Sentry (app error tracking)
- Tailscale (a VPN)
- YouTube
- YouTube (images)

## Every domain the twin logged (11 unique)
- `android.apis.google.com`  (x1)
- `api2.branch.io`  (x1)
- `app-measurement.com`  (x1)
- `i.ytimg.com`  (x1)
- `log.tailscale.com`  (x1)
- `m.youtube.com`  (x1)
- `miro.com`  (x1)
- `mtalk.google.com`  (x1)
- `o881784.ingest.sentry.io`  (x1)
- `www.facebook.com`  (x1)
- `www.youtube.com`  (x1)

## The lesson
HTTPS hides the *contents*, not *where you go*. From one device on the twin, the attacker learns the victim's social media, video habits, analytics/tracking backends, even that they run a VPN (Tailscale). Mitigation: **encrypted DNS (DoH/DoT) and Encrypted Client Hello (ECH)** hide this metadata; **WPA3/PMF** stops the device joining the twin at all.