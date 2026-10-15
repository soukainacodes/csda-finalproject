"""Lab configuration for the Watcher and the arms-race orchestrator.

Fill in your own values before a live run. Everything here describes YOUR OWN
lab: your router, your AL-GHUL board, your sniffer. Nothing else is ever touched.
"""
from pathlib import Path

# ---- Your own network (the thing being cloned) -----------------------------
REAL_ROUTER_SSID  = "YOUR_LAB_SSID"
# The REAL AP's BSSID (e.g. your phone hotspot). This is the label anchor: during
# capture, a frame from this BSSID is "real", a frame on the same SSID from any
# other BSSID is "twin". Find it from the sniffer scan or `netsh wlan show interfaces`.
REAL_ROUTER_BSSID = "aa:bb:cc:dd:ee:ff"

# ---- AL-GHUL control plane -------------------------------------------------
# The twin's SoftAP gateway. When the laptop joins the twin's own AP (Kaffi_FRI,
# which out-signals the real one), AL-GHUL is reachable here. This avoids needing
# to know its DHCP-assigned uplink IP.
ALGHUL_CONTROL_URL = "http://192.168.4.1"

# ---- Sniffer serial link ---------------------------------------------------
SNIFFER_SERIAL_PORT = "COM14"     # the ESP32-S3 sniffer (CH343 UART); was COM8 on the classic ESP32
SNIFFER_BAUD        = 115200

# ---- Paths (all off Google Drive, under the project) -----------------------
ROOT        = Path(__file__).resolve().parents[2]      # C:\Users\souka\AL-GHUL
DATA_DIR    = ROOT / "watcher" / "data"
MODEL_DIR   = ROOT / "watcher" / "models"
EXPERIMENTS = ROOT / "experiments"
ROUND_LOGS  = EXPERIMENTS / "round-logs"
PLOTS       = EXPERIMENTS / "plots"

for _d in (DATA_DIR, MODEL_DIR, ROUND_LOGS, PLOTS):
    _d.mkdir(parents=True, exist_ok=True)
