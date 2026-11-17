#ifndef G474_BACKLIGHT_BRIGHTNESS_PAGE_HPP
#define G474_BACKLIGHT_BRIGHTNESS_PAGE_HPP

#include "service/backlight_service.hpp"

namespace display_ui {
class BrightnessPage
{
  public:
    /// @brief Bind the page to a service which must outlive it.
    /// @param service Borrowed business service; no ownership transfer.
    explicit BrightnessPage(BacklightService& service) : service_(service)
    {
    }

    /// @brief Apply a user request. UI context only; no register access.
    /// @param percent Requested percent.
    /// @return Status returned by the service.
    Status onUserSet(unsigned percent)
    {
        lastStatus_ = service_.setLevel(percent);
        return lastStatus_;
    }

    /// @brief Last status shown by the page. UI context only.
    /// @return Most recent service result.
    Status lastStatus() const
    {
        return lastStatus_;
    }

  private:
    BacklightService& service_;
    Status lastStatus_ = Status::kOk;
};
} // namespace display_ui

#endif
