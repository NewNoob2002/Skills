#include "app_abi.h"

/** @brief Run the C entry point on the host. Owns no resources. */
int
main (void)
{
    return app_run();
}
