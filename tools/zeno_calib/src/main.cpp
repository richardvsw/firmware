/*
 * ================================================================
 *  📋 TABEL PANDUAN LAYAR TFT SPI (MODUL PCB MERAH)
 *     Chip Touch: XPT2046 / HR2046 / ADS7843 (Semua Sama)
 *     Board: ESP32-S3 Goou
 * ================================================================
 *
 *  ┌──────────┬─────────────┬──────────────┬──────────┬───────────────────────┐
 *  │  UKURAN  │  RESOLUSI   │  DRIVER LCD  │  TOUCH   │  YANG PERLU DIUBAH    │
 *  │  LAYAR   │  (PIXEL)    │  (Library)   │  CHIP    │  DI KODE              │
 *  ├──────────┼─────────────┼──────────────┼──────────┼───────────────────────┤
 *  │  2.4"    │  320 x 240  │  ILI9341     │ XPT2046  │  Tidak ada (langsung) │
 *  │  2.8"    │  320 x 240  │  ILI9341     │ XPT2046  │  Tidak ada (langsung) │
 *  │  3.2"    │  320 x 240  │  ILI9341     │ XPT2046  │  Tidak ada (langsung) │
 *  │  3.5"    │  480 x 320  │  ILI9488     │ XPT2046  │  Ganti resolusi &     │
 *  │          │             │  / ST7796    │          │  driver LCD           │
 *  │  4.0"    │  480 x 320  │  ST7796      │ XPT2046  │  Ganti resolusi &     │
 *  │          │             │  / ILI9486   │          │  driver LCD           │
 *  └──────────┴─────────────┴──────────────┴──────────┴───────────────────────┘
 *
 *  📌 CARA GANTI UKURAN LAYAR:
 *     1. Ubah SCREEN_WIDTH dan SCREEN_HEIGHT di bawah.
 *     2. Untuk 3.5"/4.0", ganti library driver LCD.
 *     3. Upload ulang & kalibrasi 2 titik.
 *
 *  📌 PINOUT ESP32-S3 GOUU:
 *     TFT_CS=15, TFT_DC=16, TFT_RST=3, TFT_BL=4
 *     MOSI=11, SCK=12, MISO=13
 *     TOUCH_CS=5, TOUCH_IRQ=6
 *
 *  📌 HASIL KALIBRASI ANDA:
 *     #define TOUCH_CAL_X_MIN   ____
 *     #define TOUCH_CAL_X_MAX   ____
 *     #define TOUCH_CAL_Y_MIN   ____
 *     #define TOUCH_CAL_Y_MAX   ____
 * ================================================================
 */

#include <Arduino.h>
#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ILI9341.h> // Ganti library ini jika driver LCD-nya bukan ILI9341 (misal ILI9488)
#include <XPT2046_Touchscreen.h>

// =======================================================
//  🔧 PENGATURAN UKURAN LAYAR (UBAH DI SINI)
//  2.4" / 2.8" / 3.2"  →  320 x 240
//  3.5" / 4.0"         →  480 x 320
// =======================================================
#define SCREEN_WIDTH 320
#define SCREEN_HEIGHT 240
// =======================================================

#define TFT_CS 15
#define TFT_DC 16
#define TFT_RST 3
#define TFT_BL 4
#define TOUCH_CS 5
#define TOUCH_IRQ 6
#define SPI_SCK 12
#define SPI_MOSI 11
#define SPI_MISO 13

Adafruit_ILI9341 tft = Adafruit_ILI9341(TFT_CS, TFT_DC, TFT_RST);
XPT2046_Touchscreen ts(TOUCH_CS, TOUCH_IRQ);

const int T1_X = SCREEN_WIDTH * 0.1;
const int T1_Y = SCREEN_HEIGHT * 0.1;
const int T2_X = SCREEN_WIDTH * 0.9;
const int T2_Y = SCREEN_HEIGHT * 0.9;

int raw_x1 = 0, raw_y1 = 0;
int raw_x2 = 0, raw_y2 = 0;
int final_adc_x_min = 0, final_adc_x_max = 0;
int final_adc_y_min = 0, final_adc_y_max = 0;
unsigned long waktuSebelumnya = 0;

void drawTarget(int x, int y, uint16_t color)
{
    tft.drawCircle(x, y, 12, color);
    tft.drawCircle(x, y, 4, color);
    tft.drawFastHLine(x - 18, y, 36, color);
    tft.drawFastVLine(x, y - 18, 36, color);
}

void getSample(int targetX, int targetY, int &outX, int &outY)
{
    drawTarget(targetX, targetY, ILI9341_RED);
    while (!ts.touched())
        delay(10);
    long sumX = 0, sumY = 0;
    int count = 0;
    while (ts.touched() && count < 30)
    {
        TS_Point p = ts.getPoint();
        sumX += p.x;
        sumY += p.y;
        count++;
        delay(10);
    }
    outX = sumX / count;
    outY = sumY / count;
    drawTarget(targetX, targetY, ILI9341_GREEN);
    delay(400);
    drawTarget(targetX, targetY, ILI9341_BLACK);
}

void hitungHasilAkhirADC()
{
    float dx = T2_X - T1_X, dy = T2_Y - T1_Y;
    float ax = (float)(raw_x2 - raw_x1) / dx;
    float ay = (float)(raw_y2 - raw_y1) / dy;
    final_adc_x_min = raw_x1 - (int)(ax * T1_X);
    final_adc_x_max = raw_x1 + (int)(ax * (SCREEN_WIDTH - T1_X));
    final_adc_y_min = raw_y1 - (int)(ay * T1_Y);
    final_adc_y_max = raw_y1 + (int)(ay * (SCREEN_HEIGHT - T1_Y));
}

