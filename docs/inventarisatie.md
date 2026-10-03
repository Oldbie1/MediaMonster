# Inventarisatie 5 september 2026

Dit was de alleen-lezen inventarisatie toen Docker nog in Linux/WSL op de NUC11 draaide. De huidige host is een Ubuntu-VM in Proxmox. Opslagmeting gebruikt nu **NUC 11 = `/`** (niet `/mnt/c`). NAS-paden DS224 en DS716 zijn gelijk gebleven.

Bron destijds: SSH-inventarisatie en eerdere afspraak in "Schrijfproblemen SABnzbd".

- NUC SSH: marco@192.168.72.23, poort 12107.
- Docker in Linux/WSL; Compose v5.5.0, Python 3.14.4.
- Containers: sonarr, radarr, sabnzbd, mealie, seerr, prowlarr, homepage, bazarr, homarr, qbittorrent, uptime-kuma, watchtower.
- Sonarr en Radarr waren tijdens inventarisatie gestopt (exitcode 137). Geen herstel uitgevoerd.
- Compose Sonarr: /home/marco/docker/sonarr; Radarr: /home/marco/docker/radarr.
- C: is /mnt/c (9p).
- DS224: /mnt/DS224/video (CIFS //192.168.72.12/video).
- DS716: /mnt/DS716/video (CIFS //192.168.72.10/video).
- /mnt/DS224 en /mnt/DS716 zelf zijn GEEN NAS-mounts; daarop meten zou ten onrechte WSL-opslag tonen.
- Java, Gradle en Android SDK niet aangetroffen op de ontwikkel-pc.

Een draaiende container zonder Docker-healthcheck heet "Actief": applicatiegezondheid is daarmee niet bewezen.
Updatecontrole mag mislukken; dat is "Onbekend" en nooit "Geen update".
