#include "bench.h"
template <class Derived> class BusBase { public: uint32_t read_id() { return static_cast<Derived*>(this)->read(0x0FU); } };
class SpiBus : public BusBase<SpiBus> { public: uint32_t read(uint8_t reg) { g_reg = reg; return g_reg; } };
class I2cBus : public BusBase<I2cBus> { public: uint32_t read(uint8_t reg) { g_reg = reg | 0x100U; return g_reg + 1U; } };
constinit SpiBus g_spi; constinit I2cBus g_i2c;
volatile uint32_t g_pick;
int main() { g_sink = (g_pick == 0U) ? g_spi.read_id() : g_i2c.read_id(); return 0; }
