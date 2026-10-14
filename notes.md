# Release Notes — R.5.1 (2.16.443.8525-master)

| Field | Value |
|-------|-------|
| Build | `2.16.443.8525-master` |
| Environment | `qa` |
| Promoted at | 2026-10-06 11:50 UTC |
| Generated | 2026-10-14 12:38 UTC |
| Compared to | `2.16.203.8402-master` |
| Changed components | 44 |
| Unchanged components | 9 |

---

## Changes by JIRA Ticket

### DORA-6775, DORA-6809, DORA-6825

**DORA-6825: make twistlock_scan_next report-only permanently (reword DORA-6775 step) (#89)**  
Components: `boot-strap-management`, `bootstrap`

### DORA-6787

**Merge pull request #3 from Inmarsat/DORA-6787-ciglue-proxy**  
Components: `asob-services`, `kapacitor`

### DORA-6809, DORA-6825

**DORA-6825: make twistlock_scan_next report-only (next publish no longer gated) (#50)**  
Components: `appnat`, `cce`, `crf`, `diag-tool`, `edge-api-webserver`, `edge-identity-api`, `etcd`, `mgmt`, `mosquitto`, `netmon`, `sdwan-geo-fencing-agent`, `sdwan-interface-control-agent`, `sdwan-sdep-selection-agent`, `secrets-scheduler`, `security-validation`, `splunk-uf`, `svn-checker`, `telegraf`, `vault`, `voice`

### MAS-13998

**MAS-13998: upgrade Edge collector ECR from v0.107 to v0.156 (#16)**  
Components: `otel-collector`

### REL-1732

**REL-1732: run edge_disk_maintenance as a scheduled playbook (#173)**  
Components: `updater`

### SDWAN-13245

**Merge pull request #17 from Inmarsat/SDWAN-13245/route-concentrator-nlb-subnet**  
Components: `overlay-crf`

### SDWAN-13474

**SDWAN-13474 Some assurance data metrics from the VS60 are 0 (#327)**  
Components: `vseacu`, `vseapi`, `vseappmon`, `vseconfigfilestore`, `vsefleet`, `vselogger`, `vsemap`, `vsemodemapi`, `vsetcp`

### SDWAN-13555

**SDWAN-13555 remove mqtt exporter (#357)**  
Components: `razorlink-logs-forwarder`

### SDWAN-13619

**SDWAN-13619 corrupt state file (#30)**  
Components: `asob-updates-manager`

### (No JIRA ticket)

Components: `hosting`, `hosting-secondary`, `mosquitto-vars`, `razorlink-asob-processor`, `telegraf-host`, `telegraf-network`

---

## Component Version Changes

| Component | From | To | JIRA | Commit | Author | Message |
|-----------|------|----|------|--------|--------|---------|
| `appnat` | `1.0.19` | **`1.0.23`** | DORA-6825, DORA-6809 | `efb57540` | Joe Holder | DORA-6825: make twistlock_scan_next report-only (next publish no longer gated) (#50) |
| `asob-services` | `0.0.12` | **`0.0.13`** | DORA-6787 | `d662393f` | Joe Holder | Merge pull request #3 from Inmarsat/DORA-6787-ciglue-proxy |
| `asob-updates-manager` | `0.0.11` | **`0.0.31`** | SDWAN-13619 | `e642990a` | Bogdan Ungureanu | SDWAN-13619 corrupt state file (#30) |
| `boot-strap-management` | `1.0.37` | **`1.0.43`** | DORA-6825, DORA-6809, DORA-6775 | `0221b67e` | Joe Holder | DORA-6825: make twistlock_scan_next report-only permanently (reword DORA-6775 step) (#89) |
| `bootstrap` | `1.0.37` | **`1.0.43`** | DORA-6825, DORA-6809, DORA-6775 | `7fdc9a3c` | Joe Holder | DORA-6825: make twistlock_scan_next report-only permanently (reword DORA-6775 step) (#170) |
| `cce` | `1.0.16` | **`1.0.20`** | DORA-6825, DORA-6809 | `6170b96b` | Joe Holder | DORA-6825: make twistlock_scan_next report-only (next publish no longer gated) (#45) |
| `crf` | `1.0.56` | **`1.0.60`** | DORA-6825, DORA-6809 | `895ff3a3` | Joe Holder | DORA-6825: make twistlock_scan_next report-only (next publish no longer gated) (#118) |
| `diag-tool` | `0.3.3` | **`0.3.8`** | DORA-6825, DORA-6809 | `ecf56e3c` | Joe Holder | DORA-6825: make twistlock_scan_next report-only (next publish no longer gated) (#51) |
| `edge-api-webserver` | `1.0.27` | **`1.0.32`** | DORA-6825, DORA-6809 | `42c03faf` | Joe Holder | DORA-6825: make twistlock_scan_next report-only (next publish no longer gated) (#34) |
| `edge-identity-api` | `1.0.20` | **`1.0.25`** | DORA-6825, DORA-6809 | `b1da3b89` | Joe Holder | DORA-6825: make twistlock_scan_next report-only (next publish no longer gated) (#24) |
| `etcd` | `1.0.12` | **`1.0.15`** | DORA-6825, DORA-6809 | `32039389` | Joe Holder | DORA-6825: make twistlock_scan_next report-only (next publish no longer gated) (#32) |
| `hosting` | `1.0.39` | **`1.0.45`** | — | `—` | — | — |
| `hosting-secondary` | `1.0.39` | **`1.0.45`** | — | `—` | — | — |
| `kapacitor` | `1.0.14` | **`1.0.18`** | DORA-6787 | `3801df23` | Joe Holder | DORA-6787: route kapacitor's CI-Glue publish calls through the bastion SOCKS proxy (#44) |
| `mgmt` | `1.0.34` | **`1.0.38`** | DORA-6825, DORA-6809 | `d7e7146c` | Joe Holder | DORA-6825: make twistlock_scan_next report-only (next publish no longer gated) (#91) |
| `mosquitto` | `1.0.13` | **`1.0.16`** | DORA-6825, DORA-6809 | `4212f48f` | Joe Holder | DORA-6825: make twistlock_scan_next report-only (next publish no longer gated) (#35) |
| `mosquitto-vars` | `1.0.13` | **`1.0.16`** | — | `—` | — | — |
| `netmon` | `2.0.13` | **`2.0.16`** | DORA-6825, DORA-6809 | `4787cdff` | Joe Holder | DORA-6825: make twistlock_scan_next report-only (next publish no longer gated) (#36) |
| `otel-collector` | `0.0.14` | **`0.0.15`** | MAS-13998 | `f08916f7` | John Mayock | MAS-13998: upgrade Edge collector ECR from v0.107 to v0.156 (#16) |
| `overlay-crf` | `0.0.11` | **`0.0.14`** | SDWAN-13245 | `756bfc0c` | EuanBotham7 | Merge pull request #17 from Inmarsat/SDWAN-13245/route-concentrator-nlb-subnet |
| `razorlink-asob-processor` | `0.0.99` | **`0.0.116`** | — | `—` | — | — |
| `razorlink-logs-forwarder` | `0.0.240` | **`0.0.249`** | SDWAN-13555 | `e66b07c8` | alexandrturcan1 | SDWAN-13555 remove mqtt exporter (#357) |
| `sdwan-geo-fencing-agent` | `0.0.50` | **`0.0.55`** | DORA-6825, DORA-6809 | `efcb3a4e` | Joe Holder | DORA-6825: make twistlock_scan_next report-only (next publish no longer gated) (#58) |
| `sdwan-interface-control-agent` | `0.0.20` | **`0.0.24`** | DORA-6825, DORA-6809 | `47d0a1ae` | Joe Holder | DORA-6825: make twistlock_scan_next report-only (next publish no longer gated) (#23) |
| `sdwan-sdep-selection-agent` | `0.0.27` | **`0.0.32`** | DORA-6825, DORA-6809 | `4cb05ce0` | Joe Holder | DORA-6825: make twistlock_scan_next report-only (next publish no longer gated) (#29) |
| `secrets-scheduler` | `1.0.70` | **`1.0.74`** | DORA-6825, DORA-6809 | `9fd189aa` | Joe Holder | DORA-6825: make twistlock_scan_next report-only (next publish no longer gated) (#54) |
| `security-validation` | `1.0.33` | **`1.0.37`** | DORA-6825, DORA-6809 | `545fb0ab` | Joe Holder | DORA-6825: make twistlock_scan_next report-only (next publish no longer gated) (#131) |
| `splunk-uf` | `1.0.13` | **`1.0.17`** | DORA-6825, DORA-6809 | `b7abe82f` | Joe Holder | DORA-6825: make twistlock_scan_next report-only (next publish no longer gated) (#60) |
| `svn-checker` | `1.0.13` | **`1.0.19`** | DORA-6825, DORA-6809 | `ebb22ab6` | Joe Holder | DORA-6825: make twistlock_scan_next report-only (next publish no longer gated) (#65) |
| `telegraf` | `1.0.16` | **`1.0.22`** | DORA-6825, DORA-6809 | `36ee32d0` | Joe Holder | DORA-6825: make twistlock_scan_next report-only (next publish no longer gated) (#60) |
| `telegraf-host` | `1.0.16` | **`1.0.22`** | — | `—` | — | — |
| `telegraf-network` | `1.0.16` | **`1.0.22`** | — | `—` | — | — |
| `updater` | `1.0.68` | **`1.0.75`** | REL-1732 | `43d77b74` | belavarasan | REL-1732: run edge_disk_maintenance as a scheduled playbook (#173) |
| `vault` | `1.0.15` | **`1.0.18`** | DORA-6825, DORA-6809 | `75f948e9` | Joe Holder | DORA-6825: make twistlock_scan_next report-only (next publish no longer gated) (#38) |
| `voice` | `1.0.55` | **`1.0.62`** | DORA-6825, DORA-6809 | `ff168890` | Joe Holder | DORA-6825: make twistlock_scan_next report-only (next publish no longer gated) (#129) |
| `vseacu` | `1.0.152` | **`1.0.156`** | SDWAN-13474 | `f1421151` | nicksmith1973 | SDWAN-13474 Some assurance data metrics from the VS60 are 0 (#327) |
| `vseapi` | `1.0.152` | **`1.0.156`** | SDWAN-13474 | `f1421151` | nicksmith1973 | SDWAN-13474 Some assurance data metrics from the VS60 are 0 (#327) |
| `vseappmon` | `1.0.152` | **`1.0.156`** | SDWAN-13474 | `f1421151` | nicksmith1973 | SDWAN-13474 Some assurance data metrics from the VS60 are 0 (#327) |
| `vseconfigfilestore` | `1.0.152` | **`1.0.156`** | SDWAN-13474 | `f1421151` | nicksmith1973 | SDWAN-13474 Some assurance data metrics from the VS60 are 0 (#327) |
| `vsefleet` | `1.0.152` | **`1.0.156`** | SDWAN-13474 | `f1421151` | nicksmith1973 | SDWAN-13474 Some assurance data metrics from the VS60 are 0 (#327) |
| `vselogger` | `1.0.152` | **`1.0.156`** | SDWAN-13474 | `f1421151` | nicksmith1973 | SDWAN-13474 Some assurance data metrics from the VS60 are 0 (#327) |
| `vsemap` | `1.0.152` | **`1.0.156`** | SDWAN-13474 | `f1421151` | nicksmith1973 | SDWAN-13474 Some assurance data metrics from the VS60 are 0 (#327) |
| `vsemodemapi` | `1.0.152` | **`1.0.156`** | SDWAN-13474 | `f1421151` | nicksmith1973 | SDWAN-13474 Some assurance data metrics from the VS60 are 0 (#327) |
| `vsetcp` | `1.0.152` | **`1.0.156`** | SDWAN-13474 | `f1421151` | nicksmith1973 | SDWAN-13474 Some assurance data metrics from the VS60 are 0 (#327) |

---

## Unchanged Components

`edge-assurance`, `edge-service-management`, `feas-routing-service`, `influxdb`, `inservice-cert-refresh-playbook`, `sdwan-hsts-agent`, `sdwan-sla-controller`, `sdwan-test-validation-agent`, `secrets-refresh-playbook`
