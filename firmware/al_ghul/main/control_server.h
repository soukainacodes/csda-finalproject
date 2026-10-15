// HTTP control plane for the arms-race orchestrator on the laptop:
//   GET  /status    -> JSON: chip/heap/uplink/running-partition/current disguise
//   POST /disguise  -> JSON disguise patch; applied after the reply is sent
//   POST /ota       -> firmware image (normal update, or the kill image)
#pragma once

#include "esp_err.h"

esp_err_t control_server_start(void);
