# Installatie en gebruik

Huidige host: Ubuntu-VM in Proxmox (Media Monster / NUC11). Niet meer de eerdere WSL/Windows-opstelling.

## Android
Open de map `android` in Android Studio, of bouw met JDK 17 en Android SDK 36:

    ./gradlew assembleDebug

De ontwikkelbuild staat na compilatie in `app/build/outputs/apk/debug/app-debug.apk`.
Installeer die APK op een Android-telefoon (Android 8 of nieuwer).
Officiële releases worden vanaf de NUC aangeboden via `/v1/app/update`. Publiceer een nieuwe APK als GitHub Release; zet hem niet als groot binair bestand in Git.

## API op de Ubuntu-VM
De live-installatie staat in `/home/marco/mediamonster`. Wijzig die map pas na testen.

Gebruik Python 3.11+ onder dezelfde Linux-gebruiker die Docker mag bedienen.
Vanuit `backend/`:

    ./install-linux.sh /home/marco/mediamonster
    ./set-password.sh

`install-linux.sh` maakt `api.env` (mode 0600) aan als die ontbreekt, installeert de user-systemd-unit en zet linger aan. Standaardwaarden in dat script:

- `MM_BIND=0.0.0.0`
- `MM_PORT=8787`
- `MM_STORAGE={"NUC 11":"/","DS224":"/mnt/DS224/video","DS716":"/mnt/DS716/video"}`

Zonder `MM_STORAGE` gebruikt `server.py` dezelfde standaard: systeenschijf `/`, niet het oude WSL-pad `/mnt/c`.
Meet alleen echte mounts. `/mnt/DS224` en `/mnt/DS716` zelf zijn geen NAS-volumes.

In de app: API-adres zoals `192.168.72.23:8787`, `mm.tenhaaf.nu` of het Tailscale-adres. HTTP voor LAN/Tailscale; HTTPS buiten die omgeving. Zet deze beheer-API niet via port-forwarding open op internet.

## Gedrag
- Omlaag vegen vernieuwt de status en controleert alle containers op updates.
- Containers zonder healthcheck tonen "Actief".
- Updatecontrole vergelijkt de registry-image met de geïnstalleerde image zonder pull.
- Onbereikbare registry geeft onbekende updatestatus, nooit "geen update".
- Update haalt via de bestaande Compose-configuratie de image op en maakt alleen de gekozen service opnieuw aan.
- Automatisch bijwerken en automatisch herstarten zijn onafhankelijk. Herstarten uitzetten stopt de achtergrondupdatecontrole niet.
- Stille vensters: 01:15–01:30 en 03:45–04:30 (Europe/Amsterdam). Onderhoudsmodus pauzeert controles en meldingen.
- Containeracties zijn globaal geserialiseerd.
- De API heeft de Docker-rechten van de uitvoerende gebruiker.

## Geheimen
- Token: `api.env` (`MM_TOKEN`), nooit in Git.
- Inlogwachtwoord: alleen als hash in `password.hash`.
- Firebase-server: `/home/marco/mediamonster/firebase-service-account.json`, nooit in Git.
- `google-services.json` in de Android-app is clientconfiguratie. Beperk de sleutel in Firebase tot deze app.

## Verificatie
    cd backend
    python3 -m unittest -v

## Bouwreferenties
- https://developer.android.com/build/releases/gradle-plugin
- https://developer.android.com/develop/ui/compose/bom
