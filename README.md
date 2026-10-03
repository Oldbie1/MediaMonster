# Media Monster
Android-app (Kotlin + Jetpack Compose) plus een kleine Python-API voor de Media Monster-VM: Ubuntu in Proxmox, op de NUC11.

Huidige appversie: **1.0.13** (versiecode 45).

## Afgesproken versie 1
- Containers: groen bij actief/gezond, geel bij een beschikbare update, rood bij gestopt of ongezond. Rood heeft voorrang.
- Starten, stoppen, herstarten, updaten en logs.
- Vrije en totale opslag op NUC 11, DS224 en DS716.
- Verbinding via eigen LAN, Tailscale of https://mm.tenhaaf.nu. Handmatige updates op verzoek; optioneel automatisch bijwerken op de NUC.
- Pushmeldingen via Firebase bij gestopte/ongezonde containers, beschikbare updates of uitgevoerde automatische updates.

## Project
- android/: Kotlin + Jetpack Compose.
- backend/: Python 3, zonder externe packages; Docker CLI, Compose en Buildx nodig.
- docs/: inventarisatie, installatie en versienotities.
- releases/: oudere APK-bestanden. Nieuwe APK’s horen als GitHub Release, niet als groot binair bestand in de broncode.

De API draait op de Ubuntu-VM zodat hij Docker en de NAS-mounts kan uitlezen.
De actieve installatie staat in `/home/marco/mediamonster`. Wijzig die map pas na testen.
Broncode staat op `\\synology\home\mediamonster` en in deze GitHub-repo.

Bewaar API-tokens, wachtwoordhashes en `firebase-service-account.json` uitsluitend in de serveromgeving, nooit in Git.
`android/app/google-services.json` is Firebase-clientconfiguratie, geen serviceaccountsleutel. Beperk die sleutel in Firebase tot deze app en de toegestane API’s.

## Automatisering
Achtergrondupdatecontrole, automatisch bijwerken en automatisch herstarten zijn onafhankelijke schakelaars.
Uitzetten van automatisch herstarten stopt de periodieke updatecontrole niet.
