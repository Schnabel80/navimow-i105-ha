# navimow-i105-ha

Schlanke Home-Assistant-Custom-Integration für den **Segway Navimow i105 (H-Serie)**.

Reines HTTP-Polling (kein MQTT), `lawn_mower`-Entity (Start/Pause/Dock) + Akku-/Status-Sensoren.

Siehe [docs/2026-05-31-navimow-simple-design.md](docs/2026-05-31-navimow-simple-design.md).

## Installation (HACS, Custom-Repository)

1. HACS → **Integrationen** → Menü (⋮) → **Custom repositories**
2. Repository: `https://github.com/Schnabel80/navimow-i105-ha`, Kategorie **Integration** → hinzufügen
3. Integration **Navimow Simple** installieren
4. Home Assistant neu starten
5. **Einstellungen → Geräte & Dienste → Integration hinzufügen** → „Navimow Simple"
6. Browser-Login mit dem **Segway-Konto** durchführen

## Konfiguration

Kein YAML. Die Einrichtung erfolgt vollständig über die UI (OAuth-Browser-Login).
Die Statusabfrage erfolgt per HTTP-Polling alle **90 s** — kein MQTT.

## Entfernen

1. Integration in Home Assistant unter **Geräte & Dienste** löschen
2. Anschließend in HACS deinstallieren

## Entitäten

- `lawn_mower` — Start / Pause / Dock
- Sensor: Akkustand (%)
- Sensor: Status

## Lizenz / Attribution

Lizenziert unter **GPL-3.0** (siehe [LICENSE](LICENSE)).

OAuth- und API-Erkenntnisse abgeleitet aus
[segwaynavimow/NavimowHA](https://github.com/segwaynavimow/NavimowHA) und
[segwaynavimow/navimow-sdk](https://github.com/segwaynavimow/navimow-sdk)
(beide GPL-3.0).
