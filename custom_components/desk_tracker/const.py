"""Constants for Desk Tracker integration."""

DOMAIN = "desk_tracker"

CONF_ENTITY_ID = "entity_id"
CONF_POWER_THRESHOLD = "power_threshold"
CONF_DAILY_GOAL = "daily_goal"

DEFAULT_POWER_THRESHOLD = 0.5   # W — monitor "on" if above this
DEFAULT_DAILY_GOAL = 6.0        # hours/day target
