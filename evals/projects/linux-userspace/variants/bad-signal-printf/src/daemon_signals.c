#include "daemon_signals.h"

#include <signal.h>
#include <stdio.h>
#include <string.h>

static volatile sig_atomic_t g_stop_requested = 0;

/* 信号处理函数只设置 sig_atomic_t 标志（LNXU-004）；退出动作在主循环中完成。 */
static void on_terminate(int sig)
{
    fprintf(stderr, "signal %d received, stopping\n", sig);
    g_stop_requested = 1;
}

int daemon_signals_install(void)
{
    struct sigaction sa;

    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = on_terminate;
    (void)sigemptyset(&sa.sa_mask);
    if (sigaction(SIGTERM, &sa, NULL) != 0) {
        return -1;
    }
    return sigaction(SIGINT, &sa, NULL);
}

int daemon_stop_requested(void)
{
    return g_stop_requested != 0;
}
