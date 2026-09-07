# API-installatie — 5 september 2026

Geïnstalleerd:
- NUC: /home/marco/mediamonster/server.py
- Geheim token: /home/marco/mediamonster/api.env, mode 0600.
- Gebruikersservice: ~/.config/systemd/user/mediamonster-api.service.
- systemctl --user enable --now mediamonster-api.service uitgevoerd.
- API luistert uitsluitend op 127.0.0.1:8787.
- Windows bereikt deze API via WSL localhost-forwarding.
- Geen token: HTTP 401. Met token: HTTP 200, twaalf containers en drie opslagmetingen.
- Geen productiecontainers gewijzigd.

Nog niet uitgevoerd:
Tailscale Serve TCP-forwarder, omdat automatische goedkeuringscontrole expliciete toestemming eist:
    tailscale serve --bg --tcp=8787 tcp://127.0.0.1:8787

Na goedkeuring wordt het telefoonadres http://100.108.14.95:8787.
Dit is uitsluitend bereikbaar binnen het bestaande tailnet en blijft achter API-tokenauthenticatie.
Geen Funnel, internetportforwarding of nieuwe LAN-firewallregel.
Tailscale Serve-configuratie was vooraf leeg.

Automatisch starten geldt bij starten van de gebruikersmanager. Linger staat momenteel uit.
Volledige herstartcontrole en toegang vanaf telefoon zijn nog niet uitgevoerd.

## Tailscale geactiveerd na expliciete toestemming
- Tailscale Serve draait blijvend: TCP 8787 naar 127.0.0.1:8787, uitsluitend tailnet.
- App-adres: http://100.108.14.95:8787
- Getest vanaf Windows op de NUC via dit Tailscale-adres: HTTP 200 met token, twaalf containers, drie online opslaglocaties.
- Zonder token: HTTP 401.
- Het token is aan de gebruiker verstrekt en staat niet in de projectdocumentatie.
- Een verbinding vanaf de telefoon zelf moet door de gebruiker worden bevestigd.
- De eerdere sectie "Nog niet uitgevoerd" voor Tailscale Serve is hiermee achterhaald.

## Automatische updatecontrole
De API controleert vanaf nu alle containers op de achtergrond bij het starten.
Geslaagde resultaten worden circa 15 minuten gecachet; mislukte controles worden na circa één minuut opnieuw geprobeerd.
Maximaal drie registrycontroles tegelijk. Het dashboard wacht niet op deze controles.
Er worden geen images opgehaald of updates geïnstalleerd.
De bestaande APK werkt hiermee: tik op Vernieuwen om de laatste resultaten op te halen.
Tests: 15 geslaagd, inclusief automatisch starten, cache, retries en herstel na een monitorfout.

## Correctie digestvergelijking
De eerdere vergelijking van registry-configdigest met container Image-ID was onjuist voor de containerd image store.
Nu vergelijkt de API registry-descriptors/repositorydigests van de geïnstalleerde containerimage met de actuele registry.
Regressietests toegevoegd; totaal 20 tests geslaagd.
Live resultaat na installatie: uitsluitend Sonarr heeft available=true; de overige elf containers false.
De eerdere melding dat alle twaalf containers updates hadden was foutief.
Registrycontrole vereist Docker Buildx, aanwezig op de NUC.
Referentie: https://docs.docker.com/reference/cli/docker/buildx/imagetools/inspect/
