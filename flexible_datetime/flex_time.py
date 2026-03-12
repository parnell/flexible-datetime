from __future__ import annotations

import re
from datetime import datetime, time, timedelta
from enum import StrEnum
from functools import total_ordering
from typing import Any, ClassVar, TypeAlias

import arrow
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

from flexible_datetime._base import (
    binary_to_mask as _base_binary_to_mask,
)
from flexible_datetime._base import (
    mask_to_binary as _base_mask_to_binary,
)

FlextimeInput: TypeAlias = "str | int | time | datetime | arrow.Arrow | dict | flex_time | None"

TIME_MASK_FIELDS: tuple[str, ...] = ("hour", "minute", "second", "microsecond")


class OutputFormat(StrEnum):
    """
    Enum for the output formats of flex_time.

    short_time: Serialize as shortest possible time format.
        Examples: HH, HH:mm, HH:mm:ss

    time: Serialize as full time format.
        Example: HH:mm:ss

    mask: Serialize as JSON-compatible format.
        Example: {"time": "12:30:45", "mask": "000"}

    components: Serialize as JSON-compatible format with masked components.
        Example: {"hour": 12, "minute": 30, "second": 45}
    """

    short = "short"
    time = "time"
    mask = "mask"
    components = "components"


@total_ordering
class flex_time:
    _time_formats: ClassVar[dict[str, str]] = {
        "HH": "hour",
        "mm": "minute",
        "ss": "second",
        "S": "millisecond",
        "SS": "millisecond",
        "SSS": "millisecond",
        "SSSS": "millisecond",
        "SSSSS": "millisecond",
        "SSSSSS": "millisecond",
    }

    _mask_fields: ClassVar[tuple[str, ...]] = TIME_MASK_FIELDS

    _default_output_format: ClassVar[OutputFormat] = OutputFormat.short

    @classmethod
    def _resolve_input(
        cls,
        *args: FlextimeInput,
        hour: int | None = None,
        minute: int | None = None,
        second: int | None = None,
        microsecond: int | None = None,
        **kwargs: Any,
    ) -> tuple[time, dict]:
        """Resolve constructor arguments into a (time, mask) pair."""
        _default_mask = {"hour": False, "minute": False, "second": False, "microsecond": True}

        if args and args[0] is None:
            raise ValueError("Cannot parse None as a flex_time.")

        if args and all(isinstance(arg, int) for arg in args):
            if len(args) > 4:
                raise ValueError(
                    "No more than 4 time components (hour, minute, second, microsecond) can be specified"
                )
            time_args = list(args) + [0] * (4 - len(args))
            t_hour, t_minute, t_second, t_microsecond = time_args[:4]
            mask = {
                "hour": False,
                "minute": len(args) < 2,
                "second": len(args) < 3,
                "microsecond": True,
            }
            return time(t_hour, t_minute, t_second, t_microsecond), mask  # type: ignore

        if any(x is not None for x in [hour, minute, second, microsecond]):
            t = time(hour or 0, minute or 0, second or 0, microsecond or 0)
            mask = {
                "hour": hour is None,
                "minute": minute is None,
                "second": second is None,
                "microsecond": True,
            }
            return t, mask

        if args:
            val = args[0]
            if isinstance(val, dict):
                is_dict_format = any(k in val for k in cls._mask_fields)
                if "time" not in kwargs and is_dict_format:
                    return cls._components_from_dict(val)
                t_obj = cls._parse_time_str(val["time"])
                mask = dict(_default_mask)
                if "mask" in val and isinstance(val["mask"], dict):
                    mask = val["mask"]
                elif "mask" in val and isinstance(val["mask"], str):
                    mask = cls.binary_to_mask(val["mask"])
                return t_obj, mask
            if isinstance(val, str):
                return cls._components_from_str(val)
            if isinstance(val, flex_time):
                return val.time, val.mask
            if isinstance(val, time):
                return val, dict(_default_mask)
            if isinstance(val, datetime | arrow.Arrow):
                return arrow.get(val).time(), dict(_default_mask)
            raise ValueError(f"Unsupported input: {args}")

        if "time" in kwargs:
            if isinstance(kwargs["time"], str):
                t = cls._parse_time_str(kwargs["time"])
            else:
                t = kwargs["time"]
            mask = dict(_default_mask)
            if "mask" in kwargs:
                if isinstance(kwargs["mask"], dict):
                    mask = kwargs["mask"]
                elif isinstance(kwargs["mask"], str):
                    mask = cls.binary_to_mask(kwargs["mask"])
                else:
                    raise ValueError(f"Invalid mask: {kwargs['mask']}")
            return t, mask

        raise NotImplementedError(f"Unsupported input: {args} {kwargs}")

    def __init__(
        self,
        *args: FlextimeInput,
        hour: int | None = None,
        minute: int | None = None,
        second: int | None = None,
        microsecond: int | None = None,
        **kwargs: Any,
    ):
        self._output_format: OutputFormat | None = None
        self.time, self.mask = self._resolve_input(
            *args, hour=hour, minute=minute, second=second, microsecond=microsecond, **kwargs
        )

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        def flex_time_serialization(value: flex_time, _, info) -> str:
            return str(value)

        return core_schema.no_info_after_validator_function(
            function=cls.validate,
            schema=core_schema.union_schema([
                core_schema.str_schema(),
                core_schema.dict_schema(),
                core_schema.is_instance_schema(flex_time),
                core_schema.is_instance_schema(time),
                core_schema.is_instance_schema(arrow.Arrow),
                core_schema.is_instance_schema(cls),
            ]),
            serialization=core_schema.wrap_serializer_function_ser_schema(
                flex_time_serialization, info_arg=True
            ),
        )

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

    @staticmethod
    def _parse_natural_time_str(time_str: str) -> time | None:
        """
        Parse natural language time expressions into a time object.
        Returns None if the string isn't a recognized natural time expression.
        """
        time_str = time_str.lower().strip()

        natural_times = {
            "noon": time(12, 0, 0),
            "midday": time(12, 0, 0),
            "mid-day": time(12, 0, 0),
            "mid day": time(12, 0, 0),
            "midnight": time(0, 0, 0),
            "mid-night": time(0, 0, 0),
            "mid night": time(0, 0, 0),
            "12 noon": time(12, 0, 0),
            "12noon": time(12, 0, 0),
            "12 midnight": time(0, 0, 0),
            "12midnight": time(0, 0, 0),
        }

        return natural_times.get(time_str)

    @staticmethod
    def _parse_time_str(time_str: str) -> time:
        prefixes = ["at ", "before ", "after ", "by "]
        time_str = time_str.lower().strip()
        for prefix in prefixes:
            if time_str.startswith(prefix):
                time_str = time_str[len(prefix) :]
                break

        natural_time = flex_time._parse_natural_time_str(time_str)
        if natural_time is not None:
            return natural_time
        original_str = time_str

        time_str = re.sub(r"(?i)\s*([AP])(?:\.?M\.?)?", r" \1M", time_str)
        time_str = re.sub(r"(\d{1,2})\s*:\s*(\d{2})(?:\s*(AM|PM))?", r"\1:\2", time_str)
        time_str = time_str.strip(". ").upper()

        micro_match = re.search(r"\.(\d+)$", time_str)
        if micro_match and len(micro_match.group(1)) > 6:
            raise ValueError(f"Microseconds cannot exceed 6 digits: {original_str}")

        if re.match(r"^\d{1,2}$", time_str.strip()):
            time_str = f"{time_str}:00"

        formats = [
            # 12-hour formats
            "h:mm A",  # 5:30 PM
            "h:mm a",  # 5:30 pm
            "hh:mm a",  # 05:30 pm
            "h:mma",  # 5:30pm
            "h:mmA",  # 5:30PM
            "ha",  # 5pm
            "h a",  # 5 pm
            "h:mm:ss A",  # 5:30:45 PM
            "h:mm:ss a",  # 5:30:45 pm
            "hh:mm:ss a",  # 05:30:45 pm
            "hh:mm:ss A",  # 05:30:45 PM
            "h:mm:ssA",  # 5:30:45PM
            "h:mm:ssa",  # 5:30:45pm
            "hh:mm:ssa",  # 05:30:45pm
            "hh:mm:ssA",  # 05:30:45PM
            # 24-hour formats
            "H:mm",  # 17:30
            "HH:mm",  # 17:30
            "H:mm:ss",  # 17:30:45
            "HH:mm:ss",  # 17:30:45
            "HH:mm:ss.SSSSSS",  # 17:30:45.123456
            # European-style (period separator)
            "h.mm a",  # 5.30 pm
            "h.mma",  # 5.30pm
            "hh.mm.ss a",  # 05.30.45 pm
            "HH.mm.ss",  # 17.30.45
            "H.mm",  # 17.30
            "HH.mm",  # 17.30
            "HH.mm.ss.SSSSSS",  # 17.30.45.123456
        ]

        try:
            parsed_time = arrow.get(time_str, formats)
        except arrow.parser.ParserError:
            raise ValueError(f"Could not parse time string: {original_str} {time_str}")

        return time(
            parsed_time.hour, parsed_time.minute, parsed_time.second, parsed_time.microsecond
        )

    @classmethod
    def _components_from_str(cls, time_str: str) -> tuple[time, dict]:
        t = cls._parse_time_str(time_str)
        mask = {field: False for field in cls._mask_fields}
        mask["microsecond"] = True

        clean_str = time_str.lower()
        clean_str = re.sub(r"[ap]\.?m\.?", "", clean_str, flags=re.IGNORECASE)
        clean_str = clean_str.replace(".", ":")
        clean_str = re.sub(r"\s*:\s*", ":", clean_str)
        clean_str = clean_str.strip()

        meaningful_parts = []
        parts = clean_str.split(":")
        for part in parts:
            part = part.strip()
            if part and re.match(r"^\d+$", part):
                meaningful_parts.append(part)

        if len(meaningful_parts) <= 2:
            mask["second"] = True

        if t.microsecond > 0 and len(meaningful_parts) <= 3:
            mask["microsecond"] = True

        return t, mask

    @classmethod
    def _components_from_dict(cls, time_dict: dict) -> tuple[time, dict]:
        components = {
            "hour": 0,
            "minute": 0,
            "second": 0,
            "microsecond": 0,
        }
        mask = {k: True for k in cls._mask_fields}

        components.update(time_dict)

        for k in time_dict:
            mask[k] = False

        t = time(
            components["hour"],
            components["minute"],
            components["second"],
            components["microsecond"],
        )
        return t, mask

    @property
    def mask_str(self) -> str:
        return self.mask_to_binary(self.mask)

    @staticmethod
    def mask_to_binary(mask: dict) -> str:
        return _base_mask_to_binary(mask)

    @classmethod
    def binary_to_mask(cls, binary_str: str) -> dict:
        return _base_binary_to_mask(binary_str, cls._mask_fields)

    def to_short_time(self) -> str:
        parts = [f"{self.time.hour:02d}"]

        if not self.mask["minute"]:
            parts.append(f"{self.time.minute:02d}")

        if not self.mask["second"] and (not self.mask["minute"] or self.time.second != 0):
            parts.append(f"{self.time.second:02d}")

        if not self.mask["microsecond"] and self.time.microsecond:
            parts.append(f"{self.time.microsecond:06d}")

        return ":".join(parts)

    def to_str(self, output_format: OutputFormat | str | None = None) -> str:
        if isinstance(output_format, str):
            output_format = OutputFormat(output_format)
        output_format = output_format or self._output_format or self._default_output_format

        if output_format == OutputFormat.time:
            return self.time.strftime("%H:%M:%S")
        elif output_format == OutputFormat.short:
            return self.to_short_time()
        elif output_format == OutputFormat.components:
            return str(self.to_components())
        return str(self.to_flex())

    def to_components(self) -> dict[str, int]:
        component_json = {
            "hour": self.time.hour,
            "minute": self.time.minute,
            "second": self.time.second,
            "microsecond": self.time.microsecond,
        }
        return {k: v for k, v in component_json.items() if not self.mask.get(k, False)}

    def to_flex(self) -> dict[str, str]:
        return {"time": self.time.strftime("%H:%M:%S"), "mask": self.mask_to_binary(self.mask)}

    def to_time(self) -> time:
        return self.time

    def __str__(self) -> str:
        return self.to_str()

    def __repr__(self) -> str:
        return str(self)

    @property
    def hour(self) -> int:
        return self.time.hour

    @property
    def minute(self) -> int:
        return self.time.minute

    @property
    def second(self) -> int:
        return self.time.second

    def _ensure_compatible_mask(self, other: flex_time) -> None:
        self_unmasked = {k for k, v in self.mask.items() if not v}
        other_unmasked = {k for k, v in other.mask.items() if not v}

        if not (self_unmasked.issubset(other_unmasked) or other_unmasked.issubset(self_unmasked)):
            raise ValueError(
                f"Cannot compare flex_time instances with incompatible masks. "
                f"Unmasked components don't form a subset: {self.mask} vs {other.mask}"
            )

    def get_comparable_time(self) -> time:
        other_mask = getattr(self, "_comparison_mask", self.mask)
        return time(
            self.time.hour if not (self.mask["hour"] or other_mask["hour"]) else 0,
            self.time.minute if not (self.mask["minute"] or other_mask["minute"]) else 0,
            self.time.second if not (self.mask["second"] or other_mask["second"]) else 0,
            (
                self.time.microsecond
                if not (self.mask["microsecond"] or other_mask["microsecond"])
                else 0
            ),
        )

    @classmethod
    def validate(cls, value) -> flex_time:
        if isinstance(value, flex_time):
            return value
        return flex_time(value)

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    def __eq__(self, other) -> bool:
        if not isinstance(other, flex_time):
            return False
        self._ensure_compatible_mask(other)
        return self.get_comparable_time() == other.get_comparable_time()

    def __lt__(self, other) -> bool:
        if not isinstance(other, flex_time):
            return NotImplemented
        self._ensure_compatible_mask(other)
        return self.get_comparable_time() < other.get_comparable_time()

    def __sub__(self, other: flex_time) -> timedelta:
        if not isinstance(other, flex_time):
            return NotImplemented
        self._ensure_compatible_mask(other)
        t1 = self.get_comparable_time()
        t2 = other.get_comparable_time()
        return datetime.combine(datetime.min, t1) - datetime.combine(datetime.min, t2)

    def __add__(self, other: timedelta) -> flex_time:
        if not isinstance(other, timedelta):
            return NotImplemented
        dt = datetime.combine(datetime.min, self.time) + other
        result = flex_time(dt.time())
        result.mask = self.mask.copy()
        return result

    def __radd__(self, other: timedelta) -> flex_time:
        return self.__add__(other)

    def __rsub__(self, other) -> timedelta:
        return NotImplemented
