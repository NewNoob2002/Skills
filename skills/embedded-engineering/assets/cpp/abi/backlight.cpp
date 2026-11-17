#include "backlight.h"

#include <cstdint>

extern "C" std::uint32_t
backlight_clamp (std::uint32_t requestedPercent)
{
    constexpr std::uint32_t kMaxPercent = 100;
    if (requestedPercent > kMaxPercent)
    {
        return kMaxPercent;
    }
    return requestedPercent;
}
