#ifndef _HCI_H
#define _HCI_H

#include <bluetooth/bluetooth.h>
#include <sys/ioctl.h>

#ifndef HCIGETDEVINFO
#define HCIGETDEVINFO _IOR('H', 211, int)
#endif

struct hci_dev_info {
    uint16_t dev_id;
    char name[8];
    bdaddr_t bdaddr;
    uint32_t flags;
    uint8_t type;
    uint8_t features[8];
    uint32_t pkt_type;
    uint32_t link_policy;
    uint32_t link_mode;
    uint16_t acl_mtu;
    uint16_t acl_pkts;
    uint16_t sco_mtu;
    uint16_t sco_pkts;
    uint32_t stat[10];
};

#endif
