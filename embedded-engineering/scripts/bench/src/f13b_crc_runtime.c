#include "bench.h"
static uint8_t g_crc8[256];
static void crc8_init(void) { for (uint32_t i = 0U; i < 256U; i++) { uint8_t c = (uint8_t)i; for (uint32_t b = 0U; b < 8U; b++) { c = (uint8_t)(((c & 0x80U) != 0U) ? ((uint32_t)(c << 1) ^ 0x07U) : (uint32_t)(c << 1)); } g_crc8[i] = c; } }
int main(void) { crc8_init(); g_sink = g_crc8[g_reg & 0xFFU]; return 0; }
