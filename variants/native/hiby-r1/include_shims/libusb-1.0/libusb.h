// libusb-1.0/libusb.h complete stub for HiBy R1 cross-compilation
//
// The Pine libch341-spi library requires libusb for USB-based CH341 access.
// On the HiBy R1 (Ingenic X1600), CH341 is accessed via the spidev kernel driver.
// This stub lets the source compile; the USB code path is never executed on device.

#pragma once

#include <stdint.h>
#include <stddef.h>
#include <sys/time.h>   // struct timeval (used in libusb_handle_events_timeout)

#ifdef __cplusplus
extern "C" {
#endif

// ── Calling convention (empty on Linux MIPS) ─────────────────────────────────
#define LIBUSB_CALL

// ── Forward/opaque types ──────────────────────────────────────────────────────
typedef struct libusb_context      libusb_context;
typedef struct libusb_device       libusb_device;
typedef struct libusb_device_handle libusb_device_handle;
typedef struct libusb_transfer     libusb_transfer;

// ── Error codes ───────────────────────────────────────────────────────────────
enum libusb_error {
    LIBUSB_SUCCESS             =  0,
    LIBUSB_ERROR_IO            = -1,
    LIBUSB_ERROR_INVALID_PARAM = -2,
    LIBUSB_ERROR_ACCESS        = -3,
    LIBUSB_ERROR_NO_DEVICE     = -4,
    LIBUSB_ERROR_NOT_FOUND     = -5,
    LIBUSB_ERROR_BUSY          = -6,
    LIBUSB_ERROR_TIMEOUT       = -7,
    LIBUSB_ERROR_OVERFLOW      = -8,
    LIBUSB_ERROR_PIPE          = -9,
    LIBUSB_ERROR_INTERRUPTED   = -10,
    LIBUSB_ERROR_NO_MEM        = -11,
    LIBUSB_ERROR_NOT_SUPPORTED = -12,
    LIBUSB_ERROR_OTHER         = -99,
};

// ── Transfer status ───────────────────────────────────────────────────────────
enum libusb_transfer_status {
    LIBUSB_TRANSFER_COMPLETED = 0,
    LIBUSB_TRANSFER_ERROR,
    LIBUSB_TRANSFER_TIMED_OUT,
    LIBUSB_TRANSFER_CANCELLED,
    LIBUSB_TRANSFER_STALL,
    LIBUSB_TRANSFER_NO_DEVICE,
    LIBUSB_TRANSFER_OVERFLOW,
};

enum libusb_transfer_flags {
    LIBUSB_TRANSFER_SHORT_NOT_OK    = 1 << 0,
    LIBUSB_TRANSFER_FREE_BUFFER     = 1 << 1,
    LIBUSB_TRANSFER_FREE_TRANSFER   = 1 << 2,
    LIBUSB_TRANSFER_ADD_ZERO_PACKET = 1 << 3,
};

// ── Log level / option enums ──────────────────────────────────────────────────
enum libusb_log_level {
    LIBUSB_LOG_LEVEL_NONE    = 0,
    LIBUSB_LOG_LEVEL_ERROR   = 1,
    LIBUSB_LOG_LEVEL_WARNING = 2,
    LIBUSB_LOG_LEVEL_INFO    = 3,
    LIBUSB_LOG_LEVEL_DEBUG   = 4,
};

enum libusb_option {
    LIBUSB_OPTION_LOG_LEVEL   = 0,
    LIBUSB_OPTION_USE_USBDK   = 1,
    LIBUSB_OPTION_NO_DEVICE_DISCOVERY = 2,
};

// ── Transfer callback type ────────────────────────────────────────────────────
typedef void (LIBUSB_CALL *libusb_transfer_cb_fn)(struct libusb_transfer *transfer);

// ── Transfer structure ────────────────────────────────────────────────────────
struct libusb_transfer {
    libusb_device_handle        *dev_handle;
    uint8_t                      flags;
    unsigned char                endpoint;
    unsigned char                type;
    unsigned int                 timeout;
    enum libusb_transfer_status  status;
    int                          length;
    int                          actual_length;
    libusb_transfer_cb_fn        callback;
    void                        *user_data;
    unsigned char               *buffer;
    int                          num_iso_packets;
};

// ── Device descriptor ─────────────────────────────────────────────────────────
struct libusb_device_descriptor {
    uint8_t  bLength;
    uint8_t  bDescriptorType;
    uint16_t bcdUSB;
    uint8_t  bDeviceClass;
    uint8_t  bDeviceSubClass;
    uint8_t  bDeviceProtocol;
    uint8_t  bMaxPacketSize0;
    uint16_t idVendor;
    uint16_t idProduct;
    uint16_t bcdDevice;
    uint8_t  iManufacturer;
    uint8_t  iProduct;
    uint8_t  iSerialNumber;
    uint8_t  bNumConfigurations;
};
typedef struct libusb_device_descriptor libusb_device_descriptor;

// ── Constants ─────────────────────────────────────────────────────────────────
#define LIBUSB_REQUEST_TYPE_VENDOR   (0x02 << 5)
#define LIBUSB_RECIPIENT_DEVICE      0x00
#define LIBUSB_ENDPOINT_OUT          0x00
#define LIBUSB_ENDPOINT_IN           0x80
#define LIBUSB_TRANSFER_TYPE_BULK    2
#define LIBUSB_TRANSFER_TYPE_CONTROL 0

// ── API stubs ─────────────────────────────────────────────────────────────────
static inline int libusb_init(libusb_context **ctx) { (void)ctx; return LIBUSB_ERROR_NOT_SUPPORTED; }
static inline void libusb_exit(libusb_context *ctx) { (void)ctx; }
static inline int libusb_set_option(libusb_context *ctx, enum libusb_option opt, ...) { (void)ctx;(void)opt; return LIBUSB_ERROR_NOT_SUPPORTED; }
static inline libusb_device_handle *libusb_open_device_with_vid_pid(libusb_context *ctx, uint16_t vid, uint16_t pid) { (void)ctx;(void)vid;(void)pid; return (libusb_device_handle*)0; }
static inline int libusb_open(libusb_device *dev, libusb_device_handle **h) { (void)dev;(void)h; return LIBUSB_ERROR_NOT_SUPPORTED; }
static inline void libusb_close(libusb_device_handle *h) { (void)h; }
static inline int libusb_claim_interface(libusb_device_handle *h, int i) { (void)h;(void)i; return LIBUSB_ERROR_NOT_SUPPORTED; }
static inline int libusb_release_interface(libusb_device_handle *h, int i) { (void)h;(void)i; return LIBUSB_ERROR_NOT_SUPPORTED; }
static inline int libusb_set_configuration(libusb_device_handle *h, int config) { (void)h;(void)config; return LIBUSB_ERROR_NOT_SUPPORTED; }
static inline int libusb_detach_kernel_driver(libusb_device_handle *h, int iface) { (void)h;(void)iface; return LIBUSB_ERROR_NOT_SUPPORTED; }
static inline int libusb_attach_kernel_driver(libusb_device_handle *h, int iface) { (void)h;(void)iface; return LIBUSB_ERROR_NOT_SUPPORTED; }
static inline int libusb_kernel_driver_active(libusb_device_handle *h, int iface) { (void)h;(void)iface; return LIBUSB_ERROR_NOT_SUPPORTED; }
static inline int libusb_control_transfer(libusb_device_handle *h, uint8_t rt, uint8_t req, uint16_t val, uint16_t idx, unsigned char *data, uint16_t len, unsigned int timeout) { (void)h;(void)rt;(void)req;(void)val;(void)idx;(void)data;(void)len;(void)timeout; return LIBUSB_ERROR_NOT_SUPPORTED; }
static inline int libusb_bulk_transfer(libusb_device_handle *h, unsigned char ep, unsigned char *data, int len, int *actual, unsigned int timeout) { (void)h;(void)ep;(void)data;(void)len;(void)actual;(void)timeout; return LIBUSB_ERROR_NOT_SUPPORTED; }
static inline int libusb_get_device_descriptor(libusb_device *dev, libusb_device_descriptor *desc) { (void)dev;(void)desc; return LIBUSB_ERROR_NOT_SUPPORTED; }
static inline int libusb_get_string_descriptor_ascii(libusb_device_handle *h, uint8_t idx, unsigned char *data, int len) { (void)h;(void)idx;(void)data;(void)len; return LIBUSB_ERROR_NOT_SUPPORTED; }
static inline int libusb_get_string_descriptor(libusb_device_handle *h, uint8_t idx, uint16_t lang, unsigned char *data, int len) { (void)h;(void)idx;(void)lang;(void)data;(void)len; return LIBUSB_ERROR_NOT_SUPPORTED; }
static inline const char *libusb_error_name(int code) { (void)code; return "LIBUSB_STUB"; }
static inline libusb_transfer *libusb_alloc_transfer(int iso_packets) { (void)iso_packets; return (libusb_transfer*)0; }
static inline void libusb_free_transfer(libusb_transfer *t) { (void)t; }
static inline int libusb_submit_transfer(libusb_transfer *t) { (void)t; return LIBUSB_ERROR_NOT_SUPPORTED; }
static inline int libusb_cancel_transfer(libusb_transfer *t) { (void)t; return LIBUSB_ERROR_NOT_SUPPORTED; }
static inline int libusb_handle_events(libusb_context *ctx) { (void)ctx; return LIBUSB_ERROR_NOT_SUPPORTED; }
static inline int libusb_handle_events_completed(libusb_context *ctx, int *completed) { (void)ctx;(void)completed; return LIBUSB_ERROR_NOT_SUPPORTED; }
static inline int libusb_handle_events_timeout(libusb_context *ctx, struct timeval *tv) { (void)ctx;(void)tv; return LIBUSB_ERROR_NOT_SUPPORTED; }
static inline int libusb_handle_events_timeout_completed(libusb_context *ctx, struct timeval *tv, int *completed) { (void)ctx;(void)tv;(void)completed; return LIBUSB_ERROR_NOT_SUPPORTED; }
static inline void libusb_fill_bulk_transfer(libusb_transfer *t, libusb_device_handle *h, unsigned char ep, unsigned char *buf, int len, libusb_transfer_cb_fn cb, void *udata, unsigned int timeout) { (void)t;(void)h;(void)ep;(void)buf;(void)len;(void)cb;(void)udata;(void)timeout; }
static inline ssize_t libusb_get_device_list(libusb_context *ctx, libusb_device ***list) { (void)ctx;(void)list; return 0; }
static inline void libusb_free_device_list(libusb_device **list, int unref) { (void)list;(void)unref; }
static inline libusb_device *libusb_ref_device(libusb_device *dev) { return dev; }
static inline void libusb_unref_device(libusb_device *dev) { (void)dev; }

#ifdef __cplusplus
}
#endif
