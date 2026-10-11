# IPTVibe Runtime

Public runtime mirror used by the IPTVibe Android TV application.

This repository contains only runtime data and release artifacts needed by installed clients:

- `runtime/catalogo.txt`
- `runtime/canais.txt`
- `runtime/restritos.txt`
- `runtime/vod/`
- `runtime/monitor/fontes.json`

The private source repository remains `frittcat/IPTVibe`.

Runtime catalog/source data is synchronized automatically from the authorized upstream sources so installed clients can use IPTVibe-owned URLs without embedding legacy origin names in the APK.

Scheduled and manual synchronization perform structural catalog checks only. They do not request live or VOD media from providers. Real playback, content identity and prolonged continuity must be measured exclusively on the owner's BlueStacks before changing the reviewed source policy. Retained 24-hour and Pluto inventories survive upstream replacements; retaining a channel does not certify that its sources work. Upstream application changes are recorded for adaptation and Android validation rather than published as automatically compatible APK changes.