void cetakKodeKeSerial()
{
    Serial.println("\n=======================================================");
    Serial.printf("   HASIL KALIBRASI %d x %d px\n", SCREEN_WIDTH, SCREEN_HEIGHT);
    Serial.println("=======================================================");
    Serial.printf("#define TOUCH_CAL_X_MIN   %d\n", final_adc_x_min);
    Serial.printf("#define TOUCH_CAL_X_MAX   %d\n", final_adc_x_max);
    Serial.printf("#define TOUCH_CAL_Y_MIN   %d\n", final_adc_y_min);
    Serial.printf("#define TOUCH_CAL_Y_MAX   %d\n", final_adc_y_max);
    Serial.println("=======================================================\n");
}

void tampilkanHasilKeLayarTFT()
{
    tft.fillScreen(ILI9341_BLACK);
    tft.setTextColor(ILI9341_GREEN);
    tft.setTextSize(2);
    tft.setCursor(10, 10);
    tft.printf("CALIB %dx%d", SCREEN_WIDTH, SCREEN_HEIGHT);
    tft.setTextColor(ILI9341_YELLOW);
    tft.setTextSize(2);
    tft.setCursor(10, 50);
    tft.printf("X_MIN: %d", final_adc_x_min);
    tft.setCursor(170, 50);
    tft.printf("X_MAX: %d", final_adc_x_max);
    tft.setCursor(10, 75);
    tft.printf("Y_MIN: %d", final_adc_y_min);
    tft.setCursor(170, 75);
    tft.printf("Y_MAX: %d", final_adc_y_max);
    tft.setTextColor(ILI9341_CYAN);
    tft.setTextSize(1);
    tft.setCursor(10, 105);
    tft.printf("#define TOUCH_CAL_X_MIN  %d", final_adc_x_min);
    tft.setCursor(10, 117);
    tft.printf("#define TOUCH_CAL_X_MAX  %d", final_adc_x_max);
    tft.setCursor(10, 129);
    tft.printf("#define TOUCH_CAL_Y_MIN  %d", final_adc_y_min);
    tft.setCursor(10, 141);
    tft.printf("#define TOUCH_CAL_Y_MAX  %d", final_adc_y_max);
    int lineY = SCREEN_HEIGHT - 75;
    tft.drawFastHLine(0, lineY, SCREEN_WIDTH, ILI9341_DARKGREY);
    tft.setTextColor(ILI9341_LIGHTGREY);
    tft.setCursor(10, lineY + 6);
    tft.println("Uji sentuh di bawah garis:");
}

void setup()
{
    Serial.begin(115200);
    while (!Serial && millis() < 3000)
        delay(10);
    pinMode(TFT_BL, OUTPUT);
    digitalWrite(TFT_BL, HIGH);
    SPI.begin(SPI_SCK, SPI_MISO, SPI_MOSI);
    tft.begin();
    tft.setRotation(1);
    tft.fillScreen(ILI9341_BLACK);
    ts.begin();
    ts.setRotation(1);
    tft.setTextColor(ILI9341_CYAN);
    tft.setTextSize(2);
    tft.setCursor(20, 20);
    tft.println("UNIVERSAL 2.4-4");
    tft.setTextColor(ILI9341_WHITE);
    tft.setTextSize(1);
    tft.setCursor(20, 60);
    tft.printf("Layar: %d x %d px", SCREEN_WIDTH, SCREEN_HEIGHT);
    delay(2500);
    tft.fillScreen(ILI9341_BLACK);
    tft.setCursor(20, SCREEN_HEIGHT / 2);
    tft.setTextColor(ILI9341_YELLOW);
    tft.print("1. Sentuh KIRI ATAS");
    getSample(T1_X, T1_Y, raw_x1, raw_y1);
    tft.fillScreen(ILI9341_BLACK);
    tft.setCursor(20, SCREEN_HEIGHT / 2);
    tft.setTextColor(ILI9341_YELLOW);
    tft.print("2. Sentuh KANAN BAWAH");
    getSample(T2_X, T2_Y, raw_x2, raw_y2);
    hitungHasilAkhirADC();
    cetakKodeKeSerial();
    tampilkanHasilKeLayarTFT();
}

void loop()
{
    if (millis() - waktuSebelumnya >= 3000)
    {
        waktuSebelumnya = millis();
        cetakKodeKeSerial();
    }
    if (ts.touched())
    {
        TS_Point p = ts.getPoint();
        int px = constrain(map(p.x, final_adc_x_min, final_adc_x_max, 0, SCREEN_WIDTH), 0, SCREEN_WIDTH);
        int py = constrain(map(p.y, final_adc_y_min, final_adc_y_max, 0, SCREEN_HEIGHT), 0, SCREEN_HEIGHT);
        if (py > SCREEN_HEIGHT - 60)
            tft.fillCircle(px, py, 3, ILI9341_GREEN);
        tft.fillRect(0, SCREEN_HEIGHT - 18, SCREEN_WIDTH, 18, ILI9341_BLACK);
        tft.setTextColor(ILI9341_WHITE, ILI9341_BLACK);
        tft.setTextSize(1);
        tft.setCursor(10, SCREEN_HEIGHT - 14);
        tft.printf("ADC:[%4d,%4d] -> Pixel:[%3d,%3d]", p.x, p.y, px, py);
    }
    delay(10);
}