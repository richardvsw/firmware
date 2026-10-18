#include <Arduino.h>
#include <SPI.h>
#include <SD.h>
#include <FS.h>
#include <lvgl.h>
#include <LovyanGFX.hpp>
#include "esp_ota_ops.h"
#include "esp_partition.h"
#include <RadioLib.h>
#include <WiFi.h>

// ==============================================================================
// 📌 PIN MAPPING (XIAO ESP32-S3 + WIO SX1262)
// ==============================================================================
#define PIN_SCK 7
#define PIN_MISO 8
#define PIN_MOSI 9
#define TFT_CS 1
#define TFT_DC 2
#define TFT_BL 4
#define TFT_RST -1 // LCD reset is on the EN pad
#define TOUCH_CS 5
#define LORA_CS 41
#define LORA_RST 42
#define LORA_DIO1 39
#define LORA_BUSY 40
#define LORA_RXEN 38
#define SD_CS 44     // XIAO D7
#define GPS_RX_PIN 3 // XIAO D2, receive only
#define GPS_TX_PIN -1

// The panel is 480x320 here, the UI is 320x240 and is scaled by 4/3 to 426x320, centred
#define PF_ROTATION 1
#define PF_OFFX 27
#define PF_OFFY 0

// ==============================================================================
// 🔧 SPI BUS SHARED MANAGEMENT
// ==============================================================================
SPIClass &sharedSPI = SPI;
static SemaphoreHandle_t spi_mutex = NULL;

// Macro untuk mengunci SPI bus
#define SPI_LOCK() \
    if (spi_mutex) \
    xSemaphoreTake(spi_mutex, portMAX_DELAY)
#define SPI_UNLOCK() \
    if (spi_mutex)   \
    xSemaphoreGive(spi_mutex)

// Fungsi memastikan semua CS deselect sebelum operasi
static inline void deselect_all_cs()
{
    digitalWrite(TFT_CS, HIGH);
    digitalWrite(TOUCH_CS, HIGH);
    digitalWrite(LORA_CS, HIGH);
    digitalWrite(SD_CS, HIGH);
}

// ==============================================================================
// 🔧 HARDWARE OBJECTS
// ==============================================================================
class LGFX : public lgfx::LGFX_Device
{
    lgfx::Panel_ILI9488 _panel;
    lgfx::Bus_SPI _bus;
    lgfx::Light_PWM _light;
    lgfx::Touch_XPT2046 _touch;

  public:
    LGFX()
    {
        {
            auto cfg = _bus.config();
            cfg.spi_host = SPI2_HOST;
            cfg.spi_mode = 0;
            cfg.freq_write = 40000000;
            cfg.freq_read = 16000000;
            cfg.pin_sclk = PIN_SCK;
            cfg.pin_mosi = PIN_MOSI;
            cfg.pin_miso = -1; // the LCD's SDO is not wired
            cfg.pin_dc = TFT_DC;
            _bus.config(cfg);
            _panel.setBus(&_bus);
        }
        {
            auto cfg = _panel.config();
            cfg.pin_cs = TFT_CS;
            cfg.pin_rst = -1;
            cfg.pin_busy = -1;
            cfg.memory_width = 320;
            cfg.memory_height = 480;
            cfg.panel_width = 320;
            cfg.panel_height = 480;
            cfg.offset_rotation = 0;
            cfg.readable = false;
            cfg.invert = false;
            cfg.rgb_order = false;
            cfg.dlen_16bit = false;
            cfg.bus_shared = true;
            _panel.config(cfg);
        }
        {
            auto cfg = _light.config();
            cfg.pin_bl = TFT_BL;
            cfg.invert = false;
            cfg.freq = 44000;
            cfg.pwm_channel = 7;
            _light.config(cfg);
            _panel.setLight(&_light);
        }
        {
            auto cfg = _touch.config();
            cfg.x_min = 410;
            cfg.x_max = 4010;
            cfg.y_min = 0;
            cfg.y_max = 3600;
            cfg.pin_int = -1;
            cfg.bus_shared = true;
            cfg.offset_rotation = 5; // portrait mapping (offset 7 at rotation 0) turned into rotation 1
            cfg.spi_host = SPI2_HOST;
            cfg.freq = 2500000;
            cfg.pin_sclk = PIN_SCK;
            cfg.pin_mosi = PIN_MOSI;
            cfg.pin_miso = PIN_MISO;
            cfg.pin_cs = TOUCH_CS;
            _touch.config(cfg);
            _panel.setTouch(&_touch);
        }
        setPanel(&_panel);
    }
};
LGFX tft;

// touch in UI coordinates (0..319, 0..239), false when not touched
static bool read_touch(int &x, int &y)
{
    uint16_t tx, ty;
    if (!tft.getTouch(&tx, &ty))
        return false;
    int ux = ((int)tx - PF_OFFX) * 3 / 4;
    int uy = ((int)ty - PF_OFFY) * 3 / 4;
    x = constrain(ux, 0, 319);
    y = constrain(uy, 0, 239);
    return true;
}
SX1262 radio = new Module(LORA_CS, LORA_DIO1, LORA_RST, LORA_BUSY, sharedSPI);
HardwareSerial SerialGPS(1);

static lv_disp_draw_buf_t draw_buf;
static lv_color_t buf1[320 * 20];

// ==============================================================================
// 🔧 GLOBAL STATE
// ==============================================================================
static bool radio_ready = false;
static bool sd_ready = false;
static float target_frequency = 922.875;
static bool spectrum_scanning = true;
static bool sniffer_active = false;

static int applied_preset = -1;
static float applied_freq = 0;
static int applied_mode = -1;

enum MeshPreset
{
    PRESET_SHORT_TURBO = 0,
    PRESET_SHORT_FAST,
    PRESET_SHORT_SLOW,
    PRESET_MEDIUM_FAST,
    PRESET_MEDIUM_SLOW,
    PRESET_LONG_FAST,
    PRESET_LONG_MODERATE,
    PRESET_LONG_SLOW,
    PRESET_VERY_LONG_SLOW,
    PRESET_COUNT
};

struct PresetConfig
{
    const char *name;
    float bw;
    uint8_t sf;
    uint8_t cr;
};

static const PresetConfig MESH_PRESETS[PRESET_COUNT] = {
    {"ShortTurbo", 500.0, 7, 5}, {"ShortFast", 250.0, 7, 5}, {"ShortSlow", 250.0, 8, 5}, {"MediumFast", 250.0, 9, 5}, {"MediumSlow", 250.0, 10, 5}, {"LongFast", 250.0, 11, 5}, {"LongModerate", 125.0, 11, 8}, {"LongSlow", 125.0, 12, 8}, {"VeryLongSlow", 62.5, 12, 8}};

static int current_preset = PRESET_LONG_FAST;
static int current_sniff_preset = PRESET_LONG_FAST;

// ==============================================================================
// 📊 SNIFFER STATE
// ==============================================================================
static int packet_count = 0;
static int16_t last_packet_rssi = -120;
static float last_packet_snr = 0;
static int last_packet_size = 0;
static unsigned long last_packet_time = 0;
static uint8_t sniff_packet_buf[256];

static int pkt_rate_counter = 0;
static float pkt_rate_per_sec = 0.0;
static unsigned long pkt_rate_last_calc = 0;

#define RSSI_HISTORY_LEN 60
static int16_t rssi_history[RSSI_HISTORY_LEN];
static int rssi_history_idx = 0;
static bool rssi_history_full = false;

#define MULTI_FREQ_COUNT 5
static float multi_freq_list[MULTI_FREQ_COUNT] = {921.875, 922.125, 922.375, 922.625, 922.875};
static int multi_freq_pkt_count[MULTI_FREQ_COUNT] = {0};
static int16_t multi_freq_rssi[MULTI_FREQ_COUNT] = {-130, -130, -130, -130, -130};
static bool multi_freq_mode = false;
static int multi_freq_current_idx = 0;
static unsigned long multi_freq_dwell_time = 0;
static char hex_payload[80];

// ==============================================================================
// 🧭 GPS STATE
// ==============================================================================
static double gps_lat = 0.0, gps_lon = 0.0;
static float gps_speed_kmh = 0.0, gps_course = 0.0, gps_altitude = 0.0;
static float gps_hdop = 99.9;
static float gps_course_smooth = 0.0;
static int gps_satellites = 0;
static bool gps_fixed = false;
static unsigned long gps_start_time = 0;
static char gps_line_buf[128];
static int gps_line_idx = 0;

static int current_map_zoom = 14;
static int last_tile_x = -1, last_tile_y = -1;
static bool target_active = false;
static double target_lat = 0.0, target_lon = 0.0;

// ==============================================================================
// 📊 SPECTRUM & NOISE STATE
// ==============================================================================
enum ScanRange
{
    RANGE_ID = 0,
    RANGE_US,
    RANGE_WIDE
};
static int current_scan_range = RANGE_ID;
static int spec_scan_ch = 0;
static int spec_num_channels = 48;
static float spec_freq_start = 920.0;
static float spec_freq_step = 0.0625;
static int16_t spec_peak_rssi = -135;
static float spec_peak_freq = 0;
static int32_t spec_total_rssi = 0;

static int current_noise_range = RANGE_ID;
static int noise_scan_ch = 0;
static int noise_num_channels = 48;
static float noise_freq_start = 920.0;
static float noise_freq_step = 0.0625;
static int16_t noise_peak = -140;
static int32_t noise_total = 0;

// ==============================================================================
// 🖥️ LVGL CALLBACKS (dengan SPI MUTEX)
// ==============================================================================
void my_flush(lv_disp_drv_t *d, const lv_area_t *a, lv_color_t *c)
{
    SPI_LOCK();
    static uint16_t scaled[440 * 32];
    int32_t sw = a->x2 - a->x1 + 1;
    int32_t dx0 = (a->x1 * 4) / 3, dx1 = ((a->x2 + 1) * 4) / 3 - 1;
    int32_t dy0 = (a->y1 * 4) / 3, dy1 = ((a->y2 + 1) * 4) / 3 - 1;
    int32_t dw = dx1 - dx0 + 1, dh = dy1 - dy0 + 1;
    if (dw > 0 && dh > 0 && dw * dh <= (int32_t)(sizeof(scaled) / 2))
    {
        for (int32_t y = 0; y < dh; y++)
        {
            int32_t sy = ((dy0 + y) * 3) / 4 - a->y1;
            if (sy < 0)
                sy = 0;
            if (sy > a->y2 - a->y1)
                sy = a->y2 - a->y1;
            const lv_color_t *row = c + sy * sw;
            for (int32_t x = 0; x < dw; x++)
            {
                int32_t sx = ((dx0 + x) * 3) / 4 - a->x1;
                if (sx < 0)
                    sx = 0;
                if (sx > sw - 1)
                    sx = sw - 1;
                scaled[y * dw + x] = row[sx].full;
            }
        }
        tft.startWrite();
        tft.pushImage(PF_OFFX + dx0, PF_OFFY + dy0, dw, dh, (lgfx::rgb565_t *)scaled);
        tft.endWrite();
    }
    SPI_UNLOCK();
    lv_disp_flush_ready(d);
}

void my_touch(lv_indev_drv_t *d, lv_indev_data_t *data)
{
    SPI_LOCK();
    int tx = 0, ty = 0;
    bool touched = read_touch(tx, ty);
    SPI_UNLOCK();

    if (touched)
    {
        data->state = LV_INDEV_STATE_PRESSED;
        data->point.x = tx;
        data->point.y = ty;
    }
    else
    {
        data->state = LV_INDEV_STATE_RELEASED;
    }
}

// ==============================================================================
// 📡 RADIO CONFIG (dengan SPI MUTEX)
// ==============================================================================
void configure_radio_preset(int preset, float freq, uint8_t sync, int mode_id)
{
    if (preset == applied_preset && freq == applied_freq && mode_id == applied_mode)
        return;
    const PresetConfig *p = &MESH_PRESETS[preset];
    SPI_LOCK();
    radio.standby();
    radio.setFrequency(freq);
    radio.setBandwidth(p->bw);
    radio.setSpreadingFactor(p->sf);
    radio.setCodingRate(p->cr);
    radio.setSyncWord(sync);
    radio.setPreambleLength(16);
    SPI_UNLOCK();
    applied_preset = preset;
    applied_freq = freq;
    applied_mode = mode_id;
}

void configure_radio_spectrum()
{
    if (applied_mode == 0)
        return;
    SPI_LOCK();
    radio.standby();
    radio.setBandwidth(500.0);
    radio.setSpreadingFactor(7);
    radio.setCodingRate(5);
    radio.setSyncWord(0x12);
    SPI_UNLOCK();
    applied_mode = 0;
    applied_preset = -1;
}

void invalidate_radio_config()
{
    applied_preset = -1;
    applied_freq = 0;
    applied_mode = -1;
}

// Helper wrapper SPI untuk Radio
int16_t radio_set_freq_locked(float f)
{
    SPI_LOCK();
    int16_t s = radio.setFrequency(f);
    SPI_UNLOCK();
    return s;
}
int16_t radio_start_rx_locked()
{
    SPI_LOCK();
    int16_t s = radio.startReceive();
    SPI_UNLOCK();
    return s;
}
int16_t radio_standby_locked()
{
    SPI_LOCK();
    int16_t s = radio.standby();
    SPI_UNLOCK();
    return s;
}
float radio_get_rssi_locked()
{
    SPI_LOCK();
    float r = radio.getRSSI(false);
    SPI_UNLOCK();
    return r;
}

// ==============================================================================
// 📱 SCREEN OBJECTS
// ==============================================================================
static lv_obj_t *scr_menu, *scr_spectrum, *scr_rssi, *scr_noise;
static lv_obj_t *scr_gps, *scr_map, *scr_wifi, *scr_diag, *scr_about, *scr_sniffer;

static lv_obj_t *chart_spec, *lbl_spec_peak, *lbl_spec_floor, *lbl_spec_status;
static lv_obj_t *lbl_spec_x1, *lbl_spec_x2, *lbl_spec_x3, *lbl_spec_x4;
static lv_obj_t *btn_scan_toggle, *lbl_btn_scan, *dd_scan_range;
static lv_chart_series_t *spec_ser;

static lv_obj_t *arc_rssi, *lbl_rssi_val, *lbl_rssi_quality;
static lv_obj_t *bar_rssi, *lbl_rssi_freq, *lbl_rssi_hint, *dd_preset;

