idf_component_register(
    SRCS "kill.c"
    INCLUDE_DIRS "."
    REQUIRES spi_flash esp_partition app_update nvs_flash
)
