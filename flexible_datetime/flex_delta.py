from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Any, ClassVar, TypeAlias

import arrow
from dateutil.relativedelta import relativedelta
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

FlexDeltaInput: TypeAlias = (
    "str | Mapping[str, int | str] | timedelta | relativedelta | flex_delta | None"
)


class OutputFormat(StrEnum):
    short = "short"
    components = "components"


class flex_delta:
    _unit_order: ClassVar[tuple[str, ...]] = (
        "years",
        "months",
        "weeks",
        "days",
        "hours",
        "minutes",
        "seconds",
        "microseconds",
    )
    _short_unit_names: ClassVar[dict[str, str]] = {
        "years": "y",
        "months": "mo",
        "weeks": "w",
        "days": "d",
        "hours": "h",
        "minutes": "m",
        "seconds": "s",
        "microseconds": "us",
    }
    _unit_aliases: ClassVar[dict[str, str]] = {
        "y": "years",
        "yr": "years",
        "yrs": "years",
        "year": "years",
        "years": "years",
        "mo": "months",
        "mon": "months",
        "month": "months",
        "months": "months",
        "w": "weeks",
        "week": "weeks",
        "weeks": "weeks",
        "d": "days",
        "day": "days",
        "days": "days",
        "h": "hours",
        "hr": "hours",
        "hrs": "hours",
        "hour": "hours",
        "hours": "hours",
        "m": "minutes",
        "min": "minutes",
        "mins": "minutes",
        "minute": "minutes",
        "minutes": "minutes",
        "s": "seconds",
        "sec": "seconds",
        "secs": "seconds",
        "second": "seconds",
        "seconds": "seconds",
        "us": "microseconds",
        "microsecond": "microseconds",
        "microseconds": "microseconds",
    }
    _duration_pattern: ClassVar[re.Pattern[str]] = re.compile(r"([+-]?\d+)\s*([a-zA-Z]+)")
    _default_output_format: ClassVar[OutputFormat] = OutputFormat.short

    @classmethod
    def _zero_components(cls) -> dict[str, int]:
        return {unit: 0 for unit in cls._unit_order}

    @classmethod
    def _normalize_components(cls, components: dict[str, int]) -> dict[str, int]:
        normalized = cls._zero_components()
        normalized.update({
            unit: int(value) for unit, value in components.items() if unit in normalized
        })

        total_microseconds = (
            ((normalized["weeks"] * 7) + normalized["days"]) * 24 * 60 * 60
            + normalized["hours"] * 60 * 60
            + normalized["minutes"] * 60
            + normalized["seconds"]
        ) * 1_000_000 + normalized["microseconds"]

        fixed_sign = -1 if total_microseconds < 0 else 1
        remainder = abs(total_microseconds)

        days_total, remainder = divmod(remainder, 24 * 60 * 60 * 1_000_000)
        hours, remainder = divmod(remainder, 60 * 60 * 1_000_000)
        minutes, remainder = divmod(remainder, 60 * 1_000_000)
        seconds, microseconds = divmod(remainder, 1_000_000)
        weeks, days = divmod(days_total, 7)

        normalized["weeks"] = fixed_sign * int(weeks)
        normalized["days"] = fixed_sign * int(days)
        normalized["hours"] = fixed_sign * int(hours)
        normalized["minutes"] = fixed_sign * int(minutes)
        normalized["seconds"] = fixed_sign * int(seconds)
        normalized["microseconds"] = fixed_sign * int(microseconds)
        return normalized

    @classmethod
    def _canonical_unit(cls, unit: str) -> str:
        try:
            return cls._unit_aliases[unit.lower()]
        except KeyError as exc:
            raise ValueError(f"Unsupported duration unit: {unit}") from exc

    @classmethod
    def _components_from_str(cls, duration_str: str) -> dict[str, int]:
        cleaned = duration_str.strip().lower()
        if not cleaned:
            raise ValueError("Cannot parse an empty duration string.")

        components = cls._zero_components()
        position = 0
        found_match = False

        for match in cls._duration_pattern.finditer(cleaned):
            gap = cleaned[position : match.start()]
            if gap.strip(" ,"):
                raise ValueError(f"Could not parse duration string: {duration_str}")

            found_match = True
            value = int(match.group(1))
            unit = cls._canonical_unit(match.group(2))
            components[unit] += value
            position = match.end()

        if not found_match or cleaned[position:].strip(" ,"):
            raise ValueError(f"Could not parse duration string: {duration_str}")

        return cls._normalize_components(components)

    @classmethod
    def _components_from_dict(cls, duration_dict: Mapping[str, int | str]) -> dict[str, int]:
        if "duration" in duration_dict:
            duration = duration_dict["duration"]
            if not isinstance(duration, str):
                raise ValueError("The 'duration' field must be a string.")
            return cls._components_from_str(duration)

        components = cls._zero_components()
        for key, value in duration_dict.items():
            if not isinstance(value, int):
                raise ValueError(f"Duration component '{key}' must be an int.")
            components[cls._canonical_unit(key)] += value
        return cls._normalize_components(components)

    @classmethod
    def _components_from_timedelta(cls, delta: timedelta) -> dict[str, int]:
        total_microseconds = (
            delta.days * 24 * 60 * 60 * 1_000_000 + delta.seconds * 1_000_000 + delta.microseconds
        )
        return cls._normalize_components({"microseconds": total_microseconds})

    @classmethod
    def _components_from_relativedelta(cls, delta: relativedelta) -> dict[str, int]:
        return cls._normalize_components({
            "years": int(delta.years),
            "months": int(delta.months),
            "weeks": int(delta.weeks),
            "days": int(delta.days),
            "hours": int(delta.hours),
            "minutes": int(delta.minutes),
            "seconds": int(delta.seconds),
            "microseconds": int(delta.microseconds),
        })

    @classmethod
    def _resolve_input(cls, *args: FlexDeltaInput, **kwargs: Any) -> dict[str, int]:
        if args and args[0] is None:
            raise ValueError("Cannot parse None as a flex_delta.")

        if args:
            value = args[0]
            if isinstance(value, str):
                return cls._components_from_str(value)
            if isinstance(value, dict):
                return cls._components_from_dict(value)
            if isinstance(value, timedelta):
                return cls._components_from_timedelta(value)
            if isinstance(value, relativedelta):
                return cls._components_from_relativedelta(value)
            if isinstance(value, flex_delta):
                return dict(value.components)
            raise ValueError(f"Unsupported input: {value}")

        if kwargs:
            return cls._components_from_dict(kwargs)

        raise NotImplementedError(f"Unsupported input: {args} {kwargs}")

    def __init__(self, *args: FlexDeltaInput, **kwargs: Any):
        self._output_format: OutputFormat | None = None
        self.components = self._resolve_input(*args, **kwargs)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        def flex_delta_serialization(value: flex_delta, _, info) -> str:
            return str(value)

        return core_schema.no_info_after_validator_function(
            function=cls.validate,
            schema=core_schema.union_schema([
                core_schema.str_schema(),
                core_schema.dict_schema(),
                core_schema.is_instance_schema(timedelta),
                core_schema.is_instance_schema(relativedelta),
                core_schema.is_instance_schema(flex_delta),
                core_schema.is_instance_schema(cls),
            ]),
            serialization=core_schema.wrap_serializer_function_ser_schema(
                flex_delta_serialization, info_arg=True
            ),
        )

    @classmethod
    def validate(cls, value) -> flex_delta:
        if isinstance(value, flex_delta):
            return value
        return flex_delta(value)

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    def set_output_format(self, format: OutputFormat | str | None) -> None:
        if isinstance(format, str):
            format = OutputFormat(format)
        self._output_format = format

    @property
    def output_format(self) -> OutputFormat | None:
        return self._output_format

    @output_format.setter
    def output_format(self, format: OutputFormat | str) -> None:
        self.set_output_format(format)

    def to_short(self) -> str:
        parts = []
        for unit in self._unit_order:
            value = self.components[unit]
            if value:
                parts.append(f"{value}{self._short_unit_names[unit]}")
        return "".join(parts) or "0s"

    def to_components(self) -> dict[str, int]:
        visible = {unit: value for unit, value in self.components.items() if value}
        return visible or {"seconds": 0}

    def to_flex(self) -> dict[str, str]:
        return {"duration": self.to_short()}

    def to_str(self, output_format: OutputFormat | str | None = None) -> str:
        if isinstance(output_format, str):
            output_format = OutputFormat(output_format)
        output_format = output_format or self._output_format or self._default_output_format
        if output_format == OutputFormat.components:
            return str(self.to_components())
        return self.to_short()

    def to_timedelta(self) -> timedelta:
        if self.components["years"] or self.components["months"]:
            raise ValueError(
                "Cannot convert years or months to timedelta without a reference date."
            )
        return timedelta(
            weeks=self.components["weeks"],
            days=self.components["days"],
            hours=self.components["hours"],
            minutes=self.components["minutes"],
            seconds=self.components["seconds"],
            microseconds=self.components["microseconds"],
        )

    def to_relativedelta(self) -> relativedelta:
        return relativedelta(
            years=self.components["years"],
            months=self.components["months"],
            weeks=self.components["weeks"],
            days=self.components["days"],
            hours=self.components["hours"],
            minutes=self.components["minutes"],
            seconds=self.components["seconds"],
            microseconds=self.components["microseconds"],
        )

    def apply_to(self, value: date | datetime | arrow.Arrow | Any):
        delta = self.to_relativedelta()

        if isinstance(value, arrow.Arrow):
            return arrow.get(value.datetime + delta)

        if isinstance(value, datetime | date):
            return value + delta

        if hasattr(value, "dt") and hasattr(value, "mask"):
            shifted_dt = arrow.get(value.dt.datetime + delta)
            return value.__class__(dt=shifted_dt, mask=value.mask.copy())

        raise TypeError(f"Unsupported value for duration arithmetic: {type(value)!r}")

    def _combine(self, other: flex_delta, sign: int = 1) -> flex_delta:
        merged = {
            unit: self.components[unit] + sign * other.components[unit] for unit in self._unit_order
        }
        return flex_delta(merged)

    def __str__(self) -> str:
        return self.to_str()

    def __repr__(self) -> str:
        return str(self)

    def __eq__(self, other) -> bool:
        if not isinstance(other, flex_delta):
            return False
        return self.components == other.components

    def __add__(self, other):
        if isinstance(other, flex_delta):
            return self._combine(other)
        if isinstance(other, timedelta):
            return self._combine(flex_delta(other))
        if isinstance(other, relativedelta):
            return self._combine(flex_delta(other))
        return self.apply_to(other)

    def __radd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        if isinstance(other, flex_delta):
            return self._combine(other, sign=-1)
        if isinstance(other, timedelta):
            return self._combine(flex_delta(other), sign=-1)
        if isinstance(other, relativedelta):
            return self._combine(flex_delta(other), sign=-1)
        return NotImplemented

    def __rsub__(self, other):
        if isinstance(other, arrow.Arrow):
            return arrow.get(other.datetime - self.to_relativedelta())
        if isinstance(other, datetime | date):
            return other - self.to_relativedelta()
        if hasattr(other, "dt") and hasattr(other, "mask"):
            shifted_dt = arrow.get(other.dt.datetime - self.to_relativedelta())
            return other.__class__(dt=shifted_dt, mask=other.mask.copy())
        return NotImplemented
