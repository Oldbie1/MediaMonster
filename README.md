# Media Monster
Android-app (Kotlin + Jetpack Compose) voor de NUC11, met een kleine Python-API.

## Afgesproken versie 1
- Containers: groen bij actief/gezond, geel bij een beschikbare update, rood bij gestopt of ongezond. Rood heeft voorrang.
- Starten, stoppen, herstarten, updaten en logs.
- Vrije en totale opslag op C:, DS224 en DS716.
- Verbinding via eigen LAN, Tailscale of https://mm.tenhaaf.nu. Updates uitsluitend op verzoek.
- Pushmeldingen via Firebase bij gestopte/ongezonde containers en beschikbare updates.

## Project
- android/: Kotlin + Jetpack Compose.
- backend/: Python 3, zonder externe packages; Docker CLI en Compose nodig.
- docs/: inventarisatie en installatie.

De API draait op de Linux/WSL-host zodat hij Docker en de daadwerkelijke NAS-mounts kan uitlezen.
Bewaar API-tokens uitsluitend in de serveromgeving en op de telefoon, nooit in Git.
