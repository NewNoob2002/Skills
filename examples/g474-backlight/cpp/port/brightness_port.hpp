#ifndef G474_BACKLIGHT_BRIGHTNESS_PORT_HPP
#define G474_BACKLIGHT_BRIGHTNESS_PORT_HPP

namespace display_ui {
enum class Status { kOk, kOutOfRange, kIoError };

class BrightnessPort
{
  public:
    /// @brief Apply a percentage. Task context only; caller retains this port.
    /// @param percent Value in [0, 100].
    /// @return kOk or kIoError; failure leaves the previous hardware level.
    virtual Status apply(unsigned percent) = 0;

  protected:
    /// @brief End a statically owned port lifetime; no resource release here.
    ~BrightnessPort() = default;
};
} // namespace display_ui

#endif
