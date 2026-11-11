// Digital 74HCT245 model. The project uses DIR=HIGH and OE=LOW (A to B).
// Voltage thresholds and analog current are not simulated.

#include "wokwi-api.h"
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>

typedef struct {
  pin_t a[8];
  pin_t b[8];
  pin_t dir;
  pin_t oe;
} chip_state_t;

static const char *const A_NAMES[8] = {
  "A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"
};
static const char *const B_NAMES[8] = {
  "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8"
};

static void update_bus(chip_state_t *chip) {
  const bool enabled = pin_read(chip->oe) == LOW;
  const bool a_to_b = pin_read(chip->dir) == HIGH;

  for (uint8_t i = 0; i < 8; i++) {
    if (!enabled) {
      pin_mode(chip->a[i], INPUT);
      pin_mode(chip->b[i], INPUT);
    } else if (a_to_b) {
      pin_mode(chip->a[i], INPUT);
      pin_mode(chip->b[i], OUTPUT);
      pin_write(chip->b[i], pin_read(chip->a[i]));
    } else {
      pin_mode(chip->b[i], INPUT);
      pin_mode(chip->a[i], OUTPUT);
      pin_write(chip->a[i], pin_read(chip->b[i]));
    }
  }
}

static void on_pin_change(void *user_data, pin_t pin, uint32_t value) {
  (void)pin;
  (void)value;
  update_bus(user_data);
}

void chip_init(void) {
  chip_state_t *chip = calloc(1, sizeof(chip_state_t));
  chip->dir = pin_init("DIR", INPUT_PULLUP);
  chip->oe = pin_init("OE", INPUT_PULLUP);
  for (uint8_t i = 0; i < 8; i++) {
    chip->a[i] = pin_init(A_NAMES[i], INPUT);
    chip->b[i] = pin_init(B_NAMES[i], OUTPUT_LOW);
  }
  pin_init("VCC", INPUT);
  pin_init("GND", INPUT);

  const pin_watch_config_t watch = {
    .edge = BOTH,
    .pin_change = on_pin_change,
    .user_data = chip,
  };
  pin_watch(chip->dir, &watch);
  pin_watch(chip->oe, &watch);
  for (uint8_t i = 0; i < 8; i++) {
    pin_watch(chip->a[i], &watch);
    pin_watch(chip->b[i], &watch);
  }
  update_bus(chip);
}
