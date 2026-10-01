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
