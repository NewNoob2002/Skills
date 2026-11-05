#ifndef DAEMON_SIGNALS_H
#define DAEMON_SIGNALS_H

int daemon_signals_install(void);
int daemon_stop_requested(void);

#endif /* DAEMON_SIGNALS_H */
