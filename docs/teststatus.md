# Bouw- en teststatus

Huidige bron: 1.0.13, versiecode 45. Gecontroleerd 3 oktober 2026 in deze repo.

## Backend
    cd backend
    python3 -m unittest -v

58 tests geslaagd, inclusief:

- authenticatie, wachtwoordhash en loginblokkade
- containerbestand zonder stille fallback
- digestvergelijking (containerd)
- updatecontrole onafhankelijk van automatisch herstarten
- automatische updates onafhankelijk van recovery
- standaardopslag NUC 11 = `/`, niet `/mnt/c`
- onderhoudsvensters, pushvoorkeuren en activiteitenlog

De tests lezen niet meer `/etc/media-monster-containers.conf` van de host.

## Android
Bronversie in `android/app/build.gradle.kts`: 1.0.13 / 45.
JDK 17, compile/target SDK 36. Deze cloud-omgeving heeft geen Android SDK; de APK is hier niet opnieuw gebouwd.

## Releases
De officiële 1.0.13-APK staat op de NAS en de VM, niet in Git.
`releases/` in deze repo bevat geen APK meer. Publiceer nieuwe builds als GitHub Release.

## Live-VM
`/home/marco/mediamonster` is vanuit deze omgeving niet bijgewerkt. Na merge: `backend/install-linux.sh` op de VM draaien, daarna de API-service herstarten.
