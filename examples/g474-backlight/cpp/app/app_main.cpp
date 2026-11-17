#include "app_abi.h"

#include "adapter/fake_pwm_adapter.hpp"
#include "page/brightness_page.hpp"
#include "service/backlight_service.hpp"

namespace {
display_ui::FakePwmAdapter gPwm{};
display_ui::BacklightService gService{gPwm};
display_ui::BrightnessPage gPage{gService};
} // namespace

// C ABI spelling follows the platform C rules.
// NOLINTBEGIN(readability-identifier-naming)
extern "C" int app_run(void)
{
    if (display_ui::Status::kOutOfRange != gPage.onUserSet(150U)) {
        return 1;
    }
    if (0U != gPwm.calls()) {
        return 2;
    }
    if (display_ui::Status::kOk != gPage.onUserSet(42U)) {
        return 3;
    }
    if (42U != gPwm.percent()) {
        return 4;
    }
    gPwm.setFail(true);
    if (display_ui::Status::kIoError != gPage.onUserSet(10U)) {
        return 5;
    }
    if (display_ui::Status::kIoError != gPage.lastStatus()) {
        return 6;
    }
    return 0;
}
// NOLINTEND(readability-identifier-naming)
