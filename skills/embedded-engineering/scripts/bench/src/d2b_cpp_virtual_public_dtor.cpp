#include "bench.h"
class Bus { public: virtual uint32_t read(uint8_t reg) = 0; public: virtual ~Bus() = default; };
class SpiBus final : public Bus { public: uint32_t read(uint8_t reg) override { g_reg = reg; return g_reg; } };
class I2cBus final : public Bus { public: uint32_t read(uint8_t reg) override { g_reg = reg | 0x100U; return g_reg + 1U; } };
class Sensor { public: constexpr explicit Sensor(Bus& bus) : bus_(bus) {} uint32_t read_id() { return bus_.read(0x0FU); } private: Bus& bus_; };
constinit SpiBus g_spi; constinit I2cBus g_i2c;
Bus* volatile gp_sel = &g_spi;
int main() { Sensor a(*gp_sel); g_sink = a.read_id(); gp_sel = &g_i2c; Sensor b(*gp_sel); g_sink = b.read_id(); return 0; }
