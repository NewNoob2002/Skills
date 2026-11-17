#ifndef DISPLAY_UI_BRIGHTNESS_HPP
#define DISPLAY_UI_BRIGHTNESS_HPP

namespace display_ui {
class Brightness
{
  public:
    /// @brief Set the requested level. Thread context only; owns no resources.
    /// @param requestedLevel Desired percent; values above 100 are clamped.
    void setLevel(unsigned requestedLevel)
    {
        if (requestedLevel > kMaxLevel) {
            requestedLevel = kMaxLevel;
        }
        level_ = requestedLevel;
    }

  private:
    static constexpr unsigned kMaxLevel = 100;
    unsigned level_ = 0;
};
} // namespace display_ui

#endif
