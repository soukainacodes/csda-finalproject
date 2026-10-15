#include "beacon_parse.h"

#include <stdio.h>
#include <string.h>
#include <inttypes.h>

// 802.11 MAC header is 24 bytes; beacon/probe-resp then have 12 bytes of fixed
// parameters (timestamp 8, beacon interval 2, capability 2) before the tagged
// information elements start at offset 36.
#define HDR_LEN       24
#define FIXED_LEN     12
#define IE_START      (HDR_LEN + FIXED_LEN)

// Escape an SSID for safe embedding in a JSON string.
static void json_escape(const uint8_t *in, int in_len, char *out, int out_sz)
{
    int o = 0;
    for (int i = 0; i < in_len && o < out_sz - 2; i++) {
        uint8_t c = in[i];
        if (c == '"' || c == '\\') {
            out[o++] = '\\';
            out[o++] = c;
        } else if (c < 0x20) {
            out[o++] = '?';
        } else {
            out[o++] = (char)c;
        }
    }
    out[o] = '\0';
}

void beacon_parse_and_print(const uint8_t *f, int len,
                            int8_t rssi, uint8_t channel, int64_t ts_us)
{
    if (len < IE_START) return;

    uint8_t subtype = (f[0] & 0xF0) >> 4;      // 8 = beacon, 5 = probe response
    const char *kind = (subtype == 8) ? "beacon"
                     : (subtype == 5) ? "probe_resp" : NULL;
    if (!kind) return;

    const uint8_t *sa    = f + 10;             // transmitter address
    const uint8_t *bssid = f + 16;             // BSSID (addr3)
    uint16_t bi  = (uint16_t)(f[32] | (f[33] << 8));
    uint16_t cap = (uint16_t)(f[34] | (f[35] << 8));

    char ssid[2 * 32 + 1] = {0};
    char ies[256];  int ie_o = 0;  ies[0] = '\0';
    char vnd[160];  int vn_o = 0;  vnd[0] = '\0';

    int pos = IE_START;
    while (pos + 2 <= len) {
        uint8_t tag  = f[pos];
        uint8_t ilen = f[pos + 1];
        if (pos + 2 + ilen > len) break;

        ie_o += snprintf(ies + ie_o, sizeof(ies) - ie_o, "%s%u", ie_o ? "," : "", tag);

        if (tag == 0) {                         // SSID
            json_escape(f + pos + 2, ilen > 32 ? 32 : ilen, ssid, sizeof(ssid));
        } else if (tag == 221 && ilen >= 3) {   // vendor-specific IE -> record OUI
            vn_o += snprintf(vnd + vn_o, sizeof(vnd) - vn_o,
                             "%s\"%02x:%02x:%02x\"", vn_o ? "," : "",
                             f[pos + 2], f[pos + 3], f[pos + 4]);
        }

        pos += 2 + ilen;
        if (ie_o >= (int)sizeof(ies) - 8 || vn_o >= (int)sizeof(vnd) - 16) break;
    }

    printf("{\"k\":\"%s\",\"t\":%" PRId64 ",\"ch\":%u,\"rssi\":%d,"
           "\"bssid\":\"%02x:%02x:%02x:%02x:%02x:%02x\","
           "\"sa\":\"%02x:%02x:%02x:%02x:%02x:%02x\","
           "\"ssid\":\"%s\",\"bi\":%u,\"cap\":%u,\"ies\":[%s],\"vendors\":[%s]}\n",
           kind, ts_us, channel, rssi,
           bssid[0], bssid[1], bssid[2], bssid[3], bssid[4], bssid[5],
           sa[0], sa[1], sa[2], sa[3], sa[4], sa[5],
           ssid, bi, cap, ies, vnd);
}
