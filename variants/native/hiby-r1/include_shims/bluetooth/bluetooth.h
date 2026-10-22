#ifndef _BLUETOOTH_H
#define _BLUETOOTH_H

#include <stdint.h>
#include <sys/socket.h>

#ifndef AF_BLUETOOTH
#define AF_BLUETOOTH 31
#endif

typedef struct {
    uint8_t b[6];
} __attribute__((packed)) bdaddr_t;

#endif