static lv_obj_t *chart_noise, *lbl_noise_avg, *lbl_noise_peak;
static lv_obj_t *dd_noise_range;
static lv_obj_t *lbl_noise_x1, *lbl_noise_x2, *lbl_noise_x3, *lbl_noise_x4;
static lv_chart_series_t *noise_ser;

static lv_obj_t *lbl_gps_lat_lon, *lbl_gps_info, *lbl_gps_status, *lbl_compass_heading;
static lv_obj_t *compass_canvas;
static lv_color_t *compass_cbuf = NULL;
#define COMPASS_SIZE 110
#define COMPASS_CX 55
#define COMPASS_CY 55
#define COMPASS_R 48

static lv_obj_t *map_container, *img_map_tile;
static lv_obj_t *map_marker_user, *map_marker_target;
static lv_obj_t *lbl_map_hud_spd, *lbl_map_hud_pos;
static lv_obj_t *lbl_map_status;

static lv_obj_t *chart_wifi, *lbl_wifi_status, *lbl_wifi_detail;
static lv_chart_series_t *wifi_ser;

static lv_obj_t *lbl_diag_coord, *lbl_diag_zone, *dot;

static lv_obj_t *lbl_sniff_count, *lbl_sniff_rssi, *lbl_sniff_snr;
static lv_obj_t *lbl_sniff_size, *lbl_sniff_time, *lbl_sniff_status;
static lv_obj_t *dd_sniff_preset, *lbl_sniff_preset_name;
static lv_obj_t *lbl_sniff_rate, *lbl_sniff_payload;
static lv_obj_t *chart_sniff_rssi;
static lv_chart_series_t *sniff_rssi_ser;
static lv_obj_t *lbl_sniff_multifreq, *btn_sniff_multifreq, *lbl_btn_multifreq;

// ==============================================================================
// 🔙 NAVIGATION
// ==============================================================================
void go_menu(lv_event_t *e)
{
    spectrum_scanning = false;
    sniffer_active = false;
    multi_freq_mode = false;
    radio_standby_locked();
    invalidate_radio_config();
    lv_scr_load(scr_menu);
}
void go_spectrum(lv_event_t *e)
{
    spectrum_scanning = true;
    spec_scan_ch = 0;
    invalidate_radio_config();
    lv_scr_load(scr_spectrum);
}
void go_rssi(lv_event_t *e)
{
    invalidate_radio_config();
    lv_scr_load(scr_rssi);
}
void go_noise(lv_event_t *e)
{
    invalidate_radio_config();
    lv_scr_load(scr_noise);
}
void go_gps(lv_event_t *e) { lv_scr_load(scr_gps); }
void go_map(lv_event_t *e) { lv_scr_load(scr_map); }
void go_wifi(lv_event_t *e)
{
    WiFi.scanDelete();
    lv_scr_load(scr_wifi);
}
void go_diag(lv_event_t *e) { lv_scr_load(scr_diag); }
void go_about(lv_event_t *e) { lv_scr_load(scr_about); }
void go_sniffer(lv_event_t *e)
{
    packet_count = 0;
    pkt_rate_counter = 0;
    pkt_rate_per_sec = 0;
    pkt_rate_last_calc = millis();
    rssi_history_idx = 0;
    rssi_history_full = false;
    memset(rssi_history, -130, sizeof(rssi_history));
    memset(multi_freq_pkt_count, 0, sizeof(multi_freq_pkt_count));
    for (int i = 0; i < MULTI_FREQ_COUNT; i++)
        multi_freq_rssi[i] = -130;
    multi_freq_current_idx = 0;
    hex_payload[0] = '\0';
    sniffer_active = true;
    invalidate_radio_config();
    lv_scr_load(scr_sniffer);
}

lv_obj_t *make_back_btn(lv_obj_t *parent)
{
    lv_obj_t *btn = lv_btn_create(parent);
    lv_obj_set_size(btn, 55, 26);
    lv_obj_align(btn, LV_ALIGN_TOP_RIGHT, -5, 5);
    lv_obj_set_style_bg_color(btn, lv_color_hex(0xFF3366), 0);
    lv_obj_set_style_radius(btn, 6, 0);
    lv_obj_add_event_cb(btn, go_menu, LV_EVENT_CLICKED, NULL);
    lv_obj_t *l = lv_label_create(btn);
    lv_label_set_text(l, "BACK");
    lv_obj_set_style_text_font(l, &lv_font_montserrat_12, 0);
    lv_obj_center(l);
    return btn;
}

// ==============================================================================
// 🧭 NMEA PARSER (ANTI-CRASH)
// ==============================================================================
static bool get_nmea_field(const char *sentence, int field_idx, char *out_buf, size_t max_len)
{
    int current_field = 0;
    const char *p = sentence;
    while (*p && current_field < field_idx)
    {
        if (*p == ',')
            current_field++;
        p++;
    }
    if (current_field != field_idx || *p == '\0' || *p == ',' || *p == '*')
    {
        out_buf[0] = '\0';
        return false;
    }
    size_t i = 0;
    while (*p && *p != ',' && *p != '*' && *p != '\r' && *p != '\n' && i < max_len - 1)
    {
        out_buf[i++] = *p++;
    }
    out_buf[i] = '\0';
    return (i > 0);
}

void parse_nmea_sentence(const char *sentence)
{
    if (sentence[0] != '$' || strlen(sentence) < 6)
        return;
    const char *type = sentence + 3;
    char field[32];

    if (strncmp(type, "GGA", 3) == 0)
    {
        if (get_nmea_field(sentence, 6, field, sizeof(field)))
        {
            int q = atoi(field);
            gps_fixed = (q > 0);
        }
        else
            gps_fixed = false;

        if (get_nmea_field(sentence, 7, field, sizeof(field)))
            gps_satellites = atoi(field);
        if (get_nmea_field(sentence, 8, field, sizeof(field)))
            gps_hdop = atof(field);
        if (get_nmea_field(sentence, 9, field, sizeof(field)))
            gps_altitude = atof(field);

        if (get_nmea_field(sentence, 2, field, sizeof(field)))
        {
            double raw_lat = atof(field);
            int lat_deg = (int)(raw_lat / 100);
            double lat_min = raw_lat - (lat_deg * 100);
            gps_lat = lat_deg + (lat_min / 60.0);
            char ns[4];
            if (get_nmea_field(sentence, 3, ns, sizeof(ns)) && ns[0] == 'S')
                gps_lat = -gps_lat;
        }
        if (get_nmea_field(sentence, 4, field, sizeof(field)))
        {
            double raw_lon = atof(field);
            int lon_deg = (int)(raw_lon / 100);
            double lon_min = raw_lon - (lon_deg * 100);
            gps_lon = lon_deg + (lon_min / 60.0);
            char ew[4];
            if (get_nmea_field(sentence, 5, ew, sizeof(ew)) && ew[0] == 'W')
                gps_lon = -gps_lon;
        }
    }
    else if (strncmp(type, "RMC", 3) == 0)
    {
        if (get_nmea_field(sentence, 2, field, sizeof(field)))
        {
            if (field[0] == 'A')
                gps_fixed = true;
        }
        if (get_nmea_field(sentence, 7, field, sizeof(field)))
            gps_speed_kmh = atof(field) * 1.852f;
        if (get_nmea_field(sentence, 8, field, sizeof(field)))
            gps_course = atof(field);
    }
}

// ==============================================================================
// 📊 1. MAIN MENU
// ==============================================================================
// Restart: the boot partition already points at the launcher, so this returns to the firmware selection menu
static void restart_cb(lv_event_t *e)
{
    ESP.restart();
}

void build_menu()
{
    scr_menu = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(scr_menu, lv_color_hex(0x0A0A1A), 0);
    lv_obj_clear_flag(scr_menu, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *title = lv_label_create(scr_menu);
    lv_label_set_text(title, "PATHFINDER");
    lv_obj_set_style_text_color(title, lv_color_hex(0x00FFFF), 0);
    lv_obj_set_style_text_font(title, &lv_font_montserrat_18, 0);
    lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 5);

    lv_obj_t *btn_r = lv_btn_create(scr_menu);
    lv_obj_set_size(btn_r, 26, 26);
    lv_obj_align(btn_r, LV_ALIGN_TOP_LEFT, 5, 5);
    lv_obj_set_style_bg_color(btn_r, lv_color_hex(0xB71C1C), 0);
    lv_obj_set_style_radius(btn_r, 13, 0);
    lv_obj_add_event_cb(btn_r, restart_cb, LV_EVENT_CLICKED, NULL);
    lv_obj_t *lr = lv_label_create(btn_r);
    lv_label_set_text(lr, LV_SYMBOL_REFRESH);
    lv_obj_set_style_text_font(lr, &lv_font_montserrat_14, 0);
    lv_obj_center(lr);

    lv_obj_t *btn_i = lv_btn_create(scr_menu);
    lv_obj_set_size(btn_i, 26, 26);
    lv_obj_align(btn_i, LV_ALIGN_TOP_RIGHT, -5, 5);
    lv_obj_set_style_bg_color(btn_i, lv_color_hex(0x795548), 0);
    lv_obj_set_style_radius(btn_i, 13, 0);
    lv_obj_add_event_cb(btn_i, go_about, LV_EVENT_CLICKED, NULL);
    lv_obj_t *li = lv_label_create(btn_i);
    lv_label_set_text(li, "i");
    lv_obj_set_style_text_font(li, &lv_font_montserrat_14, 0);
    lv_obj_center(li);

    const char *labels[] = {"SPECTRUM", "RSSI METER", "NOISE FLOOR", "COMPASS NAV",
                            "WIFI SCAN", "TOUCH DIAG", "PACKET SNIFFER", "OFFLINE MAPS"};
    uint32_t colors[] = {0x00C853, 0x00B0FF, 0xFFAA00, 0xE91E63,
                         0x9C27B0, 0x607D8B, 0x00BCD4, 0x4CAF50};
    lv_event_cb_t cbs[] = {go_spectrum, go_rssi, go_noise, go_gps,
                           go_wifi, go_diag, go_sniffer, go_map};

    for (int i = 0; i < 8; i++)
    {
        lv_obj_t *btn = lv_btn_create(scr_menu);
        lv_obj_set_size(btn, 135, 38);
        lv_obj_align(btn, LV_ALIGN_TOP_MID, (i % 2 == 0) ? -72 : 72, 35 + (i / 2) * 45);
        lv_obj_set_style_bg_color(btn, lv_color_hex(colors[i]), 0);
        lv_obj_set_style_radius(btn, 8, 0);
        lv_obj_add_event_cb(btn, cbs[i], LV_EVENT_CLICKED, NULL);
        lv_obj_t *l = lv_label_create(btn);
        lv_label_set_text(l, labels[i]);
        lv_obj_set_style_text_font(l, &lv_font_montserrat_12, 0);
        lv_obj_center(l);
    }

    lv_obj_t *footer = lv_label_create(scr_menu);
    lv_label_set_text(footer, "XIAO ESP32-S3 \u2022 WIO SX1262 \u2022 v1.0");
    lv_obj_set_style_text_color(footer, lv_color_hex(0x556677), 0);
    lv_obj_set_style_text_font(footer, &lv_font_montserrat_10, 0);
    lv_obj_align(footer, LV_ALIGN_BOTTOM_MID, 0, -5);
}

// ==============================================================================
// 📊 2. SPECTRUM ANALYZER
// ==============================================================================
static void btn_scan_toggle_cb(lv_event_t *e)
{
    spectrum_scanning = !spectrum_scanning;
    lv_label_set_text(lbl_btn_scan, spectrum_scanning ? "STOP" : "START");
    lv_obj_set_style_bg_color(btn_scan_toggle, lv_color_hex(spectrum_scanning ? 0xFF3366 : 0x00C853), 0);
    if (spectrum_scanning)
        spec_scan_ch = 0;
}

static void scan_range_changed_cb(lv_event_t *e)
{
    current_scan_range = lv_dropdown_get_selected(lv_event_get_target(e));
    spec_scan_ch = 0;
    switch (current_scan_range)
    {
    case RANGE_ID:
        spec_freq_start = 920.0;
        spec_freq_step = 0.0625;
        spec_num_channels = 48;
        lv_label_set_text(lbl_spec_x1, "920");
        lv_label_set_text(lbl_spec_x2, "921");
        lv_label_set_text(lbl_spec_x3, "922");
        lv_label_set_text(lbl_spec_x4, "923");
        break;
    case RANGE_US:
        spec_freq_start = 902.0;
        spec_freq_step = 0.5;
        spec_num_channels = 52;
        lv_label_set_text(lbl_spec_x1, "902");
        lv_label_set_text(lbl_spec_x2, "910");
        lv_label_set_text(lbl_spec_x3, "919");
        lv_label_set_text(lbl_spec_x4, "928");
        break;
    case RANGE_WIDE:
        spec_freq_start = 850.0;
        spec_freq_step = 1.5;
        spec_num_channels = 54;
        lv_label_set_text(lbl_spec_x1, "850");
        lv_label_set_text(lbl_spec_x2, "875");
        lv_label_set_text(lbl_spec_x3, "900");
        lv_label_set_text(lbl_spec_x4, "930");
        break;
    }
    lv_chart_set_point_count(chart_spec, spec_num_channels);
}

static void chart_spec_draw_cb(lv_event_t *e)
{
    lv_obj_draw_part_dsc_t *dsc = lv_event_get_draw_part_dsc(e);
    if (!dsc)
        return;
    if (dsc->part == LV_PART_ITEMS)
    {
        int16_t val = dsc->value;
        lv_color_t top_color;
        if (val >= -70)
            top_color = lv_color_hex(0xFF0000);
        else if (val >= -95)
            top_color = lv_color_hex(0xFFFF00);
        else if (val >= -118)
            top_color = lv_color_hex(0x00FF00);
        else
            top_color = lv_color_hex(0x0088FF);
        dsc->rect_dsc->bg_color = top_color;
        dsc->rect_dsc->bg_grad.dir = LV_GRAD_DIR_VER;
        dsc->rect_dsc->bg_grad.stops_count = 2;
        dsc->rect_dsc->bg_grad.stops[0].color = lv_color_hex(0x00C853);
        dsc->rect_dsc->bg_grad.stops[0].frac = 0;
        dsc->rect_dsc->bg_grad.stops[1].color = top_color;
        dsc->rect_dsc->bg_grad.stops[1].frac = 255;
        dsc->rect_dsc->border_width = 0;
    }
    if (dsc->part == LV_PART_MAIN && dsc->line_dsc)
    {
        dsc->line_dsc->color = lv_color_hex(0x223344);
        dsc->line_dsc->width = 1;
        dsc->line_dsc->dash_width = 3;
        dsc->line_dsc->dash_gap = 3;
    }
}

