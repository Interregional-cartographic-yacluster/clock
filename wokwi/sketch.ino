// Breadboard clock: ESP32 + ST7789 + DS3231 + TM1640, 46 LEDs, no DP.
#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <RTClib.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>

constexpr uint8_t PIN_SCLK = 25;
constexpr uint8_t PIN_DIN = 26;
constexpr uint8_t PIN_CITY_BUTTON = 32;
constexpr uint8_t TM1640_DATA_AUTO = 0x40;
constexpr uint8_t TM1640_ADDRESS_0 = 0xc0;
constexpr uint8_t TM1640_DISPLAY_ON_MAX = 0x8f;

RTC_DS3231 rtc;
Adafruit_ST7789 tft(5, 15, 4); // CS, DC, RST; SPI SCLK=18, MOSI=23.
bool rtcAvailable = false;
bool setupScreen = false;
uint8_t cityIndex = 0;
const char *const CITIES[] = {"Kursk", "Moscow", "London", "Tokyo"};

const uint8_t DIGITS[10] = {
  0x3f, 0x06, 0x5b, 0x4f, 0x66,
  0x6d, 0x7d, 0x07, 0x7f, 0x6f,
};

void tm1640_start() {
  digitalWrite(PIN_SCLK, HIGH); digitalWrite(PIN_DIN, HIGH);
  delayMicroseconds(2); digitalWrite(PIN_DIN, LOW);
  delayMicroseconds(2); digitalWrite(PIN_SCLK, LOW);
}
void tm1640_stop() {
  digitalWrite(PIN_SCLK, LOW); digitalWrite(PIN_DIN, LOW);
  delayMicroseconds(2); digitalWrite(PIN_SCLK, HIGH);
  delayMicroseconds(2); digitalWrite(PIN_DIN, HIGH);
  delayMicroseconds(2);
}
void tm1640_write_byte(uint8_t value) {
  for (uint8_t bit = 0; bit < 8; bit++) {
    digitalWrite(PIN_SCLK, LOW);
    digitalWrite(PIN_DIN, (value & (1u << bit)) ? HIGH : LOW);
    delayMicroseconds(2); digitalWrite(PIN_SCLK, HIGH);
    delayMicroseconds(2);
  }
}
void tm1640_command(uint8_t command) {
  tm1640_start(); tm1640_write_byte(command); tm1640_stop();
}
void tm1640_write_ram(const uint8_t ram[8]) {
  tm1640_start(); tm1640_write_byte(TM1640_ADDRESS_0);
  for (uint8_t i = 0; i < 8; i++) tm1640_write_byte(ram[i]);
  tm1640_stop(); tm1640_command(TM1640_DISPLAY_ON_MAX);
}

void show_time(uint8_t hour, uint8_t minute, uint8_t second, bool colonOn) {
  const uint8_t colon = colonOn ? 0x03 : 0x00;
  const uint8_t ram[8] = {
    DIGITS[hour / 10], DIGITS[hour % 10], colon,
    DIGITS[minute / 10], DIGITS[minute % 10], colon,
    DIGITS[second / 10], DIGITS[second % 10],
  };
  tm1640_write_ram(ram);
}

void draw_screen(uint8_t hour, uint8_t minute, uint8_t second) {
  tft.fillScreen(ST77XX_BLACK);
  tft.setTextWrap(false);
  if (setupScreen) {
    tft.setTextColor(ST77XX_ORANGE, ST77XX_BLACK);
    tft.setTextSize(2); tft.setCursor(8, 8); tft.print(F("Wi-Fi SETUP"));
    tft.setTextColor(ST77XX_WHITE, ST77XX_BLACK);
    tft.setTextSize(1); tft.setCursor(8, 38); tft.print(F("Network: Clock-Setup"));
    tft.setCursor(8, 54); tft.print(F("Short press C to return"));
    return;
  }
  char text[16];
  tft.setTextColor(ST77XX_CYAN, ST77XX_BLACK);
  tft.setTextSize(2); tft.setCursor(6, 4); tft.print(CITIES[cityIndex]);
  snprintf(text, sizeof(text), "%02u:%02u:%02u", hour, minute, second);
  tft.setTextColor(ST77XX_WHITE, ST77XX_BLACK);
  tft.setTextSize(3); tft.setCursor(6, 29); tft.print(text);
  tft.setTextSize(1); tft.setCursor(6, 62);
  tft.setTextColor(rtcAvailable ? ST77XX_GREEN : ST77XX_RED, ST77XX_BLACK);
  tft.print(rtcAvailable ? F("DS3231 OK  |  C: city / hold Wi-Fi") : F("RTC ERROR"));
}

