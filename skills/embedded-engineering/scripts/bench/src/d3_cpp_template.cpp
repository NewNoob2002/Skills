#include "bench.h"
#include <concepts>
template <class T> concept RegisterBus = requires(T& b, uint8_t r) { { b.read(r) } -> std::same_as<uint32_t>; };
struct SpiBus { uint32_t read(uint8_t reg) { g_reg = reg; return g_reg; } };
struct I2cBus { uint32_t read(uint8_t reg) { g_reg = reg | 0x100U; return g_reg + 1U; } };
template <RegisterBus BusT> class Sensor { public: constexpr explicit Sensor(BusT& bus) : bus_(bus) {} uint32_t read_id() { return bus_.read(0x0FU); } private: BusT& bus_; };
constinit SpiBus g_spi; constinit I2cBus g_i2c;
volatile uint32_t g_pick;
int main() { if (g_pick == 0U) { Sensor s(g_spi); g_sink = s.read_id(); } else { Sensor s(g_i2c); g_sink = s.read_id(); } return 0; }
