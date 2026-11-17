#ifndef G474_BACKLIGHT_FAKE_PWM_ADAPTER_HPP
#define G474_BACKLIGHT_FAKE_PWM_ADAPTER_HPP

#include "port/brightness_port.hpp"

namespace display_ui {
class FakePwmAdapter final : public BrightnessPort
{
  public:
    /// @brief Record an apply request; host fake, no register access.
    /// @param percent Requested percent.
    /// @return kOk, or kIoError when failure was injected.
    Status apply(unsigned percent) override
    {
        ++calls_;
        if (fail_) {
            return Status::kIoError;
        }
        percent_ = percent;
        return Status::kOk;
    }

    /// @brief Inject the next adapter failure. Test context only.
    /// @param fail True to fail subsequent applies.
    void setFail(bool fail)
    {
        fail_ = fail;
    }

    /// @brief Number of apply calls. Test context only.
    /// @return Call count since construction.
    unsigned calls() const
    {
        return calls_;
    }

    /// @brief Last successfully applied percentage. Test context only.
    /// @return Last value accepted by the fake.
    unsigned percent() const
    {
        return percent_;
    }

  private:
    bool fail_ = false;
    unsigned calls_ = 0U;
    unsigned percent_ = 0U;
};
} // namespace display_ui

#endif
