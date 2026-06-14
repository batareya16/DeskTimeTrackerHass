"""Desk Tracker sensor — computes daily desk time from a power sensor via HA recorder."""
from __future__ import annotations

import logging
from datetime import datetime, time, timedelta
from functools import partial
from typing import Any

import homeassistant.util.dt as dt_util
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.storage import Store

from .const import (
    CONF_DAILY_GOAL,
    CONF_ENTITY_ID,
    CONF_POWER_THRESHOLD,
    DEFAULT_DAILY_GOAL,
    DEFAULT_POWER_THRESHOLD,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)

_STORAGE_VERSION = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Desk Tracker sensor."""
    data = entry.data
    async_add_entities(
        [
            DeskTrackerSensor(
                hass,
                entry.entry_id,
                entity_id=data[CONF_ENTITY_ID],
                threshold=float(data.get(CONF_POWER_THRESHOLD, DEFAULT_POWER_THRESHOLD)),
                daily_goal=float(data.get(CONF_DAILY_GOAL, DEFAULT_DAILY_GOAL)),
            )
        ],
        update_before_add=False,
    )


def _count_working_days(start_date, end_date) -> int:
    """Count Mon–Fri days between start_date and end_date (inclusive)."""
    count = 0
    d = start_date
    while d <= end_date:
        if d.weekday() < 5:
            count += 1
        d += timedelta(days=1)
    return count


class DeskTrackerSensor(SensorEntity):
    """Sensor tracking daily desk time."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "h"
    _attr_icon = "mdi:monitor"
    _attr_should_poll = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        entity_id: str,
        threshold: float,
        daily_goal: float,
    ) -> None:
        self.hass = hass
        self._entry_id = entry_id
        self._entity_id = entity_id
        self._threshold = threshold
        self._daily_goal = daily_goal

        self._attr_unique_id = f"{DOMAIN}_{entry_id}"
        self._attr_name = "Desk Tracker"

        # Persistent storage — survives recorder purges
        self._store: Store = Store(
            hass,
            _STORAGE_VERSION,
            f"{DOMAIN}_{entry_id}_daily_hours",
        )
        self._stored_hours: dict[str, float] = {}
        self._store_loaded: bool = False

        # Display state
        self._today_hours: float = 0.0
        self._week_days: list[dict] = []
        self._streak: int = 0
        self._month_hours: float = 0.0
        self._month_required: float = 0.0

    # ------------------------------------------------------------------ #
    #  Storage helpers                                                     #
    # ------------------------------------------------------------------ #

    async def _load_store(self) -> None:
        """Load persisted daily hours from HA storage (runs once)."""
        raw = await self._store.async_load()
        if raw and isinstance(raw.get("daily_hours"), dict):
            self._stored_hours = raw["daily_hours"]
            _LOGGER.debug("Desk Tracker: loaded %d stored days", len(self._stored_hours))
        self._store_loaded = True

    async def _save_store(self) -> None:
        """Persist current daily hours to HA storage."""
        await self._store.async_save({"daily_hours": self._stored_hours})

    # ------------------------------------------------------------------ #
    #  Recorder query                                                      #
    # ------------------------------------------------------------------ #

    async def _get_recorder_hours(self) -> dict[str, float]:
        """
        Query HA recorder for recent power sensor history.
        Returns {ISO-date: hours_at_desk} for whatever window the recorder holds.

        For each consecutive state pair: if power > threshold during that
        interval, count it as desk time (split across midnight if needed).
        """
        try:
            from homeassistant.components.recorder import get_instance
            from homeassistant.components.recorder.history import get_significant_states
        except ImportError:
            _LOGGER.error("Desk Tracker: recorder component not available")
            return {}

        today = dt_util.now().date()
        tz = dt_util.get_time_zone(self.hass.config.time_zone)

        # Ask for 60 days — recorder returns whatever it actually has
        start_dt = datetime.combine(today - timedelta(days=60), time.min).replace(tzinfo=tz)
        end_dt = datetime.combine(today, time.max).replace(tzinfo=tz)

        try:
            instance = get_instance(self.hass)
            states_dict = await instance.async_add_executor_job(
                partial(
                    get_significant_states,
                    self.hass,
                    start_dt,
                    end_dt,
                    [self._entity_id],
                    None,   # filters
                    True,   # include_start_time_state
                    False,  # significant_changes_only — capture every change
                    False,  # minimal_response
                    True,   # no_attributes — faster
                )
            )
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error("Desk Tracker: recorder query failed: %s", exc)
            return {}

        states = states_dict.get(self._entity_id, [])
        day_seconds: dict[str, float] = {}

        for i, state in enumerate(states):
            try:
                power = float(state.state)
            except (ValueError, TypeError):
                continue

            period_start = state.last_changed
            period_end = states[i + 1].last_changed if i + 1 < len(states) else dt_util.now()

            if power <= self._threshold:
                continue  # monitor was off

            # Split across day boundaries
            cursor = period_start
            while cursor < period_end:
                local_day = cursor.astimezone(tz).date()
                next_midnight = datetime.combine(
                    local_day + timedelta(days=1), time.min
                ).replace(tzinfo=tz)
                segment_end = min(period_end, next_midnight)
                seconds = (segment_end - cursor).total_seconds()
                key = local_day.isoformat()
                day_seconds[key] = day_seconds.get(key, 0.0) + seconds
                cursor = segment_end

        return {k: v / 3600.0 for k, v in day_seconds.items()}

    # ------------------------------------------------------------------ #
    #  Update                                                              #
    # ------------------------------------------------------------------ #

    async def async_update(self) -> None:
        """Refresh sensor state and attributes."""
        # Load storage on first run
        if not self._store_loaded:
            await self._load_store()

        try:
            recorder_hours = await self._get_recorder_hours()
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error("Desk Tracker: update error: %s", exc)
            recorder_hours = {}

        # Merge: stored data is the long-term base;
        # recorder overwrites it for the days it covers (fresher truth).
        # Today is always taken from recorder (or 0 if recorder empty).
        merged: dict[str, float] = dict(self._stored_hours)
        merged.update(recorder_hours)

        # Persist the merged result (prune entries older than 120 days to keep file small)
        today = dt_util.now().date()
        cutoff = (today - timedelta(days=60)).isoformat()
        self._stored_hours = {k: v for k, v in merged.items() if k >= cutoff}
        await self._save_store()

        day_hours = merged

        # ---- Today ----
        self._today_hours = round(day_hours.get(today.isoformat(), 0.0), 2)
        self._attr_native_value = self._today_hours

        # ---- Current week (Mon–Fri) ----
        week_start = today - timedelta(days=today.weekday())
        week_days = []
        for offset in range(5):
            d = week_start + timedelta(days=offset)
            h = round(day_hours.get(d.isoformat(), 0.0), 2)
            week_days.append(
                {
                    "date": d.isoformat(),
                    "weekday": d.strftime("%a"),
                    "hours": h,
                    "logged": h >= self._daily_goal,
                    "is_today": d == today,
                    "is_future": d > today,
                }
            )
        self._week_days = week_days

        # ---- Streak ----
        streak = 0
        check = today
        if self._today_hours < self._daily_goal and today.weekday() < 5:
            check = today - timedelta(days=1)
        while True:
            if check.weekday() >= 5:
                check -= timedelta(days=1)
                continue
            h = day_hours.get(check.isoformat(), 0.0)
            if h >= self._daily_goal:
                streak += 1
                check -= timedelta(days=1)
            else:
                break
        self._streak = streak

        # ---- Monthly stats ----
        month_start = today.replace(day=1)
        month_hours = sum(
            h for d_str, h in day_hours.items()
            if month_start.isoformat() <= d_str <= today.isoformat()
        )
        self._month_hours = round(month_hours, 2)
        working_days_so_far = _count_working_days(month_start, today)
        self._month_required = round(working_days_so_far * self._daily_goal, 1)

    # ------------------------------------------------------------------ #
    #  Attributes                                                          #
    # ------------------------------------------------------------------ #

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "friendly_name": self.name,
            "today_hours": self._today_hours,
            "today_logged": self._today_hours >= self._daily_goal,
            "week_days": self._week_days,
            "streak": self._streak,
            "month_hours": self._month_hours,
            "month_required": self._month_required,
            "daily_goal": self._daily_goal,
            "power_threshold": self._threshold,
            "source_entity": self._entity_id,
        }
