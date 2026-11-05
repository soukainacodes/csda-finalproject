idf_component_register(
    SRCS "sniffer.c" "beacon_parse.c" "detector.c"
    INCLUDE_DIRS "."
    REQUIRES esp_wifi esp_netif esp_event nvs_flash esp_timer driver
)
