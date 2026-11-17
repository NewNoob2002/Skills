#ifndef PROJ_BACKLIGHT_H
#define PROJ_BACKLIGHT_H

#include <stdint.h>

#ifdef __cplusplus
extern "C"
{
#endif

    /**
     * @brief Clamp a requested brightness percentage. Pure function, ISR-safe.
     * @param requested_percent Requested percentage; values above 100 are
     * clamped.
     * @return A percentage in [0, 100]. Cannot fail. No ownership is
     * transferred.
     */
    // C ABI spelling follows the platform C rules.
    // NOLINTNEXTLINE(readability-identifier-naming)
    uint32_t backlight_clamp (uint32_t requested_percent);

#ifdef __cplusplus
}
#endif

#endif