void short_press() {
  if (setupScreen) {
    setupScreen = false;
    Serial.println(F("Wi-Fi setup screen closed"));
  } else {
    cityIndex = (cityIndex + 1) % (sizeof(CITIES) / sizeof(CITIES[0]));
    Serial.print(F("City: ")); Serial.println(CITIES[cityIndex]);
  }
}

// Debounced button with separate short-press and five-second-hold actions.
uint8_t stableButton = HIGH;
uint8_t rawButton = HIGH;
uint32_t rawChangedAt = 0;
uint32_t pressStartedAt = 0;
bool holdFired = false;
void update_button() {
  const uint32_t now = millis();
  const uint8_t reading = digitalRead(PIN_CITY_BUTTON);
  if (reading != rawButton) { rawButton = reading; rawChangedAt = now; }
  if (reading != stableButton && now - rawChangedAt >= 35) {
    stableButton = reading;
    if (stableButton == LOW) {
      pressStartedAt = now; holdFired = false;
    } else if (!holdFired) {
      short_press();
    }
  }
  if (stableButton == LOW && !holdFired && now - pressStartedAt >= 5000) {
    holdFired = true; setupScreen = true;
    Serial.println(F("Wi-Fi setup: Clock-Setup (display demonstration)"));
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println();
  Serial.println(F("Breadboard clock starting..."));
  pinMode(PIN_CITY_BUTTON, INPUT_PULLUP);
  pinMode(PIN_SCLK, OUTPUT); pinMode(PIN_DIN, OUTPUT);
  digitalWrite(PIN_SCLK, HIGH); digitalWrite(PIN_DIN, HIGH);

  // Paint the TFT before touching the RTC: a visible startup screen also
  // distinguishes a missing/stalled RTC from a display wiring problem.
  tft.init(284, 76);
  tft.setSPISpeed(40000000);
  tft.setRotation(0);
  tft.fillScreen(ST77XX_BLACK);
  tft.setTextColor(ST77XX_ORANGE, ST77XX_BLACK);
  tft.setTextSize(2); tft.setCursor(8, 24); tft.print(F("CLOCK START"));
  Serial.println(F("ST7789 initialized; connecting to DS3231..."));

  Wire.begin(21, 22);
  rtcAvailable = rtc.begin();
  if (rtcAvailable && rtc.lostPower()) {
    rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
    Serial.println(F("DS3231 time set from build timestamp"));
  }

  tm1640_command(TM1640_DATA_AUTO);
  const uint8_t lampTest[8] = {0x7f, 0x7f, 0x03, 0x7f, 0x7f, 0x03, 0x7f, 0x7f};
  tm1640_write_ram(lampTest); // All 46 LEDs, no SEG8/DP.
  Serial.println(F("Lamp test: 46 LEDs; direct TM1640 control"));
  Serial.println(F("C / GPIO32: short=city, hold 5s=Wi-Fi setup"));
  delay(1000);
}

void loop() {
  update_button();
  DateTime now = rtcAvailable ? rtc.now() : DateTime(2026, 1, 1, 12, 0, (millis() / 1000) % 60);
  const uint32_t milliseconds = millis();
  show_time(now.hour(), now.minute(), now.second(), (milliseconds % 1000) < 500);

  static uint32_t lastScreenKey = 0xffffffffUL;
  const uint32_t screenKey = now.unixtime() ^ (cityIndex << 24) ^ (setupScreen ? 0x80000000UL : 0);
  if (screenKey != lastScreenKey) {
    lastScreenKey = screenKey;
    draw_screen(now.hour(), now.minute(), now.second());
  }
  delay(80);
}
