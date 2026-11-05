#include "bench.h"
typedef struct { uint32_t (*p_read)(void * p_ctx, uint8_t reg); void * p_ctx; } bus_if_t;
static uint32_t spi_read(void * p_ctx, uint8_t reg) { (void)p_ctx; g_reg = reg; return g_reg; }
static uint32_t i2c_read(void * p_ctx, uint8_t reg) { (void)p_ctx; g_reg = (uint32_t)reg | 0x100U; return g_reg + 1U; }
static uint32_t sensor_read_id(bus_if_t const * p_bus) { return p_bus->p_read(p_bus->p_ctx, 0x0FU); }
static bus_if_t const g_spi = {spi_read, 0};
static bus_if_t const g_i2c = {i2c_read, 0};
bus_if_t const * volatile gp_sel = &g_spi; /* 运行期选择，阻止编译器常量折叠 */
int main(void) { g_sink = sensor_read_id(gp_sel); gp_sel = &g_i2c; g_sink = sensor_read_id(gp_sel); return 0; }
