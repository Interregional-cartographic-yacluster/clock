// ESP32 + TM1640 HH:MM:SS demonstration for Wokwi.
// No external Arduino libraries are required.

#include <Arduino.h>

constexpr uint8_t PIN_SCLK = 25;
constexpr uint8_t PIN_DIN = 26;
constexpr uint8_t PIN_COLON_BUTTON = 32;
constexpr uint8_t PIN_DP_BUTTON = 33;

constexpr uint8_t TM1640_DATA_AUTO = 0x40;
constexpr uint8_t TM1640_ADDRESS_0 = 0xc0;
constexpr uint8_t TM1640_DISPLAY_ON_MAX = 0x8f;

// Bits: SEG1=a … SEG7=g, SEG8=DP.
const uint8_t DIGITS[10] = {
  0x3f, 0x06, 0x5b, 0x4f, 0x66,
  0x6d, 0x7d, 0x07, 0x7f, 0x6f,
};

enum ColonMode : uint8_t { COLON_STEADY, COLON_BLINK, COLON_OFF };
ColonMode colonMode = COLON_BLINK;
bool decimalPoints = false;
uint32_t lastDisplayUpdate = 0;
uint32_t demoStartedAt = 0;

class Button {
 public:
  explicit Button(uint8_t pin) : pin_(pin) {}

  void begin() {
    pinMode(pin_, INPUT_PULLUP);
    lastReading_ = digitalRead(pin_);
    stableState_ = lastReading_;
    changedAt_ = millis();
  }

  bool pressed() {
    const uint8_t reading = digitalRead(pin_);
    const uint32_t now = millis();
    if (reading != lastReading_) {
      lastReading_ = reading;
      changedAt_ = now;
    }
    if (reading != stableState_ && now - changedAt_ >= 35) {
      stableState_ = reading;
      if (stableState_ == LOW) {
        return true;
      }
    }
    return false;
  }

 private:
  uint8_t pin_;
  uint8_t lastReading_ = HIGH;
  uint8_t stableState_ = HIGH;
  uint32_t changedAt_ = 0;
};

Button colonButton(PIN_COLON_BUTTON);
Button dpButton(PIN_DP_BUTTON);

void tm1640_start() {
  digitalWrite(PIN_SCLK, HIGH);
  digitalWrite(PIN_DIN, HIGH);
  delayMicroseconds(2);
  digitalWrite(PIN_DIN, LOW); // START while SCLK is HIGH.
  delayMicroseconds(2);
  digitalWrite(PIN_SCLK, LOW);
}

void tm1640_stop() {
  digitalWrite(PIN_SCLK, LOW);
  digitalWrite(PIN_DIN, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_SCLK, HIGH);
  delayMicroseconds(2);
  digitalWrite(PIN_DIN, HIGH); // STOP while SCLK is HIGH.
  delayMicroseconds(2);
}

void tm1640_write_byte(uint8_t value) {
  for (uint8_t bit = 0; bit < 8; bit++) {
    digitalWrite(PIN_SCLK, LOW);
    digitalWrite(PIN_DIN, (value & (1u << bit)) ? HIGH : LOW);
    delayMicroseconds(2);
    digitalWrite(PIN_SCLK, HIGH); // TM1640 samples DIN on the rising edge.
    delayMicroseconds(2);
  }
}

void tm1640_command(uint8_t command) {
  tm1640_start();
  tm1640_write_byte(command);
  tm1640_stop();
}

void tm1640_write_ram(const uint8_t ram[8]) {
  tm1640_start();
  tm1640_write_byte(TM1640_ADDRESS_0);
  for (uint8_t i = 0; i < 8; i++) {
    tm1640_write_byte(ram[i]);
  }
  tm1640_stop();
  tm1640_command(TM1640_DISPLAY_ON_MAX);
}

void show_time(uint32_t elapsedMilliseconds) {
  constexpr uint32_t DEMO_START = 12UL * 3600UL + 34UL * 60UL + 56UL;
  const uint32_t now = (DEMO_START + elapsedMilliseconds / 1000UL) % 86400UL;
  const uint8_t hour = now / 3600UL;
  const uint8_t minute = (now / 60UL) % 60UL;
  const uint8_t second = now % 60UL;

  bool colonOn = colonMode != COLON_OFF;
  if (colonMode == COLON_BLINK) {
    colonOn = (elapsedMilliseconds % 1000UL) < 500UL;
  }
  const uint8_t dp = decimalPoints ? 0x80 : 0x00;

  uint8_t ram[8] = {
    static_cast<uint8_t>(DIGITS[hour / 10] | dp),
    static_cast<uint8_t>(DIGITS[hour % 10] | dp),
    static_cast<uint8_t>(colonOn ? 0x03 : 0x00),
    static_cast<uint8_t>(DIGITS[minute / 10] | dp),
    static_cast<uint8_t>(DIGITS[minute % 10] | dp),
    static_cast<uint8_t>(colonOn ? 0x03 : 0x00),
    static_cast<uint8_t>(DIGITS[second / 10] | dp),
    static_cast<uint8_t>(DIGITS[second % 10] | dp),
  };
  tm1640_write_ram(ram);
}

void print_colon_mode() {
  Serial.print(F("Colon mode: "));
  if (colonMode == COLON_STEADY) Serial.println(F("steady"));
  if (colonMode == COLON_BLINK) Serial.println(F("1 Hz blink"));
  if (colonMode == COLON_OFF) Serial.println(F("off"));
}

void setup() {
  Serial.begin(115200);
  colonButton.begin();
  dpButton.begin();

  pinMode(PIN_SCLK, OUTPUT);
  pinMode(PIN_DIN, OUTPUT);
  digitalWrite(PIN_SCLK, HIGH);
  digitalWrite(PIN_DIN, HIGH);

  tm1640_command(TM1640_DATA_AUTO);
  uint8_t lampTest[8];
  for (uint8_t &value : lampTest) value = 0xff;
  tm1640_write_ram(lampTest); // All 52 LEDs on for one second.
  Serial.println(F("TM1640 lamp test: all segments"));
  delay(1000);

  Serial.println(F("Demo clock starts at 12:34:56"));
  Serial.println(F("Button C / key C: colon steady -> blink -> off"));
  Serial.println(F("Button D / key D: decimal points on/off"));
  print_colon_mode();
  demoStartedAt = millis();
  show_time(0);
}

void loop() {
  if (colonButton.pressed()) {
    colonMode = static_cast<ColonMode>((colonMode + 1) % 3);
    print_colon_mode();
    lastDisplayUpdate = 0;
  }
  if (dpButton.pressed()) {
    decimalPoints = !decimalPoints;
    Serial.print(F("Decimal points: "));
    Serial.println(decimalPoints ? F("on") : F("off"));
    lastDisplayUpdate = 0;
  }

  const uint32_t now = millis();
  if (now - lastDisplayUpdate >= 100) {
    lastDisplayUpdate = now;
    show_time(now - demoStartedAt);
  }
}
