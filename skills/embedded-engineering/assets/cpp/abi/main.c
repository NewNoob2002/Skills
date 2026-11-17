#include "backlight.h"

/** @brief Exercise the shared C ABI on the host. No hardware or ownership. */
int
main (void)
{
    enum
    {
        MAX_PERCENT    = 100U,
        OVER_PERCENT   = 120U,
        NORMAL_PERCENT = 42U
    };
    return ((backlight_clamp(OVER_PERCENT) == MAX_PERCENT) && (backlight_clamp(0U) == 0U) &&
            (backlight_clamp(NORMAL_PERCENT) == NORMAL_PERCENT))
               ? 0
               : 1;
}
