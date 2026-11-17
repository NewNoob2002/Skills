#ifndef G474_BACKLIGHT_APP_ABI_H
#define G474_BACKLIGHT_APP_ABI_H

#ifdef __cplusplus
extern "C"
{
#endif

    /**
     * @brief Run the host-visible backlight demo. Owns no resources.
     * @return 0 when all demo steps match; nonzero on the first failed step.
     * Cannot fail from I/O on the host; no ISR or thread context.
     */
    // C ABI spelling follows the platform C rules.
    // NOLINTNEXTLINE(readability-identifier-naming)
    int app_run (void);

#ifdef __cplusplus
}
#endif

#endif