void build_spectrum()
{
    scr_spectrum = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(scr_spectrum, lv_color_hex(0x0A0A1A), 0);
    lv_obj_clear_flag(scr_spectrum, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *t = lv_label_create(scr_spectrum);
    lv_label_set_text(t, "SPECTRUM");
    lv_obj_set_style_text_color(t, lv_color_hex(0x00FF88), 0);
    lv_obj_set_style_text_font(t, &lv_font_montserrat_14, 0);
    lv_obj_align(t, LV_ALIGN_TOP_LEFT, 5, 8);

    dd_scan_range = lv_dropdown_create(scr_spectrum);
    lv_dropdown_set_options(dd_scan_range, "ID Band\nUS Band\nWideband");
    lv_dropdown_set_selected(dd_scan_range, RANGE_ID);
    lv_obj_set_size(dd_scan_range, 85, 26);
    lv_obj_set_style_text_font(dd_scan_range, &lv_font_montserrat_10, 0);
    lv_obj_align(dd_scan_range, LV_ALIGN_TOP_RIGHT, -120, 5);
    lv_obj_add_event_cb(dd_scan_range, scan_range_changed_cb, LV_EVENT_VALUE_CHANGED, NULL);

    btn_scan_toggle = lv_btn_create(scr_spectrum);
    lv_obj_set_size(btn_scan_toggle, 50, 26);
    lv_obj_align(btn_scan_toggle, LV_ALIGN_TOP_RIGHT, -65, 5);
    lv_obj_set_style_bg_color(btn_scan_toggle, lv_color_hex(0xFF3366), 0);
    lv_obj_set_style_radius(btn_scan_toggle, 6, 0);
    lv_obj_add_event_cb(btn_scan_toggle, btn_scan_toggle_cb, LV_EVENT_CLICKED, NULL);
    lbl_btn_scan = lv_label_create(btn_scan_toggle);
    lv_label_set_text(lbl_btn_scan, "STOP");
    lv_obj_set_style_text_font(lbl_btn_scan, &lv_font_montserrat_10, 0);
    lv_obj_center(lbl_btn_scan);

    const char *dbm_labels[] = {"-35", "-60", "-85", "-110", "-135"};
    for (int i = 0; i < 5; i++)
    {
        lv_obj_t *lbl = lv_label_create(scr_spectrum);
        lv_label_set_text(lbl, dbm_labels[i]);
        lv_obj_set_style_text_color(lbl, lv_color_hex(0x666688), 0);
        lv_obj_set_style_text_font(lbl, &lv_font_montserrat_10, 0);
        lv_obj_align(lbl, LV_ALIGN_TOP_LEFT, 2, 43 + (i * 35));
    }

    chart_spec = lv_chart_create(scr_spectrum);
    lv_obj_set_size(chart_spec, 285, 140);
    lv_obj_align(chart_spec, LV_ALIGN_TOP_RIGHT, -5, 45);
    lv_chart_set_type(chart_spec, LV_CHART_TYPE_BAR);
    lv_chart_set_range(chart_spec, LV_CHART_AXIS_PRIMARY_Y, -135, -35);
    lv_chart_set_point_count(chart_spec, 48);
    lv_chart_set_div_line_count(chart_spec, 5, 0);
    lv_obj_set_style_bg_color(chart_spec, lv_color_hex(0x050510), 0);
    lv_obj_set_style_border_color(chart_spec, lv_color_hex(0x334455), 0);
    lv_obj_set_style_border_width(chart_spec, 1, 0);
    lv_obj_set_style_pad_column(chart_spec, 1, LV_PART_MAIN);
    lv_obj_add_event_cb(chart_spec, chart_spec_draw_cb, LV_EVENT_DRAW_PART_BEGIN, NULL);
    lv_obj_clear_flag(chart_spec, LV_OBJ_FLAG_SCROLLABLE);

    spec_ser = lv_chart_add_series(chart_spec, lv_color_hex(0x00FF88), LV_CHART_AXIS_PRIMARY_Y);

    lbl_spec_x1 = lv_label_create(scr_spectrum);
    lbl_spec_x2 = lv_label_create(scr_spectrum);
    lbl_spec_x3 = lv_label_create(scr_spectrum);
    lbl_spec_x4 = lv_label_create(scr_spectrum);
    lv_obj_t *x_labels[] = {lbl_spec_x1, lbl_spec_x2, lbl_spec_x3, lbl_spec_x4};
    int x_pos[] = {35, 110, 185, 260};
    for (int i = 0; i < 4; i++)
    {
        lv_obj_set_style_text_color(x_labels[i], lv_color_hex(0x9999AA), 0);
        lv_obj_set_style_text_font(x_labels[i], &lv_font_montserrat_10, 0);
        lv_obj_align(x_labels[i], LV_ALIGN_TOP_LEFT, x_pos[i], 188);
    }
    lv_label_set_text(lbl_spec_x1, "920");
    lv_label_set_text(lbl_spec_x2, "921");
    lv_label_set_text(lbl_spec_x3, "922");
    lv_label_set_text(lbl_spec_x4, "923");

    lbl_spec_peak = lv_label_create(scr_spectrum);
    lv_label_set_text(lbl_spec_peak, "Peak: --- dBm @ --- MHz");
    lv_obj_set_style_text_color(lbl_spec_peak, lv_color_hex(0xFF3366), 0);
    lv_obj_set_style_text_font(lbl_spec_peak, &lv_font_montserrat_10, 0);
    lv_obj_align(lbl_spec_peak, LV_ALIGN_BOTTOM_LEFT, 5, -18);

    lbl_spec_floor = lv_label_create(scr_spectrum);
    lv_label_set_text(lbl_spec_floor, "Noise: --- dBm");
    lv_obj_set_style_text_color(lbl_spec_floor, lv_color_hex(0xFFAA00), 0);
    lv_obj_set_style_text_font(lbl_spec_floor, &lv_font_montserrat_10, 0);
    lv_obj_align(lbl_spec_floor, LV_ALIGN_BOTTOM_LEFT, 5, -5);

    lbl_spec_status = lv_label_create(scr_spectrum);
    lv_label_set_text(lbl_spec_status, "Ready");
    lv_obj_set_style_text_color(lbl_spec_status, lv_color_hex(0x00FFFF), 0);
    lv_obj_set_style_text_font(lbl_spec_status, &lv_font_montserrat_10, 0);
    lv_obj_align(lbl_spec_status, LV_ALIGN_BOTTOM_RIGHT, -5, -5);

    make_back_btn(scr_spectrum);
}

void update_spectrum()
{
    if (!radio_ready || !spectrum_scanning)
        return;
    configure_radio_spectrum();

    int batch = 6;
    for (int j = 0; j < batch && spec_scan_ch < spec_num_channels; j++, spec_scan_ch++)
    {
        float freq = spec_freq_start + (spec_scan_ch * spec_freq_step);
        radio_set_freq_locked(freq);
        radio_start_rx_locked();
        delay(3);
        int16_t rssi = (int16_t)radio_get_rssi_locked();
        if (rssi > 0)
            rssi = -135;
        if (rssi < -140)
            rssi = -140;
        lv_chart_set_value_by_id(chart_spec, spec_ser, spec_scan_ch, rssi);
        if (rssi > spec_peak_rssi)
        {
            spec_peak_rssi = rssi;
            spec_peak_freq = freq;
        }
        spec_total_rssi += rssi;
    }

    if (spec_scan_ch >= spec_num_channels)
    {
        radio_standby_locked();
        lv_chart_refresh(chart_spec);
        int16_t avg = spec_total_rssi / spec_num_channels;
        char b[64];
        snprintf(b, sizeof(b), "Peak: %d dBm @ %.2f MHz", spec_peak_rssi, spec_peak_freq);
        lv_label_set_text(lbl_spec_peak, b);
        snprintf(b, sizeof(b), "Noise: %d dBm (avg)", avg);
        lv_label_set_text(lbl_spec_floor, b);
        lv_label_set_text(lbl_spec_status, "Scanning...");
        spec_scan_ch = 0;
        spec_peak_rssi = -135;
        spec_total_rssi = 0;
    }
    else
    {
        char b[32];
        snprintf(b, sizeof(b), "Ch %d/%d", spec_scan_ch, spec_num_channels);
        lv_label_set_text(lbl_spec_status, b);
    }
}

// ==============================================================================
// 📊 3. RSSI METER
// ==============================================================================
static void btn_freq_id_cb(lv_event_t *e)
{
    target_frequency = 922.875;
    invalidate_radio_config();
}
static void btn_freq_us_cb(lv_event_t *e)
{
    target_frequency = 915.000;
    invalidate_radio_config();
}
static void btn_freq_up_cb(lv_event_t *e)
{
    target_frequency += 0.125;
    invalidate_radio_config();
}
static void btn_freq_down_cb(lv_event_t *e)
{
    target_frequency -= 0.125;
    invalidate_radio_config();
}

static void preset_changed_cb(lv_event_t *e)
{
    current_preset = lv_dropdown_get_selected(lv_event_get_target(e));
    invalidate_radio_config();
}

static void kb_event_cb(lv_event_t *e)
{
    lv_event_code_t code = lv_event_get_code(e);
    lv_obj_t *kb = lv_event_get_target(e);
    lv_obj_t *ta = (lv_obj_t *)lv_event_get_user_data(e);
    if (code == LV_EVENT_READY)
    {
        float f = atof(lv_textarea_get_text(ta));
        if (f >= 150.0 && f <= 960.0)
        {
            target_frequency = f;
            invalidate_radio_config();
        }
        lv_obj_del(lv_obj_get_parent(kb));
    }
    else if (code == LV_EVENT_CANCEL)
        lv_obj_del(lv_obj_get_parent(kb));
}

static void btn_freq_manual_cb(lv_event_t *e)
{
    lv_obj_t *m = lv_obj_create(scr_rssi);
    lv_obj_set_size(m, 320, 240);
    lv_obj_align(m, LV_ALIGN_CENTER, 0, 0);
    lv_obj_set_style_bg_color(m, lv_color_hex(0x000000), 0);
    lv_obj_set_style_bg_opa(m, LV_OPA_90, 0);
    lv_obj_clear_flag(m, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *ta = lv_textarea_create(m);
    lv_obj_set_size(ta, 180, 36);
    lv_obj_align(ta, LV_ALIGN_TOP_MID, 0, 5);
    lv_textarea_set_one_line(ta, true);
    lv_textarea_set_placeholder_text(ta, "Freq (MHz)");
    char b[16];
    snprintf(b, sizeof(b), "%.3f", target_frequency);
    lv_textarea_set_text(ta, b);
    lv_obj_add_state(ta, LV_STATE_FOCUSED);

    lv_obj_t *kb = lv_keyboard_create(m);
    lv_obj_set_size(kb, 310, 140);
    lv_obj_align(kb, LV_ALIGN_BOTTOM_MID, 0, 0);
    lv_keyboard_set_mode(kb, LV_KEYBOARD_MODE_NUMBER);
    lv_keyboard_set_textarea(kb, ta);
    lv_obj_add_event_cb(kb, kb_event_cb, LV_EVENT_ALL, ta);
}

void build_rssi()
{
    scr_rssi = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(scr_rssi, lv_color_hex(0x0A0A1A), 0);
    lv_obj_clear_flag(scr_rssi, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *t = lv_label_create(scr_rssi);
    lv_label_set_text(t, "RSSI METER");
    lv_obj_set_style_text_color(t, lv_color_hex(0x00B0FF), 0);
    lv_obj_set_style_text_font(t, &lv_font_montserrat_14, 0);
    lv_obj_align(t, LV_ALIGN_TOP_LEFT, 5, 5);

    arc_rssi = lv_arc_create(scr_rssi);
    lv_obj_set_size(arc_rssi, 110, 110);
    lv_obj_align(arc_rssi, LV_ALIGN_TOP_LEFT, 15, 35);
    lv_arc_set_range(arc_rssi, 0, 100);
    lv_arc_set_bg_angles(arc_rssi, 135, 45);
    lv_obj_remove_style(arc_rssi, NULL, LV_PART_KNOB);
    lv_obj_clear_flag(arc_rssi, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_style_arc_color(arc_rssi, lv_color_hex(0x1A1A2E), LV_PART_MAIN);
    lv_obj_set_style_arc_color(arc_rssi, lv_color_hex(0x00FF88), LV_PART_INDICATOR);
    lv_obj_set_style_arc_width(arc_rssi, 10, LV_PART_MAIN);
    lv_obj_set_style_arc_width(arc_rssi, 10, LV_PART_INDICATOR);

    lbl_rssi_val = lv_label_create(scr_rssi);
    lv_label_set_text(lbl_rssi_val, "-- dBm");
    lv_obj_set_style_text_color(lbl_rssi_val, lv_color_hex(0xFFFFFF), 0);
    lv_obj_set_style_text_font(lbl_rssi_val, &lv_font_montserrat_16, 0);
    lv_obj_align(lbl_rssi_val, LV_ALIGN_TOP_LEFT, 40, 70);

    lbl_rssi_quality = lv_label_create(scr_rssi);
    lv_label_set_text(lbl_rssi_quality, "LISTENING...");
    lv_obj_set_style_text_color(lbl_rssi_quality, lv_color_hex(0x778899), 0);
    lv_obj_align(lbl_rssi_quality, LV_ALIGN_TOP_LEFT, 45, 95);

    lv_obj_t *pt = lv_label_create(scr_rssi);
    lv_label_set_text(pt, "Mesh Preset:");
    lv_obj_set_style_text_color(pt, lv_color_hex(0x00FFFF), 0);
    lv_obj_set_style_text_font(pt, &lv_font_montserrat_10, 0);
    lv_obj_align(pt, LV_ALIGN_TOP_RIGHT, -10, 40);

    dd_preset = lv_dropdown_create(scr_rssi);
    lv_dropdown_set_options(dd_preset, "ShortTurbo\nShortFast\nShortSlow\nMediumFast\nMediumSlow\nLongFast\nLongModerate\nLongSlow\nVeryLongSlow");
    lv_dropdown_set_selected(dd_preset, PRESET_LONG_FAST);
    lv_obj_set_size(dd_preset, 110, 26);
    lv_obj_set_style_text_font(dd_preset, &lv_font_montserrat_10, 0);
    lv_obj_align(dd_preset, LV_ALIGN_TOP_RIGHT, -10, 55);
    lv_obj_add_event_cb(dd_preset, preset_changed_cb, LV_EVENT_VALUE_CHANGED, NULL);

    lbl_rssi_hint = lv_label_create(scr_rssi);
    lv_label_set_text(lbl_rssi_hint, "Match target's node preset");
    lv_obj_set_style_text_color(lbl_rssi_hint, lv_color_hex(0x556677), 0);
    lv_obj_set_style_text_font(lbl_rssi_hint, &lv_font_montserrat_10, 0);
    lv_obj_align(lbl_rssi_hint, LV_ALIGN_TOP_RIGHT, -10, 85);

    bar_rssi = lv_bar_create(scr_rssi);
    lv_obj_set_size(bar_rssi, 300, 10);
    lv_obj_align(bar_rssi, LV_ALIGN_TOP_MID, 0, 150);
    lv_bar_set_range(bar_rssi, 0, 100);
    lv_obj_set_style_bg_color(bar_rssi, lv_color_hex(0x1A1A2E), LV_PART_MAIN);
    lv_obj_set_style_bg_color(bar_rssi, lv_color_hex(0x00FF88), LV_PART_INDICATOR);

    struct BtnDef
    {
        int w, x;
        lv_event_cb_t cb;
        uint32_t col;
        const char *txt;
    };
    BtnDef btns[] = {
        {45, -130, btn_freq_down_cb, 0x222233, "-Step"},
        {60, -70, btn_freq_id_cb, 0x00C853, "922.87"},
        {50, 0, btn_freq_manual_cb, 0x9C27B0, "SET"},
        {60, 70, btn_freq_us_cb, 0x00B0FF, "915.0"},
        {45, 130, btn_freq_up_cb, 0x222233, "+Step"}};

    for (int i = 0; i < 5; i++)
    {
        lv_obj_t *b = lv_btn_create(scr_rssi);
        lv_obj_set_size(b, btns[i].w, 26);
        lv_obj_align(b, LV_ALIGN_BOTTOM_MID, btns[i].x, -30);
        lv_obj_set_style_bg_color(b, lv_color_hex(btns[i].col), 0);
        lv_obj_set_style_radius(b, 4, 0);
        lv_obj_add_event_cb(b, btns[i].cb, LV_EVENT_CLICKED, NULL);
        lv_obj_t *l = lv_label_create(b);
        lv_label_set_text(l, btns[i].txt);
        lv_obj_set_style_text_font(l, &lv_font_montserrat_10, 0);
        lv_obj_center(l);
    }

    lbl_rssi_freq = lv_label_create(scr_rssi);
    lv_label_set_text(lbl_rssi_freq, "Freq: --- MHz");
    lv_obj_set_style_text_color(lbl_rssi_freq, lv_color_hex(0x00FFFF), 0);
    lv_obj_set_style_text_font(lbl_rssi_freq, &lv_font_montserrat_10, 0);
    lv_obj_align(lbl_rssi_freq, LV_ALIGN_BOTTOM_MID, 0, -8);

    make_back_btn(scr_rssi);
}

void update_rssi()
{
    if (!radio_ready)
        return;
    configure_radio_preset(current_preset, target_frequency, 0x2B, 1);
    radio_start_rx_locked();
    delay(15);
    int16_t rssi = (int16_t)radio_get_rssi_locked();
    radio_standby_locked();

    if (rssi > 0)
        rssi = -135;
    if (rssi < -140)
        rssi = -140;

    int pct = constrain(map(rssi, -135, -35, 0, 100), 0, 100);
    lv_arc_set_value(arc_rssi, pct);
    lv_bar_set_value(bar_rssi, pct, LV_ANIM_OFF);

    char b[48];
    snprintf(b, sizeof(b), "%d dBm", rssi);
    lv_label_set_text(lbl_rssi_val, b);

    const PresetConfig *p = &MESH_PRESETS[current_preset];
    snprintf(b, sizeof(b), "Freq: %.3f MHz (%s)", target_frequency, p->name);
    lv_label_set_text(lbl_rssi_freq, b);

    const char *q;
    uint32_t c;
    if (rssi >= -75)
    {
        q = "EXCELLENT";
        c = 0x00FF88;
    }
    else if (rssi >= -95)
    {
        q = "GOOD";
        c = 0x88FF00;
    }
    else if (rssi >= -115)
    {
        q = "FAIR (LONG)";
        c = 0xFFAA00;
    }
    else if (rssi >= -128)
    {
        q = "MARGINAL";
        c = 0xFF3366;
    }
    else
    {
        q = "LISTENING...";
        c = 0x556677;
    }

    lv_label_set_text(lbl_rssi_quality, q);
    lv_obj_set_style_text_color(lbl_rssi_quality, lv_color_hex(c), 0);
    lv_obj_set_style_arc_color(arc_rssi, lv_color_hex(c), LV_PART_INDICATOR);
    lv_obj_set_style_bg_color(bar_rssi, lv_color_hex(c), LV_PART_INDICATOR);
}

// ==============================================================================
// 📊 4. NOISE FLOOR
// ==============================================================================
static void noise_range_changed_cb(lv_event_t *e)
{
    current_noise_range = lv_dropdown_get_selected(lv_event_get_target(e));
    noise_scan_ch = 0;
    noise_peak = -140;
    noise_total = 0;
    switch (current_noise_range)
    {
    case RANGE_ID:
        noise_freq_start = 920.0;
        noise_freq_step = 0.0625;
        noise_num_channels = 48;
        lv_label_set_text(lbl_noise_x1, "920");
        lv_label_set_text(lbl_noise_x2, "921");
        lv_label_set_text(lbl_noise_x3, "922");
        lv_label_set_text(lbl_noise_x4, "923");
        break;
    case RANGE_US:
        noise_freq_start = 902.0;
        noise_freq_step = 0.5;
        noise_num_channels = 52;
        lv_label_set_text(lbl_noise_x1, "902");
        lv_label_set_text(lbl_noise_x2, "910");
        lv_label_set_text(lbl_noise_x3, "919");
        lv_label_set_text(lbl_noise_x4, "928");
        break;
    case RANGE_WIDE:
        noise_freq_start = 850.0;
        noise_freq_step = 1.5;
        noise_num_channels = 54;
        lv_label_set_text(lbl_noise_x1, "850");
        lv_label_set_text(lbl_noise_x2, "875");
        lv_label_set_text(lbl_noise_x3, "900");
        lv_label_set_text(lbl_noise_x4, "930");
        break;
    }
    lv_chart_set_point_count(chart_noise, noise_num_channels);
    for (int i = 0; i < noise_num_channels; i++)
        lv_chart_set_value_by_id(chart_noise, noise_ser, i, -135);
    lv_chart_refresh(chart_noise);
}

void build_noise()
{
    scr_noise = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(scr_noise, lv_color_hex(0x0A0A1A), 0);
    lv_obj_clear_flag(scr_noise, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *t = lv_label_create(scr_noise);
    lv_label_set_text(t, "NOISE FLOOR SCAN");
    lv_obj_set_style_text_color(t, lv_color_hex(0xFFAA00), 0);
    lv_obj_set_style_text_font(t, &lv_font_montserrat_14, 0);
    lv_obj_align(t, LV_ALIGN_TOP_LEFT, 5, 8);

    dd_noise_range = lv_dropdown_create(scr_noise);
    lv_dropdown_set_options(dd_noise_range, "ID Band\nUS Band\nWideband");
    lv_dropdown_set_selected(dd_noise_range, RANGE_ID);
    lv_obj_set_size(dd_noise_range, 85, 26);
    lv_obj_set_style_text_font(dd_noise_range, &lv_font_montserrat_10, 0);
    lv_obj_align(dd_noise_range, LV_ALIGN_TOP_RIGHT, -65, 5);
    lv_obj_add_event_cb(dd_noise_range, noise_range_changed_cb, LV_EVENT_VALUE_CHANGED, NULL);

    const char *dbm_labels[] = {"-35", "-60", "-85", "-110", "-135"};
    for (int i = 0; i < 5; i++)
    {
        lv_obj_t *lbl = lv_label_create(scr_noise);
        lv_label_set_text(lbl, dbm_labels[i]);
        lv_obj_set_style_text_color(lbl, lv_color_hex(0x666688), 0);
        lv_obj_set_style_text_font(lbl, &lv_font_montserrat_10, 0);
        lv_obj_align(lbl, LV_ALIGN_TOP_LEFT, 2, 43 + (i * 35));
    }

    chart_noise = lv_chart_create(scr_noise);
    lv_obj_set_size(chart_noise, 285, 140);
    lv_obj_align(chart_noise, LV_ALIGN_TOP_RIGHT, -5, 45);
    lv_chart_set_type(chart_noise, LV_CHART_TYPE_LINE);
    lv_chart_set_range(chart_noise, LV_CHART_AXIS_PRIMARY_Y, -135, -35);
    lv_chart_set_point_count(chart_noise, 48);
    lv_chart_set_div_line_count(chart_noise, 5, 4);
    lv_obj_set_style_bg_color(chart_noise, lv_color_hex(0x111122), 0);
    lv_obj_set_style_border_color(chart_noise, lv_color_hex(0xFFAA00), 0);
    lv_obj_set_style_border_width(chart_noise, 1, 0);
    lv_obj_set_style_line_color(chart_noise, lv_color_hex(0x2A2A44), LV_PART_MAIN);
    lv_obj_set_style_line_width(chart_noise, 1, LV_PART_MAIN);
    lv_obj_set_style_size(chart_noise, 0, LV_PART_INDICATOR);
    lv_obj_set_style_line_width(chart_noise, 2, LV_PART_ITEMS);
    lv_obj_set_style_line_color(chart_noise, lv_color_hex(0xFFAA00), LV_PART_ITEMS);
    lv_obj_clear_flag(chart_noise, LV_OBJ_FLAG_SCROLLABLE);

    noise_ser = lv_chart_add_series(chart_noise, lv_color_hex(0xFFAA00), LV_CHART_AXIS_PRIMARY_Y);

    lbl_noise_x1 = lv_label_create(scr_noise);
    lbl_noise_x2 = lv_label_create(scr_noise);
    lbl_noise_x3 = lv_label_create(scr_noise);
    lbl_noise_x4 = lv_label_create(scr_noise);
    lv_obj_t *nx_labels[] = {lbl_noise_x1, lbl_noise_x2, lbl_noise_x3, lbl_noise_x4};
    int nx_pos[] = {35, 110, 185, 260};
    for (int i = 0; i < 4; i++)
    {
        lv_obj_set_style_text_color(nx_labels[i], lv_color_hex(0x9999AA), 0);
        lv_obj_set_style_text_font(nx_labels[i], &lv_font_montserrat_10, 0);
        lv_obj_align(nx_labels[i], LV_ALIGN_TOP_LEFT, nx_pos[i], 188);
    }
    lv_label_set_text(lbl_noise_x1, "920");
    lv_label_set_text(lbl_noise_x2, "921");
    lv_label_set_text(lbl_noise_x3, "922");
    lv_label_set_text(lbl_noise_x4, "923");

    lbl_noise_avg = lv_label_create(scr_noise);
    lv_label_set_text(lbl_noise_avg, "Avg: --- dBm");
    lv_obj_set_style_text_color(lbl_noise_avg, lv_color_hex(0xFFAA00), 0);
    lv_obj_set_style_text_font(lbl_noise_avg, &lv_font_montserrat_10, 0);
    lv_obj_align(lbl_noise_avg, LV_ALIGN_BOTTOM_LEFT, 5, -18);

    lbl_noise_peak = lv_label_create(scr_noise);
    lv_label_set_text(lbl_noise_peak, "Peak: --- dBm");
    lv_obj_set_style_text_color(lbl_noise_peak, lv_color_hex(0xFF3366), 0);
    lv_obj_set_style_text_font(lbl_noise_peak, &lv_font_montserrat_10, 0);
    lv_obj_align(lbl_noise_peak, LV_ALIGN_BOTTOM_LEFT, 5, -5);

    make_back_btn(scr_noise);
}

void update_noise()
{
    if (!radio_ready)
        return;
    configure_radio_spectrum();
    int batch = 8;
    for (int j = 0; j < batch && noise_scan_ch < noise_num_channels; j++, noise_scan_ch++)
    {
        float freq = noise_freq_start + (noise_scan_ch * noise_freq_step);
        radio_set_freq_locked(freq);
        radio_start_rx_locked();
        delay(3);
        int16_t rssi = (int16_t)radio_get_rssi_locked();
        if (rssi > 0)
            rssi = -135;
        if (rssi < -140)
            rssi = -140;
        lv_chart_set_value_by_id(chart_noise, noise_ser, noise_scan_ch, rssi);
        noise_total += rssi;
        if (rssi > noise_peak)
            noise_peak = rssi;
    }
    if (noise_scan_ch >= noise_num_channels)
    {
        radio_standby_locked();
        lv_chart_refresh(chart_noise);
        char b[64];
        snprintf(b, sizeof(b), "Avg: %d dBm (Low=Clean)", noise_total / noise_num_channels);
        lv_label_set_text(lbl_noise_avg, b);
        snprintf(b, sizeof(b), "Peak: %d dBm (Interf.)", noise_peak);
        lv_label_set_text(lbl_noise_peak, b);
        noise_scan_ch = 0;
        noise_peak = -140;
        noise_total = 0;
    }
}

// ==============================================================================
// 🧭 5. COMPASS NAV
// ==============================================================================
void draw_compass(float heading_deg)
{
    if (!compass_cbuf)
        return;
    lv_canvas_fill_bg(compass_canvas, lv_color_hex(0x050510), LV_OPA_COVER);

    lv_draw_line_dsc_t line_dsc;
    lv_draw_line_dsc_init(&line_dsc);
    lv_draw_label_dsc_t label_dsc;
    lv_draw_label_dsc_init(&label_dsc);
    label_dsc.font = &lv_font_montserrat_10;
    label_dsc.align = LV_TEXT_ALIGN_CENTER;

    line_dsc.color = lv_color_hex(0x223344);
    line_dsc.width = 2;
    for (int i = 0; i < 36; i++)
    {
        float a1 = (i * 10) * DEG_TO_RAD;
        float a2 = ((i + 1) * 10) * DEG_TO_RAD;
        lv_point_t pts[2] = {
            {(lv_coord_t)(COMPASS_CX + cos(a1) * COMPASS_R), (lv_coord_t)(COMPASS_CY + sin(a1) * COMPASS_R)},
            {(lv_coord_t)(COMPASS_CX + cos(a2) * COMPASS_R), (lv_coord_t)(COMPASS_CY + sin(a2) * COMPASS_R)}};
        lv_canvas_draw_line(compass_canvas, pts, 2, &line_dsc);
    }

    for (int i = 0; i < 36; i++)
    {
        float angle_deg = i * 10.0;
        float a = (angle_deg - heading_deg - 90) * DEG_TO_RAD;
        int r1, r2 = COMPASS_R - 2;
        if (i % 9 == 0)
        {
            r1 = COMPASS_R - 12;
            line_dsc.color = lv_color_hex(0x00FFFF);
            line_dsc.width = 2;
        }
        else if (i % 3 == 0)
        {
            r1 = COMPASS_R - 8;
            line_dsc.color = lv_color_hex(0x88AACC);
            line_dsc.width = 2;
        }
        else
        {
            r1 = COMPASS_R - 5;
            line_dsc.color = lv_color_hex(0x445566);
            line_dsc.width = 1;
        }
        lv_point_t pts[2] = {
            {(lv_coord_t)(COMPASS_CX + cos(a) * r1), (lv_coord_t)(COMPASS_CY + sin(a) * r1)},
            {(lv_coord_t)(COMPASS_CX + cos(a) * r2), (lv_coord_t)(COMPASS_CY + sin(a) * r2)}};
        lv_canvas_draw_line(compass_canvas, pts, 2, &line_dsc);

        if (i % 9 == 0)
        {
            const char *dirs[] = {"N", "E", "S", "W"};
            uint32_t colors[] = {0xFF3366, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF};
            int lx = COMPASS_CX + (int)(cos(a) * (COMPASS_R - 20)) - 4;
            int ly = COMPASS_CY + (int)(sin(a) * (COMPASS_R - 20)) - 5;
            label_dsc.color = lv_color_hex(colors[i / 9]);
            lv_canvas_draw_text(compass_canvas, lx, ly, 10, &label_dsc, dirs[i / 9]);
        }
    }

    line_dsc.color = lv_color_hex(0xFFAA00);
    line_dsc.width = 2;
    lv_point_t p_wing[2] = {{(lv_coord_t)(COMPASS_CX - 8), (lv_coord_t)COMPASS_CY}, {(lv_coord_t)(COMPASS_CX + 8), (lv_coord_t)COMPASS_CY}};
    lv_canvas_draw_line(compass_canvas, p_wing, 2, &line_dsc);
    lv_point_t p_body[2] = {{(lv_coord_t)COMPASS_CX, (lv_coord_t)(COMPASS_CY - 10)}, {(lv_coord_t)COMPASS_CX, (lv_coord_t)(COMPASS_CY + 5)}};
    lv_canvas_draw_line(compass_canvas, p_body, 2, &line_dsc);

    line_dsc.color = lv_color_hex(0xFF0000);
    line_dsc.width = 3;
    lv_point_t p_lubber[2] = {{(lv_coord_t)COMPASS_CX, 2}, {(lv_coord_t)COMPASS_CX, 12}};
    lv_canvas_draw_line(compass_canvas, p_lubber, 2, &line_dsc);
}

void build_gps()
{
    scr_gps = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(scr_gps, lv_color_hex(0x050510), 0);
    lv_obj_clear_flag(scr_gps, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *t = lv_label_create(scr_gps);
    lv_label_set_text(t, "TACTICAL COMPASS");
    lv_obj_set_style_text_color(t, lv_color_hex(0xE91E63), 0);
    lv_obj_set_style_text_font(t, &lv_font_montserrat_14, 0);
    lv_obj_align(t, LV_ALIGN_TOP_LEFT, 5, 8);

    lbl_gps_status = lv_label_create(scr_gps);
    lv_label_set_text(lbl_gps_status, "ACQUIRING SATS...");
    lv_obj_set_style_text_color(lbl_gps_status, lv_color_hex(0xFFAA00), 0);
    lv_obj_set_style_text_font(lbl_gps_status, &lv_font_montserrat_10, 0);
    lv_obj_align(lbl_gps_status, LV_ALIGN_TOP_LEFT, 5, 28);

    if (!compass_cbuf)
    {
        compass_cbuf = (lv_color_t *)heap_caps_malloc(COMPASS_SIZE * COMPASS_SIZE * sizeof(lv_color_t), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
        if (!compass_cbuf)
            compass_cbuf = (lv_color_t *)malloc(COMPASS_SIZE * COMPASS_SIZE * sizeof(lv_color_t));
    }
    compass_canvas = lv_canvas_create(scr_gps);
    if (compass_cbuf)
    {
        lv_canvas_set_buffer(compass_canvas, compass_cbuf, COMPASS_SIZE, COMPASS_SIZE, LV_IMG_CF_TRUE_COLOR);
    }
    lv_obj_align(compass_canvas, LV_ALIGN_TOP_LEFT, 20, 48);

    lbl_compass_heading = lv_label_create(scr_gps);
    lv_label_set_text(lbl_compass_heading, "--- N");
    lv_obj_set_style_text_color(lbl_compass_heading, lv_color_hex(0x00FFFF), 0);
    lv_obj_set_style_text_font(lbl_compass_heading, &lv_font_montserrat_14, 0);
    lv_obj_set_style_bg_color(lbl_compass_heading, lv_color_hex(0x1A1A2E), 0);
    lv_obj_set_style_bg_opa(lbl_compass_heading, LV_OPA_COVER, 0);
    lv_obj_set_style_border_color(lbl_compass_heading, lv_color_hex(0x334455), 0);
    lv_obj_set_style_border_width(lbl_compass_heading, 1, 0);
    lv_obj_set_style_pad_all(lbl_compass_heading, 4, 0);
    lv_obj_set_style_radius(lbl_compass_heading, 4, 0);
    lv_obj_align(lbl_compass_heading, LV_ALIGN_TOP_LEFT, 35, 175);

    lv_obj_t *panel_nav = lv_obj_create(scr_gps);
    lv_obj_set_size(panel_nav, 145, 105);
    lv_obj_align(panel_nav, LV_ALIGN_TOP_RIGHT, -5, 45);
    lv_obj_set_style_bg_color(panel_nav, lv_color_hex(0x0A0A1A), 0);
    lv_obj_set_style_border_color(panel_nav, lv_color_hex(0x334455), 0);
    lv_obj_set_style_radius(panel_nav, 6, 0);
    lv_obj_clear_flag(panel_nav, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *lbl_nav_title = lv_label_create(panel_nav);
    lv_label_set_text(lbl_nav_title, "FLIGHT DATA");
    lv_obj_set_style_text_color(lbl_nav_title, lv_color_hex(0x778899), 0);
    lv_obj_set_style_text_font(lbl_nav_title, &lv_font_montserrat_10, 0);
    lv_obj_align(lbl_nav_title, LV_ALIGN_TOP_MID, 0, -10);

    lbl_gps_info = lv_label_create(panel_nav);
    lv_label_set_text(lbl_gps_info, "SPD: -- km/h\nALT: -- m\nSAT: --\nDOP: --");
    lv_obj_set_style_text_color(lbl_gps_info, lv_color_hex(0x00FF88), 0);
    lv_obj_set_style_text_font(lbl_gps_info, &lv_font_montserrat_12, 0);
    lv_obj_align(lbl_gps_info, LV_ALIGN_TOP_LEFT, -10, 10);

    lv_obj_t *panel_pos = lv_obj_create(scr_gps);
    lv_obj_set_size(panel_pos, 145, 65);
    lv_obj_align(panel_pos, LV_ALIGN_BOTTOM_RIGHT, -5, -5);
    lv_obj_set_style_bg_color(panel_pos, lv_color_hex(0x0A0A1A), 0);
    lv_obj_set_style_border_color(panel_pos, lv_color_hex(0x334455), 0);
    lv_obj_set_style_radius(panel_pos, 6, 0);
    lv_obj_clear_flag(panel_pos, LV_OBJ_FLAG_SCROLLABLE);

    lbl_gps_lat_lon = lv_label_create(panel_pos);
    lv_label_set_text(lbl_gps_lat_lon, "LAT: ---\nLON: ---");
    lv_obj_set_style_text_color(lbl_gps_lat_lon, lv_color_hex(0xFFFFFF), 0);
    lv_obj_set_style_text_font(lbl_gps_lat_lon, &lv_font_montserrat_10, 0);
    lv_obj_align(lbl_gps_lat_lon, LV_ALIGN_CENTER, 0, 0);

    if (compass_cbuf)
        draw_compass(0);
    make_back_btn(scr_gps);
}

void update_gps()
{
    if (gps_fixed && gps_speed_kmh >= 2.5f)
    {
        float diff = gps_course - gps_course_smooth;
        while (diff > 180.0f)
            diff -= 360.0f;
        while (diff < -180.0f)
            diff += 360.0f;
        gps_course_smooth += diff * 0.05f;
        if (gps_course_smooth < 0.0f)
            gps_course_smooth += 360.0f;
        if (gps_course_smooth >= 360.0f)
            gps_course_smooth -= 360.0f;
    }

    const char *heading_name;
    float h = gps_course_smooth;
    if (h >= 337.5 || h < 22.5)
        heading_name = "N";
    else if (h < 67.5)
        heading_name = "NE";
    else if (h < 112.5)
        heading_name = "E";
    else if (h < 157.5)
        heading_name = "SE";
    else if (h < 202.5)
        heading_name = "S";
    else if (h < 247.5)
        heading_name = "SW";
    else if (h < 292.5)
        heading_name = "W";
    else
        heading_name = "NW";

    if (compass_cbuf)
        draw_compass(gps_course_smooth);

    char hb[32];
    if (gps_fixed && gps_speed_kmh < 2.5f)
    {
        snprintf(hb, sizeof(hb), "STATIONARY");
        lv_obj_set_style_text_color(lbl_compass_heading, lv_color_hex(0xFFAA00), 0);
    }
    else
    {
        snprintf(hb, sizeof(hb), "%.0f\u00B0 %s", gps_course_smooth, heading_name);
        lv_obj_set_style_text_color(lbl_compass_heading, lv_color_hex(0x00FFFF), 0);
    }
    lv_label_set_text(lbl_compass_heading, hb);

    char sb[64];
    unsigned long el = (millis() - gps_start_time) / 1000;
    if (gps_fixed)
    {
        snprintf(sb, sizeof(sb), "FIX: 3D | HDOP: %.1f", gps_hdop);
        lv_obj_set_style_text_color(lbl_gps_status, lv_color_hex(0x00FF88), 0);
    }
    else if (gps_satellites > 0)
    {
        snprintf(sb, sizeof(sb), "AQUIRING: %d SATS (%lus)", gps_satellites, el);
        lv_obj_set_style_text_color(lbl_gps_status, lv_color_hex(0xFFAA00), 0);
    }
    else
    {
        snprintf(sb, sizeof(sb), "NO FIX (COLD START %lus)", el);
        lv_obj_set_style_text_color(lbl_gps_status, lv_color_hex(0xFF3366), 0);
    }
    lv_label_set_text(lbl_gps_status, sb);

    char b[80];
    snprintf(b, sizeof(b), "SPD: %.1f km/h\nALT: %.0f m\nSAT: %d\nDOP: %.1f",
             gps_speed_kmh, gps_altitude, gps_satellites, gps_hdop);
    lv_label_set_text(lbl_gps_info, b);

    if (gps_fixed && gps_lat != 0.0)
        snprintf(b, sizeof(b), "LAT: %.6f\nLON: %.6f", gps_lat, gps_lon);
    else
        snprintf(b, sizeof(b), "LAT: SEARCHING\nLON: SEARCHING");
    lv_label_set_text(lbl_gps_lat_lon, b);
}

// ==============================================================================
// 🗺️ 5B. OFFLINE MAPS
// ==============================================================================
void get_tile_coord(double lat, double lon, int zoom, int &tx, int &ty, int &px, int &py)
{
    double lat_rad = lat * DEG_TO_RAD;
    double n = pow(2.0, zoom);
    double exact_x = (lon + 180.0) / 360.0 * n;
    double exact_y = (1.0 - log(tan(lat_rad) + (1.0 / cos(lat_rad))) / PI) / 2.0 * n;
    tx = (int)floor(exact_x);
    ty = (int)floor(exact_y);
    px = (int)floor((exact_x - tx) * 256.0);
    py = (int)floor((exact_y - ty) * 256.0);
}

void build_map()
{
    scr_map = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(scr_map, lv_color_hex(0x112211), 0);
    lv_obj_clear_flag(scr_map, LV_OBJ_FLAG_SCROLLABLE);

    map_container = lv_obj_create(scr_map);
    lv_obj_set_size(map_container, 320, 240);
    lv_obj_align(map_container, LV_ALIGN_CENTER, 0, 0);
    lv_obj_set_style_bg_opa(map_container, LV_OPA_TRANSP, 0);
    lv_obj_set_style_border_width(map_container, 0, 0);
    lv_obj_set_style_pad_all(map_container, 0, 0);
    lv_obj_clear_flag(map_container, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_style_clip_corner(map_container, true, 0);

    img_map_tile = lv_img_create(map_container);

    map_marker_target = lv_obj_create(map_container);
    lv_obj_set_size(map_marker_target, 14, 14);
    lv_obj_set_style_radius(map_marker_target, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_color(map_marker_target, lv_color_hex(0xFFFF00), 0);
    lv_obj_set_style_border_color(map_marker_target, lv_color_hex(0x000000), 0);
    lv_obj_set_style_border_width(map_marker_target, 2, 0);
    lv_obj_add_flag(map_marker_target, LV_OBJ_FLAG_HIDDEN);

    map_marker_user = lv_obj_create(map_container);
    lv_obj_set_size(map_marker_user, 12, 12);
    lv_obj_set_style_radius(map_marker_user, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_color(map_marker_user, lv_color_hex(0xFF0000), 0);
    lv_obj_set_style_border_color(map_marker_user, lv_color_hex(0xFFFFFF), 0);
    lv_obj_set_style_border_width(map_marker_user, 2, 0);
    lv_obj_align(map_marker_user, LV_ALIGN_CENTER, 0, 0);

    lbl_map_hud_spd = lv_label_create(scr_map);
    lv_label_set_text(lbl_map_hud_spd, "SPD: --\nALT: --");
    lv_obj_set_style_text_color(lbl_map_hud_spd, lv_color_hex(0x00FF88), 0);
    lv_obj_set_style_text_font(lbl_map_hud_spd, &lv_font_montserrat_10, 0);
    lv_obj_set_style_bg_color(lbl_map_hud_spd, lv_color_hex(0x000000), 0);
    lv_obj_set_style_bg_opa(lbl_map_hud_spd, LV_OPA_70, 0);
    lv_obj_set_style_pad_all(lbl_map_hud_spd, 4, 0);
    lv_obj_align(lbl_map_hud_spd, LV_ALIGN_TOP_LEFT, 5, 5);

    lbl_map_hud_pos = lv_label_create(scr_map);
    lv_label_set_text(lbl_map_hud_pos, "WAITING GPS...");
    lv_obj_set_style_text_color(lbl_map_hud_pos, lv_color_hex(0xFFFFFF), 0);
    lv_obj_set_style_text_font(lbl_map_hud_pos, &lv_font_montserrat_10, 0);
    lv_obj_set_style_bg_color(lbl_map_hud_pos, lv_color_hex(0x000000), 0);
    lv_obj_set_style_bg_opa(lbl_map_hud_pos, LV_OPA_70, 0);
    lv_obj_set_style_pad_all(lbl_map_hud_pos, 4, 0);
    lv_obj_align(lbl_map_hud_pos, LV_ALIGN_BOTTOM_LEFT, 5, -5);

    lbl_map_status = lv_label_create(scr_map);
    lv_label_set_text(lbl_map_status, "NO FIX");
    lv_obj_set_style_text_color(lbl_map_status, lv_color_hex(0xFF3366), 0);
    lv_obj_set_style_text_font(lbl_map_status, &lv_font_montserrat_10, 0);
    lv_obj_set_style_bg_color(lbl_map_status, lv_color_hex(0x000000), 0);
    lv_obj_set_style_bg_opa(lbl_map_status, LV_OPA_70, 0);
    lv_obj_set_style_pad_all(lbl_map_status, 4, 0);
    lv_obj_align(lbl_map_status, LV_ALIGN_BOTTOM_RIGHT, -5, -5);

    make_back_btn(scr_map);
}

void update_map()
{
    if (!gps_fixed)
    {
        lv_label_set_text(lbl_map_hud_pos, "WAITING GPS FIX...");
        return;
    }
    int tx, ty, px, py;
    get_tile_coord(gps_lat, gps_lon, current_map_zoom, tx, ty, px, py);
    if (tx != last_tile_x || ty != last_tile_y)
    {
        last_tile_x = tx;
        last_tile_y = ty;
        if (sd_ready)
        {
            char map_path[64];
            snprintf(map_path, sizeof(map_path), "S:/maps/%d/%d/%d.bin", current_map_zoom, tx, ty);
            lv_img_set_src(img_map_tile, map_path);
        }
    }
    int img_x = 160 - px;
    int img_y = 120 - py;
    lv_obj_set_pos(img_map_tile, img_x, img_y);

    if (target_active)
    {
        int ttx, tty, tpx, tpy;
        get_tile_coord(target_lat, target_lon, current_map_zoom, ttx, tty, tpx, tpy);
        int screen_target_x = ((ttx - tx) * 256 + tpx - px) + 160;
        int screen_target_y = ((tty - ty) * 256 + tpy - py) + 120;
        if (screen_target_x > -20 && screen_target_x < 340 && screen_target_y > -20 && screen_target_y < 260)
        {
            lv_obj_clear_flag(map_marker_target, LV_OBJ_FLAG_HIDDEN);
            lv_obj_set_pos(map_marker_target, screen_target_x - 7, screen_target_y - 7);
        }
        else
        {
            lv_obj_add_flag(map_marker_target, LV_OBJ_FLAG_HIDDEN);
        }
    }
    char buf[64];
    snprintf(buf, sizeof(buf), "SPD: %.1f km/h\nALT: %.0f m", gps_speed_kmh, gps_altitude);
    lv_label_set_text(lbl_map_hud_spd, buf);
    snprintf(buf, sizeof(buf), "LAT: %.6f\nLON: %.6f", gps_lat, gps_lon);
    lv_label_set_text(lbl_map_hud_pos, buf);
    snprintf(buf, sizeof(buf), "SATS: %d", gps_satellites);
    lv_label_set_text(lbl_map_status, buf);
    lv_obj_set_style_text_color(lbl_map_status, lv_color_hex(0x00FF88), 0);
}

// ==============================================================================
// 📶 6. WIFI SCANNER
// ==============================================================================
static bool wifi_scan_pending = false;

static void chart_wifi_draw_cb(lv_event_t *e)
{
    lv_obj_draw_part_dsc_t *dsc = lv_event_get_draw_part_dsc(e);
    if (!dsc)
        return;
    if (dsc->part == LV_PART_ITEMS)
    {
        int16_t val = dsc->value;
        lv_color_t top_color;
        if (val >= -55)
            top_color = lv_color_hex(0x00FF88);
        else if (val >= -75)
            top_color = lv_color_hex(0xFFAA00);
        else
            top_color = lv_color_hex(0xFF3366);
        dsc->rect_dsc->bg_color = top_color;
        dsc->rect_dsc->bg_grad.dir = LV_GRAD_DIR_VER;
        dsc->rect_dsc->bg_grad.stops_count = 2;
        dsc->rect_dsc->bg_grad.stops[0].color = lv_color_hex(0x1A1A2E);
        dsc->rect_dsc->bg_grad.stops[0].frac = 0;
        dsc->rect_dsc->bg_grad.stops[1].color = top_color;
        dsc->rect_dsc->bg_grad.stops[1].frac = 255;
        dsc->rect_dsc->radius = 3;
        dsc->rect_dsc->border_width = 0;
    }
    if (dsc->part == LV_PART_MAIN && dsc->line_dsc)
    {
        dsc->line_dsc->color = lv_color_hex(0x223344);
        dsc->line_dsc->width = 1;
        dsc->line_dsc->dash_width = 2;
        dsc->line_dsc->dash_gap = 4;
    }
}

void trigger_wifi_scan_cb(lv_event_t *e)
{
    lv_label_set_text(lbl_wifi_status, "Scanning...");
    lv_label_set_text(lbl_wifi_detail, "");
    WiFi.scanNetworks(true);
    wifi_scan_pending = true;
}

void process_wifi_results()
{
    int16_t n = WiFi.scanComplete();
    if (n == WIFI_SCAN_RUNNING || !wifi_scan_pending)
        return;
    wifi_scan_pending = false;
    if (n <= 0)
    {
        lv_label_set_text(lbl_wifi_status, "No WiFi found.");
        lv_label_set_text(lbl_wifi_detail, "");
        WiFi.scanDelete();
        return;
    }
    int16_t cr[13];
    int cc[13];
    for (int i = 0; i < 13; i++)
    {
        cr[i] = -100;
        cc[i] = 0;
    }
    for (int i = 0; i < n; i++)
    {
        int ch = WiFi.channel(i);
        int32_t r = WiFi.RSSI(i);
        if (ch >= 1 && ch <= 13)
        {
            cc[ch - 1]++;
            if (r > cr[ch - 1])
                cr[ch - 1] = r;
        }
    }
    for (int i = 0; i < 13; i++)
    {
        if (cc[i] == 0)
            cr[i] = -100;
        lv_chart_set_value_by_id(chart_wifi, wifi_ser, i, cr[i]);
    }
    lv_chart_refresh(chart_wifi);
    int bc = 1, mc = 0;
    for (int i = 0; i < 13; i++)
    {
        if (cc[i] > mc)
        {
            mc = cc[i];
            bc = i + 1;
        }
    }
    char b[64];
    snprintf(b, sizeof(b), "Found %d APs | Busy: Ch%d (%d APs)", n, bc, mc);
    lv_label_set_text(lbl_wifi_status, b);
    int clean_ch = 1;
    int16_t clean_rssi = 0;
    for (int i = 0; i < 13; i++)
    {
        if (cc[i] == 0)
        {
            clean_ch = i + 1;
            clean_rssi = -100;
            break;
        }
        if (cr[i] < clean_rssi || i == 0)
        {
            clean_rssi = cr[i];
            clean_ch = i + 1;
        }
    }
    char d[80];
    snprintf(d, sizeof(d), "Cleanest: Ch%d (%d dBm)", clean_ch, clean_rssi);
    lv_label_set_text(lbl_wifi_detail, d);
    WiFi.scanDelete();
}

void build_wifi()
{
    scr_wifi = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(scr_wifi, lv_color_hex(0x0A0A1A), 0);
    lv_obj_clear_flag(scr_wifi, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *t = lv_label_create(scr_wifi);
    lv_label_set_text(t, "WIFI 2.4GHz ANALYZER");
    lv_obj_set_style_text_color(t, lv_color_hex(0x00B0FF), 0);
    lv_obj_set_style_text_font(t, &lv_font_montserrat_14, 0);
    lv_obj_align(t, LV_ALIGN_TOP_LEFT, 5, 8);

    lv_obj_t *bs = lv_btn_create(scr_wifi);
    lv_obj_set_size(bs, 60, 26);
    lv_obj_align(bs, LV_ALIGN_TOP_RIGHT, -65, 5);
    lv_obj_set_style_bg_color(bs, lv_color_hex(0x00B0FF), 0);
    lv_obj_set_style_radius(bs, 6, 0);
    lv_obj_add_event_cb(bs, trigger_wifi_scan_cb, LV_EVENT_CLICKED, NULL);
    lv_obj_t *ls = lv_label_create(bs);
    lv_label_set_text(ls, "SCAN");
    lv_obj_set_style_text_font(ls, &lv_font_montserrat_10, 0);
    lv_obj_center(ls);

    const char *dbm_labels[] = {"-30", "-53", "-76", "-100"};
    for (int i = 0; i < 4; i++)
    {
        lv_obj_t *lbl = lv_label_create(scr_wifi);
        lv_label_set_text(lbl, dbm_labels[i]);
        lv_obj_set_style_text_color(lbl, lv_color_hex(0x666688), 0);
        lv_obj_set_style_text_font(lbl, &lv_font_montserrat_10, 0);
        lv_obj_align(lbl, LV_ALIGN_TOP_LEFT, 2, 45 + (i * 35));
    }

    chart_wifi = lv_chart_create(scr_wifi);
    int chart_w = 285;
    lv_obj_set_size(chart_wifi, chart_w, 140);
    lv_obj_align(chart_wifi, LV_ALIGN_TOP_RIGHT, -5, 45);
    lv_chart_set_type(chart_wifi, LV_CHART_TYPE_BAR);
    lv_chart_set_range(chart_wifi, LV_CHART_AXIS_PRIMARY_Y, -100, -30);
    lv_chart_set_point_count(chart_wifi, 13);
    lv_chart_set_div_line_count(chart_wifi, 4, 0);
    lv_obj_set_style_bg_color(chart_wifi, lv_color_hex(0x050510), 0);
    lv_obj_set_style_border_color(chart_wifi, lv_color_hex(0x334455), 0);
    lv_obj_set_style_border_width(chart_wifi, 1, 0);
    lv_obj_set_style_pad_column(chart_wifi, 2, LV_PART_MAIN);
    lv_obj_add_event_cb(chart_wifi, chart_wifi_draw_cb, LV_EVENT_DRAW_PART_BEGIN, NULL);
    lv_obj_clear_flag(chart_wifi, LV_OBJ_FLAG_SCROLLABLE);

    wifi_ser = lv_chart_add_series(chart_wifi, lv_color_hex(0x9C27B0), LV_CHART_AXIS_PRIMARY_Y);
    for (int i = 0; i < 13; i++)
        lv_chart_set_value_by_id(chart_wifi, wifi_ser, i, -100);

    int start_x = 35;
    float step_x = (float)(chart_w) / 13.0;
    for (int i = 0; i < 13; i++)
    {
        lv_obj_t *lbl_ch = lv_label_create(scr_wifi);
        char buf[4];
        snprintf(buf, sizeof(buf), "%d", i + 1);
        lv_label_set_text(lbl_ch, buf);
        if (i == 0 || i == 5 || i == 10)
            lv_obj_set_style_text_color(lbl_ch, lv_color_hex(0xFFFFFF), 0);
        else
            lv_obj_set_style_text_color(lbl_ch, lv_color_hex(0x778899), 0);
        lv_obj_set_style_text_font(lbl_ch, &lv_font_montserrat_10, 0);
        int pos_x = start_x + (int)(i * step_x) + (int)(step_x / 2.0) - 3;
        if (i > 8)
            pos_x -= 2;
        lv_obj_align(lbl_ch, LV_ALIGN_TOP_LEFT, pos_x, 190);
    }

    lbl_wifi_status = lv_label_create(scr_wifi);
    lv_label_set_text(lbl_wifi_status, "Ready. Tap SCAN to start.");
    lv_obj_set_style_text_color(lbl_wifi_status, lv_color_hex(0x00B0FF), 0);
    lv_obj_set_style_text_font(lbl_wifi_status, &lv_font_montserrat_10, 0);
    lv_obj_align(lbl_wifi_status, LV_ALIGN_BOTTOM_LEFT, 5, -18);

    lbl_wifi_detail = lv_label_create(scr_wifi);
    lv_label_set_text(lbl_wifi_detail, "");
    lv_obj_set_style_text_color(lbl_wifi_detail, lv_color_hex(0x00FF88), 0);
    lv_obj_set_style_text_font(lbl_wifi_detail, &lv_font_montserrat_10, 0);
    lv_obj_align(lbl_wifi_detail, LV_ALIGN_BOTTOM_LEFT, 5, -5);

    make_back_btn(scr_wifi);
}

// ==============================================================================
// 📊 7. TOUCH DIAGNOSTIC
// ==============================================================================
void build_diag()
{
    scr_diag = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(scr_diag, lv_color_hex(0x000000), 0);
    lv_obj_clear_flag(scr_diag, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *t = lv_label_create(scr_diag);
    lv_label_set_text(t, "TOUCH DIAGNOSTIC");
    lv_obj_set_style_text_color(t, lv_color_hex(0x00FFFF), 0);
    lv_obj_align(t, LV_ALIGN_TOP_MID, 0, 8);

    lv_obj_t *lh = lv_line_create(scr_diag);
    static lv_point_t ph[] = {{0, 120}, {320, 120}};
    lv_line_set_points(lh, ph, 2);
    lv_obj_set_style_line_color(lh, lv_color_hex(0x333355), 0);

    lv_obj_t *lv2 = lv_line_create(scr_diag);
    static lv_point_t pv[] = {{160, 30}, {160, 210}};
    lv_line_set_points(lv2, pv, 2);
    lv_obj_set_style_line_color(lv2, lv_color_hex(0x333355), 0);

    lbl_diag_coord = lv_label_create(scr_diag);
    lv_label_set_text(lbl_diag_coord, "X: --- Y: ---");
    lv_obj_set_style_text_color(lbl_diag_coord, lv_color_hex(0x00FF88), 0);
    lv_obj_align(lbl_diag_coord, LV_ALIGN_BOTTOM_LEFT, 5, -5);

    lbl_diag_zone = lv_label_create(scr_diag);
    lv_label_set_text(lbl_diag_zone, "ZONE: ---");
    lv_obj_set_style_text_color(lbl_diag_zone, lv_color_hex(0xFFFF00), 0);
    lv_obj_align(lbl_diag_zone, LV_ALIGN_BOTTOM_RIGHT, -5, -5);

    dot = lv_obj_create(scr_diag);
    lv_obj_set_size(dot, 16, 16);
    lv_obj_set_style_radius(dot, 8, 0);
    lv_obj_set_style_bg_color(dot, lv_color_hex(0xFF0000), 0);
    lv_obj_clear_flag(dot, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(dot, LV_OBJ_FLAG_HIDDEN);

    make_back_btn(scr_diag);
}

void update_diag()
{
    SPI_LOCK();
    int x = 0, y = 0;
    bool touched = read_touch(x, y);
    SPI_UNLOCK();

    if (touched)
    {
        char b[32];
        snprintf(b, sizeof(b), "X: %d  Y: %d", x, y);
        lv_label_set_text(lbl_diag_coord, b);
        const char *z = (x < 160 && y < 120) ? "TOP L" : (x >= 160 && y < 120) ? "TOP R"
                                                     : (x < 160)               ? "BOT L"
                                                                               : "BOT R";
        snprintf(b, sizeof(b), "ZONE: %s", z);
        lv_label_set_text(lbl_diag_zone, b);
        lv_obj_clear_flag(dot, LV_OBJ_FLAG_HIDDEN);
        lv_obj_set_pos(dot, x - 8, y - 8);
    }
}

// ==============================================================================
// 🕵️ 8. PACKET SNIFFER
// ==============================================================================
static void sniff_preset_changed_cb(lv_event_t *e)
{
    current_sniff_preset = lv_dropdown_get_selected(lv_event_get_target(e));
    invalidate_radio_config();
    char b[32];
    snprintf(b, sizeof(b), "Preset: %s", MESH_PRESETS[current_sniff_preset].name);
    lv_label_set_text(lbl_sniff_preset_name, b);
}

static void toggle_multifreq_cb(lv_event_t *e)
{
    multi_freq_mode = !multi_freq_mode;
    lv_label_set_text(lbl_btn_multifreq, multi_freq_mode ? "MULTI:ON" : "MULTI:OFF");
    lv_obj_set_style_bg_color(btn_sniff_multifreq, lv_color_hex(multi_freq_mode ? 0xFF6600 : 0x333344), 0);
    if (multi_freq_mode)
    {
        memset(multi_freq_pkt_count, 0, sizeof(multi_freq_pkt_count));
        for (int i = 0; i < MULTI_FREQ_COUNT; i++)
            multi_freq_rssi[i] = -130;
        multi_freq_current_idx = 0;
    }
    invalidate_radio_config();
}

void build_sniffer()
{
    scr_sniffer = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(scr_sniffer, lv_color_hex(0x0A0A1A), 0);
    lv_obj_clear_flag(scr_sniffer, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *t = lv_label_create(scr_sniffer);
    lv_label_set_text(t, "PACKET SNIFFER");
    lv_obj_set_style_text_color(t, lv_color_hex(0x00BCD4), 0);
    lv_obj_set_style_text_font(t, &lv_font_montserrat_14, 0);
    lv_obj_align(t, LV_ALIGN_TOP_LEFT, 5, 8);

    lbl_sniff_status = lv_label_create(scr_sniffer);
    lv_label_set_text(lbl_sniff_status, "LISTENING...");
    lv_obj_set_style_text_color(lbl_sniff_status, lv_color_hex(0x00FF88), 0);
    lv_obj_set_style_text_font(lbl_sniff_status, &lv_font_montserrat_10, 0);
    lv_obj_align(lbl_sniff_status, LV_ALIGN_TOP_LEFT, 5, 26);

    lbl_sniff_rate = lv_label_create(scr_sniffer);
    lv_label_set_text(lbl_sniff_rate, "Rate: 0.0 pkt/s");
    lv_obj_set_style_text_color(lbl_sniff_rate, lv_color_hex(0xFF6600), 0);
    lv_obj_set_style_text_font(lbl_sniff_rate, &lv_font_montserrat_10, 0);
    lv_obj_align(lbl_sniff_rate, LV_ALIGN_TOP_RIGHT, -145, 26);

    dd_sniff_preset = lv_dropdown_create(scr_sniffer);
    lv_dropdown_set_options(dd_sniff_preset, "ShortTurbo\nShortFast\nShortSlow\nMediumFast\nMediumSlow\nLongFast\nLongModerate\nLongSlow\nVeryLongSlow");
    lv_dropdown_set_selected(dd_sniff_preset, PRESET_LONG_FAST);
    lv_obj_set_size(dd_sniff_preset, 100, 26);
    lv_obj_set_style_text_font(dd_sniff_preset, &lv_font_montserrat_10, 0);
    lv_obj_align(dd_sniff_preset, LV_ALIGN_TOP_LEFT, 5, 42);
    lv_obj_add_event_cb(dd_sniff_preset, sniff_preset_changed_cb, LV_EVENT_VALUE_CHANGED, NULL);

    lbl_sniff_preset_name = lv_label_create(scr_sniffer);
    lv_label_set_text(lbl_sniff_preset_name, "LongFast");
    lv_obj_set_style_text_color(lbl_sniff_preset_name, lv_color_hex(0x9999AA), 0);
    lv_obj_set_style_text_font(lbl_sniff_preset_name, &lv_font_montserrat_10, 0);
    lv_obj_align(lbl_sniff_preset_name, LV_ALIGN_TOP_LEFT, 110, 48);

    btn_sniff_multifreq = lv_btn_create(scr_sniffer);
    lv_obj_set_size(btn_sniff_multifreq, 70, 26);
    lv_obj_align(btn_sniff_multifreq, LV_ALIGN_TOP_RIGHT, -65, 5);
    lv_obj_set_style_bg_color(btn_sniff_multifreq, lv_color_hex(0x333344), 0);
    lv_obj_set_style_radius(btn_sniff_multifreq, 6, 0);
    lv_obj_add_event_cb(btn_sniff_multifreq, toggle_multifreq_cb, LV_EVENT_CLICKED, NULL);
    lbl_btn_multifreq = lv_label_create(btn_sniff_multifreq);
    lv_label_set_text(lbl_btn_multifreq, "MULTI:OFF");
    lv_obj_set_style_text_font(lbl_btn_multifreq, &lv_font_montserrat_10, 0);
    lv_obj_center(lbl_btn_multifreq);

    lbl_sniff_count = lv_label_create(scr_sniffer);
    lv_label_set_text(lbl_sniff_count, "Cnt: 0");
    lv_obj_set_style_text_color(lbl_sniff_count, lv_color_hex(0xFFAA00), 0);
    lv_obj_set_style_text_font(lbl_sniff_count, &lv_font_montserrat_10, 0);
    lv_obj_align(lbl_sniff_count, LV_ALIGN_TOP_LEFT, 5, 75);

    lbl_sniff_rssi = lv_label_create(scr_sniffer);
    lv_label_set_text(lbl_sniff_rssi, "RSSI:---");
    lv_obj_set_style_text_color(lbl_sniff_rssi, lv_color_hex(0x00FF88), 0);
    lv_obj_set_style_text_font(lbl_sniff_rssi, &lv_font_montserrat_10, 0);
    lv_obj_align(lbl_sniff_rssi, LV_ALIGN_TOP_MID, -30, 75);

    lbl_sniff_snr = lv_label_create(scr_sniffer);
    lv_label_set_text(lbl_sniff_snr, "SNR:---");
    lv_obj_set_style_text_color(lbl_sniff_snr, lv_color_hex(0x00B0FF), 0);
    lv_obj_set_style_text_font(lbl_sniff_snr, &lv_font_montserrat_10, 0);
    lv_obj_align(lbl_sniff_snr, LV_ALIGN_TOP_RIGHT, -10, 75);

    chart_sniff_rssi = lv_chart_create(scr_sniffer);
    lv_obj_set_size(chart_sniff_rssi, 310, 60);
    lv_obj_align(chart_sniff_rssi, LV_ALIGN_TOP_MID, 0, 90);
    lv_chart_set_type(chart_sniff_rssi, LV_CHART_TYPE_LINE);
    lv_chart_set_range(chart_sniff_rssi, LV_CHART_AXIS_PRIMARY_Y, -135, -35);
    lv_chart_set_point_count(chart_sniff_rssi, RSSI_HISTORY_LEN);
    lv_chart_set_div_line_count(chart_sniff_rssi, 3, 0);
    lv_obj_set_style_bg_color(chart_sniff_rssi, lv_color_hex(0x0D0D1A), 0);
    lv_obj_set_style_border_color(chart_sniff_rssi, lv_color_hex(0x334455), 0);
    lv_obj_set_style_border_width(chart_sniff_rssi, 1, 0);
    lv_obj_set_style_line_color(chart_sniff_rssi, lv_color_hex(0x1A2A3A), LV_PART_MAIN);
    lv_obj_set_style_line_width(chart_sniff_rssi, 1, LV_PART_MAIN);
    lv_obj_set_style_size(chart_sniff_rssi, 0, LV_PART_INDICATOR);
    lv_obj_set_style_line_width(chart_sniff_rssi, 2, LV_PART_ITEMS);
    lv_obj_set_style_line_color(chart_sniff_rssi, lv_color_hex(0x00FF88), LV_PART_ITEMS);
    lv_obj_set_style_line_rounded(chart_sniff_rssi, true, LV_PART_ITEMS);
    lv_obj_clear_flag(chart_sniff_rssi, LV_OBJ_FLAG_SCROLLABLE);

    sniff_rssi_ser = lv_chart_add_series(chart_sniff_rssi, lv_color_hex(0x00FF88), LV_CHART_AXIS_PRIMARY_Y);
    for (int i = 0; i < RSSI_HISTORY_LEN; i++)
        lv_chart_set_value_by_id(chart_sniff_rssi, sniff_rssi_ser, i, -135);

    lbl_sniff_size = lv_label_create(scr_sniffer);
    lv_label_set_text(lbl_sniff_size, "Size: --- B");
    lv_obj_set_style_text_color(lbl_sniff_size, lv_color_hex(0xBBBBBB), 0);
    lv_obj_set_style_text_font(lbl_sniff_size, &lv_font_montserrat_10, 0);
    lv_obj_align(lbl_sniff_size, LV_ALIGN_TOP_LEFT, 5, 155);

    lbl_sniff_time = lv_label_create(scr_sniffer);
    lv_label_set_text(lbl_sniff_time, "Last: Never");
    lv_obj_set_style_text_color(lbl_sniff_time, lv_color_hex(0xBBBBBB), 0);
    lv_obj_set_style_text_font(lbl_sniff_time, &lv_font_montserrat_10, 0);
    lv_obj_align(lbl_sniff_time, LV_ALIGN_TOP_RIGHT, -10, 155);

    lbl_sniff_payload = lv_label_create(scr_sniffer);
    lv_label_set_text(lbl_sniff_payload, "Payload: ---");
    lv_obj_set_style_text_color(lbl_sniff_payload, lv_color_hex(0x00FFFF), 0);
    lv_obj_set_style_text_font(lbl_sniff_payload, &lv_font_montserrat_10, 0);
    lv_obj_set_style_bg_color(lbl_sniff_payload, lv_color_hex(0x0A0A22), 0);
    lv_obj_set_style_bg_opa(lbl_sniff_payload, LV_OPA_COVER, 0);
    lv_obj_set_style_pad_all(lbl_sniff_payload, 2, 0);
    lv_obj_set_width(lbl_sniff_payload, 310);
    lv_obj_align(lbl_sniff_payload, LV_ALIGN_TOP_LEFT, 5, 170);

    lbl_sniff_multifreq = lv_label_create(scr_sniffer);
    lv_label_set_text(lbl_sniff_multifreq, "");
    lv_obj_set_style_text_color(lbl_sniff_multifreq, lv_color_hex(0xFFAA00), 0);
    lv_obj_set_style_text_font(lbl_sniff_multifreq, &lv_font_montserrat_10, 0);
    lv_obj_set_width(lbl_sniff_multifreq, 310);
    lv_obj_align(lbl_sniff_multifreq, LV_ALIGN_BOTTOM_LEFT, 5, -5);

    make_back_btn(scr_sniffer);
}

void update_sniffer()
{
    if (!radio_ready || !sniffer_active)
        return;

    unsigned long now = millis();
    if (now - pkt_rate_last_calc >= 3000)
    {
        pkt_rate_per_sec = (float)pkt_rate_counter / ((now - pkt_rate_last_calc) / 1000.0);
        pkt_rate_counter = 0;
        pkt_rate_last_calc = now;
        char rb[32];
        snprintf(rb, sizeof(rb), "Rate: %.1f pkt/s", pkt_rate_per_sec);
        lv_label_set_text(lbl_sniff_rate, rb);
    }

    float listen_freq = target_frequency;
    if (multi_freq_mode)
    {
        if (now - multi_freq_dwell_time > 800)
        {
            multi_freq_current_idx = (multi_freq_current_idx + 1) % MULTI_FREQ_COUNT;
            multi_freq_dwell_time = now;
            invalidate_radio_config();
        }
        listen_freq = multi_freq_list[multi_freq_current_idx];
    }

    configure_radio_preset(current_sniff_preset, listen_freq, 0x2B, 2);

    static bool rx_active = false;
    if (!rx_active || applied_mode != 2)
    {
        radio_start_rx_locked();
        rx_active = true;
    }

    if (digitalRead(LORA_DIO1) == HIGH)
    {
        SPI_LOCK();
        size_t len = radio.getPacketLength();
        if (len > 0 && len < 256)
        {
            int state = radio.readData(sniff_packet_buf, len);
            SPI_UNLOCK();
            if (state == RADIOLIB_ERR_NONE || state == RADIOLIB_ERR_CRC_MISMATCH)
            {
                packet_count++;
                pkt_rate_counter++;
                SPI_LOCK();
                last_packet_rssi = radio.getRSSI();
                last_packet_snr = radio.getSNR();
                SPI_UNLOCK();
                last_packet_size = len;
                last_packet_time = millis();

                rssi_history[rssi_history_idx] = last_packet_rssi;
                lv_chart_set_value_by_id(chart_sniff_rssi, sniff_rssi_ser, rssi_history_idx, last_packet_rssi);
                rssi_history_idx = (rssi_history_idx + 1) % RSSI_HISTORY_LEN;
                if (rssi_history_idx == 0)
                    rssi_history_full = true;
                lv_chart_refresh(chart_sniff_rssi);

                int show_len = (len > 24) ? 24 : len;
                char *hp = hex_payload;
                hp += sprintf(hp, "HEX[%d]: ", len);
                for (int i = 0; i < show_len; i++)
                    hp += sprintf(hp, "%02X ", sniff_packet_buf[i]);
                if (len > 24)
                    strcat(hex_payload, "...");
                lv_label_set_text(lbl_sniff_payload, hex_payload);

                if (multi_freq_mode)
                {
                    multi_freq_pkt_count[multi_freq_current_idx]++;
                    multi_freq_rssi[multi_freq_current_idx] = last_packet_rssi;
                }

                lv_label_set_text(lbl_sniff_status, "PKT CAPTURED!");
                lv_obj_set_style_text_color(lbl_sniff_status, lv_color_hex(0x00FF00), 0);

                char b[48];
                snprintf(b, sizeof(b), "Cnt: %d", packet_count);
                lv_label_set_text(lbl_sniff_count, b);
                snprintf(b, sizeof(b), "RSSI:%d", last_packet_rssi);
                lv_label_set_text(lbl_sniff_rssi, b);
                snprintf(b, sizeof(b), "SNR:%.1f", last_packet_snr);
                lv_label_set_text(lbl_sniff_snr, b);
                snprintf(b, sizeof(b), "Size: %d bytes", last_packet_size);
                lv_label_set_text(lbl_sniff_size, b);
            }
        }
        else
        {
            SPI_UNLOCK();
        }
        radio_start_rx_locked();
    }

    if (packet_count > 0)
    {
        unsigned long ago = (millis() - last_packet_time) / 1000;
        char b[32];
        if (ago < 60)
            snprintf(b, sizeof(b), "Last: %lus ago", ago);
        else
            snprintf(b, sizeof(b), "Last: %lum ago", ago / 60);
        lv_label_set_text(lbl_sniff_time, b);
        if (ago > 3)
        {
            lv_label_set_text(lbl_sniff_status, "LISTENING...");
            lv_obj_set_style_text_color(lbl_sniff_status, lv_color_hex(0x00FF88), 0);
        }
    }

    if (multi_freq_mode)
    {
        char mf[128];
        int best_idx = 0, best_cnt = 0;
        char *mp = mf;
        mp += sprintf(mp, "MultiFreq: ");
        for (int i = 0; i < MULTI_FREQ_COUNT; i++)
        {
            mp += sprintf(mp, "%.1f:%d ", multi_freq_list[i], multi_freq_pkt_count[i]);
            if (multi_freq_pkt_count[i] > best_cnt)
            {
                best_cnt = multi_freq_pkt_count[i];
                best_idx = i;
            }
        }
        if (best_cnt > 0)
            mp += sprintf(mp, "| BEST:%.2f", multi_freq_list[best_idx]);
        lv_label_set_text(lbl_sniff_multifreq, mf);
    }
    else
    {
        char fb[48];
        snprintf(fb, sizeof(fb), "Freq: %.3f MHz", listen_freq);
        lv_label_set_text(lbl_sniff_multifreq, fb);
    }
}

// ==============================================================================
// 📘 10. ABOUT
// ==============================================================================
void build_about()
{
    scr_about = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(scr_about, lv_color_hex(0x0A0A1A), 0);

    lv_obj_t *t = lv_label_create(scr_about);
    lv_label_set_text(t, "SYSTEM INFO & HELP");
    lv_obj_set_style_text_color(t, lv_color_hex(0x795548), 0);
    lv_obj_set_style_text_font(t, &lv_font_montserrat_14, 0);
    lv_obj_align(t, LV_ALIGN_TOP_LEFT, 5, 8);
    make_back_btn(scr_about);

    lv_obj_t *scroll_container = lv_obj_create(scr_about);
    lv_obj_set_size(scroll_container, 310, 195);
    lv_obj_align(scroll_container, LV_ALIGN_BOTTOM_MID, 0, -5);
    lv_obj_set_style_bg_color(scroll_container, lv_color_hex(0x0A0A1A), 0);
    lv_obj_set_style_border_width(scroll_container, 0, 0);
    lv_obj_set_style_pad_all(scroll_container, 0, 0);

    lv_obj_t *c = lv_label_create(scroll_container);
    lv_label_set_long_mode(c, LV_LABEL_LONG_WRAP);
    lv_obj_set_width(c, 290);
    lv_obj_set_style_text_color(c, lv_color_hex(0xDDDDDD), 0);
    lv_obj_set_style_text_font(c, &lv_font_montserrat_10, 0);

    lv_label_set_text(c,
                      "=== PATHFINDER v1.0 ===\n"
                      "Advanced Tactical RF Multi-tool\n\n"
                      "[ SPECTRUM RTA ] Real-time analyzer\n"
                      "[ RSSI METER ] Signal tracker LoRa\n"
                      "[ NOISE FLOOR ] RF background scan\n"
                      "[ COMPASS NAV ] HSI aviation style\n"
                      "[ WIFI SCANNER ] 2.4GHz analyzer\n"
                      "[ PKT SNIFFER ] Capture LoRa packets\n"
                      "[ OFFLINE MAPS ] GPS tracking map\n\n"
                      "=== HARDWARE ===\n"
                      "Core: XIAO ESP32-S3 (8MB PSRAM)\n"
                      "Radio: WIO SX1262 TCXO 1.8V\n"
                      "Display: ILI9488 + XPT2046\n"
                      "GNSS: U-Blox M10\n"
                      "SPI: Shared Bus (TFT+Touch+LoRa+SD)\n\n"
                      "ZXS & Meshnode ID | 2026\n");
}

// ==============================================================================
// 📡 GPS SERIAL BACKGROUND
// ==============================================================================
void process_gps_serial()
{
    while (SerialGPS.available())
    {
        char c = SerialGPS.read();
        if (c == '\n' || c == '\r')
        {
            if (gps_line_idx > 10)
            {
                gps_line_buf[gps_line_idx] = '\0';
                parse_nmea_sentence(gps_line_buf);
            }
            gps_line_idx = 0;
        }
        else if (gps_line_idx < (int)sizeof(gps_line_buf) - 2)
        {
            gps_line_buf[gps_line_idx++] = c;
        }
    }
}

void auto_scan_gps_baudrate()
{
    uint32_t br[] = {115200, 38400, 9600};
    for (int i = 0; i < 3; i++)
    {
        SerialGPS.begin(br[i], SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
        unsigned long st = millis();
        while (millis() - st < 2500)
        {
            if (SerialGPS.available())
            {
                char c = SerialGPS.read();
                if (c == '$')
                {
                    String l = SerialGPS.readStringUntil('\n');
                    if (l.startsWith("GP") || l.startsWith("GN"))
                    {
                        Serial.printf("[GPS] Locked %d baud\n", br[i]);
                        gps_start_time = millis();
                        SerialGPS.setTimeout(50);
                        return;
                    }
                }
            }
        }
        SerialGPS.end();
    }
    SerialGPS.begin(115200, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
    SerialGPS.setTimeout(50);
    gps_start_time = millis();
}

// ==============================================================================
// 🚀 SETUP
// ==============================================================================
void setup()
{
    Serial.begin(115200);

    // Dual boot: point the boot partition back at the launcher, so any restart returns to the selection menu
    {
        const esp_partition_t *launcher =
            esp_partition_find_first(ESP_PARTITION_TYPE_APP, ESP_PARTITION_SUBTYPE_APP_FACTORY, NULL);
        if (launcher)
            esp_ota_set_boot_partition(launcher);
    }
    delay(800);
    Serial.println("\n--- ZXS PATHFINDER v1.0 ---");

    // 1. BUAT MUTEX SPI UNTUK SHARED BUS
    spi_mutex = xSemaphoreCreateMutex();
    if (!spi_mutex)
    {
        Serial.println("[FATAL] SPI Mutex creation failed!");
        while (1)
            ;
    }

    // 2. SET SEMUA CS SEBAGAI OUTPUT & HIGH (deselect semua)
    pinMode(TFT_CS, OUTPUT);
    digitalWrite(TFT_CS, HIGH);
    pinMode(TOUCH_CS, OUTPUT);
    digitalWrite(TOUCH_CS, HIGH);
    pinMode(LORA_CS, OUTPUT);
    digitalWrite(LORA_CS, HIGH);
    pinMode(SD_CS, OUTPUT);
    digitalWrite(SD_CS, HIGH);

    // 3. Reset LoRa manual
    pinMode(LORA_RST, OUTPUT);
    digitalWrite(LORA_RST, LOW);
    delay(20);
    digitalWrite(LORA_RST, HIGH);
    delay(50);

    // 4. Enable pull-up MISO untuk stabilitas SD
    pinMode(PIN_MISO, INPUT_PULLUP);

    // 5. INISIALISASI SPI BUS BERSAMA (SATU KALI!)
    sharedSPI.begin(PIN_SCK, PIN_MISO, PIN_MOSI, -1);
    delay(100);

    // 6. MOUNT SD CARD (via shared SPI, speed rendah untuk stabilitas)
    deselect_all_cs();
    if (!SD.begin(SD_CS, sharedSPI, 4000000))
    {
        Serial.println("[SD] Failed to mount SD Card!");
        sd_ready = false;
    }
    else
    {
        uint8_t cardType = SD.cardType();
        if (cardType == CARD_NONE)
        {
            Serial.println("[SD] Card detected but no media!");
            sd_ready = false;
        }
        else
        {
            Serial.printf("[SD] Mounted. Size: %llu MB\n", SD.cardSize() / (1024 * 1024));
            sd_ready = true;
        }
    }
    deselect_all_cs();
    // let the card release MISO: 16 clocks with every CS high, so it does not load the touch controller's data line
    sharedSPI.beginTransaction(SPISettings(400000, MSBFIRST, SPI_MODE0));
    sharedSPI.transfer16(0xFFFF);
    sharedSPI.endTransaction();

    // 7. INISIALISASI TFT (gunakan shared SPI - sudah dilempar lewat constructor)
    tft.init();
    tft.setRotation(PF_ROTATION);
    tft.setBrightness(200);
    tft.fillScreen(0x000000);
    deselect_all_cs();

    // 8. INISIALISASI TOUCH (XPT2046 kecepatan rendah)
    deselect_all_cs();

    // 9. INISIALISASI LVGL
    lv_init();
    lv_disp_draw_buf_init(&draw_buf, buf1, NULL, 320 * 20);

    static lv_disp_drv_t dd;
    lv_disp_drv_init(&dd);
    dd.hor_res = 320;
    dd.ver_res = 240;
    dd.flush_cb = my_flush;
    dd.draw_buf = &draw_buf;
    lv_disp_drv_register(&dd);

    static lv_indev_drv_t id;
    lv_indev_drv_init(&id);
    id.type = LV_INDEV_TYPE_POINTER;
    id.read_cb = my_touch;
    lv_indev_drv_register(&id);

    // 10. BUILD SEMUA LAYAR
    build_menu();
    build_spectrum();
    build_rssi();
    build_noise();
    build_gps();
    build_map();
    build_wifi();
    build_diag();
    build_sniffer();
    build_about();

    lv_scr_load(scr_menu);

    // 11. INISIALISASI GPS
    auto_scan_gps_baudrate();

    // 12. INISIALISASI LORA SX1262 DENGAN TCXO 1.8V
    Serial.println("[LoRa] Initializing SX1262 (TCXO 1.8V)...");
    deselect_all_cs();

    radio.XTAL = false;
    // Parameter: freq, bw, sf, cr, syncWord, power, preambleLength, tcxoVoltage, useRegulatorLDO
    int16_t lora_state = radio.begin(922.875, 250.0, 11, 5, 0x2B, 10, 16, 1.8, false);

    if (lora_state == RADIOLIB_ERR_NONE)
    {
        radio.setDio2AsRfSwitch(true);
        radio.setRfSwitchPins(LORA_RXEN, RADIOLIB_NC);
        radio.setRxBoostedGainMode(true);
        radio_ready = true;
        Serial.println("[LoRa] SX1262 Ready!");
    }
    else
    {
        Serial.printf("[LoRa] SX1262 FAILED! Error: %d\n", lora_state);
        radio_ready = false;
    }
    deselect_all_cs();

    // 13. WIFI
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();

    Serial.println("\n>>> PATHFINDER v1.0 READY! <<<\n");
}

// ==============================================================================
// 🔄 MAIN LOOP
// ==============================================================================
static unsigned long last_spec = 0, last_rssi_t = 0;
static unsigned long last_noise = 0, last_sniff = 0;
static unsigned long last_gps = 0, last_map = 0;

void loop()
{
    lv_timer_handler();

    lv_obj_t *cur = lv_scr_act();
    unsigned long now = millis();

    process_gps_serial();

    if (cur == scr_spectrum && spectrum_scanning && (now - last_spec > 50))
    {
        update_spectrum();
        last_spec = now;
    }
    if (cur == scr_rssi && radio_ready && (now - last_rssi_t > 120))
    {
        update_rssi();
        last_rssi_t = now;
    }
    if (cur == scr_noise && radio_ready && (now - last_noise > 80))
    {
        update_noise();
        last_noise = now;
    }
    if (cur == scr_sniffer && sniffer_active && (now - last_sniff > 100))
    {
        update_sniffer();
        last_sniff = now;
    }
    if (cur == scr_diag)
    {
        update_diag();
    }
    if (cur == scr_gps && (now - last_gps > 100))
    {
        update_gps();
        last_gps = now;
    }
    if (cur == scr_map && (now - last_map > 100))
    {
        update_map();
        last_map = now;
    }
    if (cur == scr_wifi)
    {
        process_wifi_results();
    }

    delay(5);
}