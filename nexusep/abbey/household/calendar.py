from typing import Any, Dict


def get_weekday_index(day: int, config: Dict[str, Any]) -> int:
    calendar_config = config.get("simulation_calendar", {})

    start_weekday = int(calendar_config.get("start_weekday", 0))

    return (start_weekday + int(day)) % 7


def get_day_type(day: int, config: Dict[str, Any]) -> str:
    calendar_config = config.get("simulation_calendar", {})

    holiday_days = set(
        int(value)
        for value in calendar_config.get("holiday_days", [])
    )

    if int(day) in holiday_days:
        return "holiday"

    weekday_index = get_weekday_index(day=day, config=config)

    weekend_days = set(
        int(value)
        for value in calendar_config.get("weekend_days", [5, 6])
    )

    if weekday_index in weekend_days:
        return "weekend"

    return "weekday"


def get_weekday_name(day: int, config: Dict[str, Any]) -> str:
    calendar_config = config.get("simulation_calendar", {})

    weekday_index = get_weekday_index(day=day, config=config)

    weekday_names = calendar_config.get("weekday_names", {})

    return str(
        weekday_names.get(
            str(weekday_index),
            weekday_index,
        )
    )