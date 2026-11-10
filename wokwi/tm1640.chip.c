// TM1640 digital model for the Wokwi simulator.
// Implements the two-wire protocol, 16-byte display RAM and common-cathode scanning.
// Analog voltage/current behaviour is intentionally outside this digital model.

#include "wokwi-api.h"
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
  pin_t din;
  pin_t sclk;
  pin_t seg[8];
  pin_t grid[16];
  timer_t scan_timer;

  uint8_t ram[16];
  uint8_t command;
  uint8_t data_mode;
  uint8_t address;
  uint8_t shift;
  uint8_t bit_count;
  uint8_t brightness;
  uint8_t active_grid;
  bool receiving;
  bool awaiting_command;
  bool display_on;
} chip_state_t;

static const char *const SEG_NAMES[8] = {
  "SEG1", "SEG2", "SEG3", "SEG4", "SEG5", "SEG6", "SEG7", "SEG8"
};

static const char *const GRID_NAMES[16] = {
  "GRID1", "GRID2", "GRID3", "GRID4",
  "GRID5", "GRID6", "GRID7", "GRID8",
  "GRID9", "GRID10", "GRID11", "GRID12",
  "GRID13", "GRID14", "GRID15", "GRID16"
};

static void clear_outputs(chip_state_t *chip) {
  for (uint8_t i = 0; i < 8; i++) {
    pin_write(chip->seg[i], LOW);
  }
  for (uint8_t i = 0; i < 16; i++) {
    pin_write(chip->grid[i], HIGH);
  }
}

static void scan_next_grid(void *user_data) {
  chip_state_t *chip = user_data;

  pin_write(chip->grid[chip->active_grid], HIGH);
  for (uint8_t i = 0; i < 8; i++) {
    pin_write(chip->seg[i], LOW);
  }

  chip->active_grid = (chip->active_grid + 1) & 0x0f;
  if (!chip->display_on) {
    return;
  }

  const uint8_t value = chip->ram[chip->active_grid];
  for (uint8_t bit = 0; bit < 8; bit++) {
    pin_write(chip->seg[bit], (value & (1u << bit)) ? HIGH : LOW);
  }
  // A GRID output sinks current: the active common cathode is LOW.
  pin_write(chip->grid[chip->active_grid], LOW);
}

static void receive_byte(chip_state_t *chip, uint8_t value) {
  if (chip->awaiting_command) {
    chip->command = value;
    chip->awaiting_command = false;

    switch (value & 0xc0) {
      case 0x80: // Display control: 0x80…0x8f.
        chip->display_on = (value & 0x08) != 0;
        chip->brightness = value & 0x07;
        if (!chip->display_on) {
          clear_outputs(chip);
        }
        break;
      case 0x40: // Data mode: automatic/fixed address, read/write.
        chip->data_mode = value;
        break;
      case 0xc0: // Display RAM address: 0xc0…0xcf.
        chip->address = value & 0x0f;
        break;
      default:
        break; // 0x00…0x3f are not valid TM1640 commands.
    }
    return;
  }

  // Only an address command is followed by display RAM data bytes.
  if ((chip->command & 0xc0) != 0xc0) {
    return;
  }

  chip->ram[chip->address] = value;
  // 0x44 selects fixed-address mode; 0x40 auto-increments the address.
  if ((chip->data_mode & 0x04) == 0) {
    chip->address = (chip->address + 1) & 0x0f;
  }
}

static void on_din_change(void *user_data, pin_t pin, uint32_t value) {
  (void)pin;
  chip_state_t *chip = user_data;
  if (pin_read(chip->sclk) == LOW) {
    return;
  }

  if (value == LOW) { // START: DIN falls while SCLK is HIGH.
    chip->receiving = true;
    chip->awaiting_command = true;
    chip->shift = 0;
    chip->bit_count = 0;
  } else if (chip->receiving) { // STOP: DIN rises while SCLK is HIGH.
    chip->receiving = false;
    chip->shift = 0;
    chip->bit_count = 0;
  }
}

static void on_sclk_change(void *user_data, pin_t pin, uint32_t value) {
  (void)pin;
  chip_state_t *chip = user_data;
  if (!chip->receiving || value != HIGH) {
    return;
  }

  if (pin_read(chip->din) != LOW) {
    chip->shift |= 1u << chip->bit_count; // TM1640 sends LSB first.
  }
  chip->bit_count++;
  if (chip->bit_count == 8) {
    receive_byte(chip, chip->shift);
    chip->shift = 0;
    chip->bit_count = 0;
  }
}

void chip_init(void) {
  chip_state_t *chip = calloc(1, sizeof(chip_state_t));
  chip->data_mode = 0x40;
  chip->din = pin_init("DIN", INPUT);
  chip->sclk = pin_init("SCLK", INPUT);

  for (uint8_t i = 0; i < 8; i++) {
    chip->seg[i] = pin_init(SEG_NAMES[i], OUTPUT_LOW);
  }
  for (uint8_t i = 0; i < 16; i++) {
    chip->grid[i] = pin_init(GRID_NAMES[i], OUTPUT_HIGH);
  }
  pin_init("VDD", INPUT);
  pin_init("GND", INPUT);

  const pin_watch_config_t din_watch = {
    .edge = BOTH,
    .pin_change = on_din_change,
    .user_data = chip,
  };
  const pin_watch_config_t sclk_watch = {
    .edge = RISING,
    .pin_change = on_sclk_change,
    .user_data = chip,
  };
  pin_watch(chip->din, &din_watch);
  pin_watch(chip->sclk, &sclk_watch);

  const timer_config_t timer_config = {
    .callback = scan_next_grid,
    .user_data = chip,
  };
  chip->scan_timer = timer_init(&timer_config);
  timer_start(chip->scan_timer, 250, true); // 16 grids: 250 Hz full refresh.
}
