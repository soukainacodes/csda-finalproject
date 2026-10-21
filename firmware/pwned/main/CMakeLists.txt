idf_component_register(
    SRCS "pwned.c"
    INCLUDE_DIRS "."
    REQUIRES nvs_flash esp_wifi esp_netif esp_event
)
