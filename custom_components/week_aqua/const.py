"""Constants for the Week Aqua integration."""

from typing import Final

DOMAIN: Final = "week_aqua"

CONF_KIND: Final = "kind"
CONF_RISK_ACCEPTED: Final = "risk_accepted"

# Seconds to keep an idle link open after the last command. Short enough to
# free proxy slots for the other devices, long enough to absorb slider drags.
DISCONNECT_DELAY: Final = 15.0
# Gap between consecutive frames; the official app waits 500 ms, the firmware
# is fine with less.
FRAME_GAP: Final = 0.15

# Daily clock re-sync (local time), staggered per device.
CLOCK_SYNC_HOUR: Final = 3
CLOCK_SYNC_MINUTE: Final = 7

SERVICE_SET_SCHEDULE: Final = "set_schedule"
SERVICE_CLEAR_SCHEDULE: Final = "clear_schedule"
ATTR_ON_TIME: Final = "on_time"
ATTR_OFF_TIME: Final = "off_time"
ATTR_RAMP: Final = "ramp"
