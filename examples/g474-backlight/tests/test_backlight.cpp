#include "adapter/fake_pwm_adapter.hpp"
#include "page/brightness_page.hpp"
#include "service/backlight_service.hpp"

#include <cstdio>

namespace {
int gFailures = 0;

void expect(bool condition, const char * message)
{
    if (!condition) {
        std::printf("FAIL: %s\n", message);
        ++gFailures;
    }
}
} // namespace

/// @brief Exercise range rejection, success, and adapter failure on the host.
int
main()
{
    display_ui::FakePwmAdapter pwm;
    display_ui::BacklightService service{pwm};
    display_ui::BrightnessPage page{service};

    expect(page.onUserSet(150U) == display_ui::Status::kOutOfRange, "range rejected");
    expect(pwm.calls() == 0U, "range rejection performs no I/O");
    expect(page.onUserSet(42U) == display_ui::Status::kOk, "valid value succeeds");
    expect(pwm.percent() == 42U, "adapter saw the value");
    pwm.setFail(true);
    expect(page.onUserSet(10U) == display_ui::Status::kIoError, "failure propagates");
    expect(page.lastStatus() == display_ui::Status::kIoError, "page keeps the error");
    return (gFailures == 0) ? 0 : 1;
}
