// OTA receive endpoint. The laptop POSTs a firmware image (the normal twin
// image for updates, or the "kill" image for the finisher) to /ota. The image
// is written to the inactive OTA slot, marked bootable, and the board reboots
// into it. This is the authenticated-by-design update channel the kill-switch
// rides on: it is a command AL-GHUL is built to obey, not an exploit.
#pragma once

#include "esp_http_server.h"

esp_err_t ota_receive_handler(httpd_req_t *req);
