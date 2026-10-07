# Inventarisatie

Laatst bijgewerkt: 3 oktober 2026. Host en paden horen bij de huidige Ubuntu-VM. De containerlijst en SSH-gegevens komen uit de alleen-lezen inventarisatie van 5 september 2026; die zijn hier niet opnieuw geverifieerd.

## Host
- Naam: Media Monster
- Ubuntu-VM in Proxmox, op de NUC11
- Live API: `/home/marco/mediamonster`
- Bron: `\\synology\home\mediamonster` en https://github.com/Oldbie1/MediaMonster
- Laatst bekende SSH: `marco@192.168.72.23`, poort 12107
- App: 1.0.13, versiecode 45

## Docker
- Compose-projecten onder `/home/marco/docker/`
- Toegestane namen: `/etc/media-monster-containers.conf` (geen stille fallback)
- Laatst bekende lijst: sonarr, radarr, sabnzbd, mealie, seerr, prowlarr, homepage, bazarr, homarr, qbittorrent, uptime-kuma, watchtower
- Een draaiende container zonder healthcheck heet "Actief"
- Updatecontrole mag mislukken: dat is "Onbekend", nooit "Geen update"

## Opslag
- NUC 11: `/` (systeenschijf van de Ubuntu-VM)
- DS224: `/mnt/DS224/video` (CIFS `//192.168.72.12/video`)
- DS716: `/mnt/DS716/video` (CIFS `//192.168.72.10/video`)
- `/mnt/DS224` en `/mnt/DS716` zelf zijn geen NAS-volumes; daarop meten toont de VM-schijf

## Netwerk
- LAN, Tailscale of `https://mm.tenhaaf.nu`
- Laatst bekende Tailscale-adres: `http://100.108.14.95:8787`
- Geen Funnel of internet-portforwarding voor de beheer-API
