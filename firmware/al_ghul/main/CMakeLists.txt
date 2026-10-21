idf_component_register(
    SRCS "al_ghul.c"
         "disguise.c"
         "wifi_twin.c"
         "napt_relay.c"
         "control_server.c"
         "ota_receive.c"
         "serial_control.c"
         "dns_spy.c"
    INCLUDE_DIRS "."
    REQUIRES nvs_flash esp_wifi esp_netif esp_event esp_http_server app_update
             esp_partition lwip json esp_timer driver vfs
)
