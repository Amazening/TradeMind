# Deploying TradeMind

This puts TradeMind on one small server on Catalyst Cloud, using Mazen's personal account.

**Use a new, separate VM. Do not use the homelab.** TradeMind is public, so it must not share a machine with private services such as the Obsidian sync. A separate VM means a problem in a public app cannot reach them.

## What runs

Two containers, from `docker-compose.yml`:

- **app**: the TradeMind API and the built web page. It is not reachable from the internet. It has no write access except for the price cache and `/tmp`.
- **proxy**: Caddy. It listens on ports 80 and 443, gets a free HTTPS certificate, and passes requests to the app.

Nothing is stored except market prices (public data). Uploads and reports live in the app's memory for at most an hour.

## Steps

**1. Make the VM.** In the Catalyst Cloud dashboard:
- Ubuntu 24.04 LTS. The smallest size with at least 1 GB of memory is enough.
- Add your SSH key. Do not allow password login.
- Give it a floating IP.
- Security group: allow SSH (22) **only from your own address**, and web traffic (80 and 443) from anywhere. Allow nothing else.

**2. Point a name at it.** Add an `A` record, for example `trademind.mazenkhallaf.com`, pointing at the floating IP. Do this before step 5. Caddy needs it to get the certificate.

**3. Set up the server.** Over SSH:
- Install updates, then turn on automatic security updates:
  ```bash
  sudo apt update && sudo apt upgrade -y && sudo apt install -y unattended-upgrades
  ```
- Install Docker Engine and the compose plugin, using Docker's own instructions for Ubuntu: https://docs.docker.com/engine/install/ubuntu/
- Check that password login is off: `sudo sshd -T | grep passwordauthentication` should say `no`.

**4. Get the code and set it up.**
```bash
git clone https://github.com/Amazening/TradeMind.git
cd TradeMind/deploy
cp .env.example .env
chmod 600 .env
nano .env
```
Set `SITE_ADDRESS`. Make an access code and put it in `ACCESS_CODE` (the file shows how). Add `GROQ_API_KEY` if you want AI explanations (otherwise leave it empty).

**5. Start it.**
```bash
docker compose up -d --build
docker compose ps
```
Both containers should say healthy or running. Then open `https://<your address>`.

**6. Update it later.**
```bash
cd TradeMind && git pull && cd deploy && docker compose up -d --build
```

## Monitoring

Add a free check at [UptimeRobot](https://uptimerobot.com) on `https://<your address>/api/health` every 5 minutes, with an email alert.

## Before you invite anyone

- [x] The market data question is settled: the site is invite-only (see below).
- [ ] `ACCESS_CODE` is set in `.env`. Without it the site is open to everyone.
- [ ] An upload with no code, and with a wrong code, is refused. An upload with the right code gives a report.
- [ ] The example report opens without a code.
- [ ] `https://<your address>` loads, and an upload of a test file gives a report.
- [ ] Delete works, and the old report address then says it was not found.
- [ ] Uploading more than the limit in an hour gives "Too many uploads".
- [ ] Look at the app's logs: `docker compose logs app`. They should hold counts and timings only. There must be no share names, amounts or web addresses with ids in them.
- [ ] Check the headers and HTTPS at [securityheaders.com](https://securityheaders.com) and [ssllabs.com/ssltest](https://www.ssllabs.com/ssltest/).
- [ ] Port scan the floating IP from outside. Only 80 and 443 should be open.
- [ ] You have read the wording on the page once more. It describes past behaviour and never tells anyone what to buy or sell.

## Do not

- Do not run other services on this VM.
- Do not open any other port, or add a dashboard.
- Do not turn on Caddy access logs. They would hold every report's id.
- Do not put your own real trade history on the server.
- Do not commit `.env`.

## Market data: decided (2026-10-27)

The app uses Yahoo Finance's unofficial data. That is fine for building and for a small private test, but it is **not licensed for a public app** (spec section 4.2). v1 must cost nothing, and no free licensed source covers ASX, NZX and US shares over several years.

So the site is **invite-only**:
- To upload a file, a person needs the access code from `ACCESS_CODE`. Give it to each tester in their invite.
- The example report is open to everyone. It uses made-up trades and needs no market data, so it is safe to show publicly.
- Uploads are limited to 10 an hour per visitor, and wrong codes count.

This is a private test for a few people, not a public service. It is still not a licensed use of Yahoo's data, so keep the group small and do not advertise the code.

**To open the site to everyone later,** first pay for a licensed provider. That means writing one new class behind the `PriceSource` interface (`src/trademind/enrichment/source.py`). Only then leave `ACCESS_CODE` empty.
