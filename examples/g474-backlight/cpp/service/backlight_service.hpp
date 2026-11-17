#ifndef G474_BACKLIGHT_BACKLIGHT_SERVICE_HPP
#define G474_BACKLIGHT_BACKLIGHT_SERVICE_HPP

#include "port/brightness_port.hpp"

namespace display_ui {
class BacklightService
{
  public:
    /// @brief Bind a port which must outlive the service. No hardware access.
    /// @param port Borrowed adapter; no ownership transfer.
    explicit BacklightService(BrightnessPort& port) : port_(port)
    {
    }

    /// @brief Request brightness. Task context; externally serialized, not ISR-safe.
    /// @param percent Requested percent; values above 100 are rejected.
    /// @return kOutOfRange without I/O, or the adapter result.
    Status setLevel(unsigned percent)
    {
        if (percent > kMaxPercent) {
            return Status::kOutOfRange;
        }
        return port_.apply(percent);
    }

  private:
    static constexpr unsigned kMaxPercent = 100U;
    BrightnessPort& port_;
};
} // namespace display_ui

#endif
