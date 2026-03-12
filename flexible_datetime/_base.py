import re
from datetime import date, datetime
from enum import StrEnum
from functools import total_ordering
from typing import ClassVar

import arrow
from dateutil import parser as date_parser

from flexible_datetime.time_utils import infer_time_format

MASK_FIELDS: tuple[str, ...] = (
    "year",
    "month",
    "day",
    "hour",
    "minute",
    "second",
    "millisecond",
)

DT_FORMATS: dict[str, str] = {
    "YYYY": "year",
    "MM": "month",
    "DD": "day",
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


class DatetimeOutputFormat(StrEnum):
    """Output format for flex_datetime / FlexDateTime serialization.

    minimal_datetime: Shortest possible datetime format.
        Examples: YYYY, YYYY-MM, YYYY-MM-DD, YYYY-MM-DD HH:mm:ss

    datetime: Full datetime format.
        Example: YYYY-MM-DD HH:mm:ss

    mask: Dict with datetime string and binary mask.
        Example: {"dt": "2023-06-29T12:30:45+00:00", "mask": "0011111"}

    components: Dict with individual component values.
        Example: {"year": 2023, "month": 6, "day": 29}
    """

    minimal_datetime = "minimal_datetime"
    datetime = "datetime"
    mask = "mask"
    components = "components"


def default_mask(all_masked: bool = False) -> dict[str, bool]:
    return {field: all_masked for field in MASK_FIELDS}


def mask_to_binary(mask: dict, fields: tuple[str, ...] | None = None) -> str:
    keys = fields if fields is not None else mask.keys()
    return "".join("1" if mask[field] else "0" for field in keys)


def binary_to_mask(binary_str: str, fields: tuple[str, ...] = MASK_FIELDS) -> dict[str, bool]:
    padded = binary_str.ljust(len(fields), "1")
    return {field: bool(int(bit)) for field, bit in zip(fields, padded)}


@total_ordering
class FlexDateTimeMixin:
    """Shared logic for flex_datetime and FlexDateTime.

    Subclasses must provide:
      - self.dt: arrow.Arrow
      - self.mask: dict[str, bool]
    """

    _SHORT_DATETIME_FMT: ClassVar[str] = "YYYY-MM-DDTHH:mm:ss.SSSSSS"
    _BOUNDARY_RE: ClassVar[str] = r"^[^\d+-]+|[^\d+-]+$"

    # --- Static / class helpers ---

    @staticmethod
    def infer_format(date_str: str) -> str:
        return infer_time_format(date_str)

    @staticmethod
    def mask_to_binary(mask: dict) -> str:
        return mask_to_binary(mask)

    @staticmethod
    def binary_to_mask(binary_str: str) -> dict[str, bool]:
        return binary_to_mask(binary_str)

    @classmethod
    def _parse_date_or_datetime(cls, s):
        time_pattern = re.compile(r"(\d:\d|am|pm|midnight|noon|\bat\s*\d)", re.IGNORECASE)
        has_time = bool(time_pattern.search(s))
        dt = date_parser.parse(s, fuzzy=True)
        if dt.year == 1900:
            dt = dt.replace(year=datetime.now().year)
        return dt if has_time else dt.date()

    @classmethod
    def _components_from_str(cls, date_str: str, input_fmt: str | None = None) -> tuple:
        try:
            dt = arrow.get(date_str, input_fmt) if input_fmt else arrow.get(date_str)
        except (arrow.parser.ParserError, ValueError):
            try:
                date_time = cls._parse_date_or_datetime(date_str)
                if isinstance(date_time, datetime):
                    ft = cls(date_time)
                    return ft.dt, ft.mask
                else:
                    ft = cls(date_time)
                    return ft.dt, binary_to_mask("0001111")
            except ValueError:
                raise ValueError(f"Invalid date string: {date_str}")

        mask = default_mask()
        input_fmt = input_fmt or cls.infer_format(date_str)

        provided_parts = set()
        for fmt, field in DT_FORMATS.items():
            if fmt in input_fmt:
                provided_parts.add(field)

        for part in MASK_FIELDS:
            mask[part] = part not in provided_parts

        return dt, mask

    @classmethod
    def _components_from_dict(cls, datetime_dict):
        datetime_dict = dict(datetime_dict)
        components = {
            "year": 1970,
            "month": 1,
            "day": 1,
            "hour": 0,
            "minute": 0,
            "second": 0,
            "microsecond": 0,
            "tzinfo": "UTC",
        }
        mask = default_mask(all_masked=True)

        if "millisecond" in datetime_dict:
            datetime_dict["microsecond"] = datetime_dict.pop("millisecond") * 1000

        components.update(datetime_dict)

        for k in datetime_dict:
            if k in mask:
                mask[k] = False

        if "microsecond" in datetime_dict:
            mask["millisecond"] = False

        dt = arrow.Arrow(**components)
        return dt, mask

    @classmethod
    def _resolve_datetime_input(cls, *args, **kwargs) -> tuple:
        """Resolve constructor arguments into an (Arrow, mask) pair."""
        if args:
            val = args[0]
            if val is None:
                raise ValueError("Cannot parse None.")
            if isinstance(val, dict):
                is_component = any(k in val for k in MASK_FIELDS)
                if "dt" not in kwargs and is_component:
                    return cls._components_from_dict(val)
                dt = arrow.get(val["dt"])
                mask = default_mask()
                if "mask" in val:
                    if isinstance(val["mask"], dict):
                        mask = val["mask"]
                    elif isinstance(val["mask"], str):
                        mask = binary_to_mask(val["mask"])
                return dt, mask
            if isinstance(val, str):
                return cls._components_from_str(val)
            if isinstance(val, FlexDateTimeMixin):
                return val.dt, val.mask
            if isinstance(val, datetime | arrow.Arrow):
                return arrow.get(val), default_mask()
            if isinstance(val, date):
                mask = default_mask()
                mask.update({"hour": True, "minute": True, "second": True, "millisecond": True})
                return arrow.get(val), mask
            raise ValueError(f"Unsupported input: {val}")

        if "dt" in kwargs:
            dt = arrow.get(kwargs["dt"])
            mask = default_mask()
            if "mask" in kwargs:
                if isinstance(kwargs["mask"], dict):
                    mask = kwargs["mask"]
                elif isinstance(kwargs["mask"], str):
                    mask = binary_to_mask(kwargs["mask"])
                else:
                    raise ValueError(f"Invalid mask: {kwargs['mask']}")
            return dt, mask

        raise NotImplementedError(f"Unsupported input: {args} {kwargs}")

    @classmethod
    def from_str(cls, date_str: str, input_fmt: str | None = None):
        dt, mask = cls._components_from_str(date_str, input_fmt)
        return cls(dt=dt, mask=mask)

    @classmethod
    def from_datetime(cls, dt: datetime | date):
        return cls(dt=dt)

    @classmethod
    def from_dict(cls, datetime_dict):
        dt, mask = cls._components_from_dict(datetime_dict)
        return cls(dt=dt, mask=mask)

    # --- Mask manipulation ---

    def apply_mask(self, **kwargs) -> None:
        self.mask.update(kwargs)

    def clear_mask(self) -> None:
        self.mask = default_mask()

    def use_only(self, *args, **kwargs) -> None:
        self.clear_mask()
        nargs = args[0] if args and isinstance(args[0], list) else args
        keep = {k: True for k in nargs}
        keep.update(kwargs)
        for k in self.mask:
            if k not in keep:
                self.mask[k] = True

    def toggle_mask(self, **kwargs) -> None:
        for key in kwargs:
            self.mask[key] = not self.mask[key]

    # --- Properties ---

    @property
    def year(self):
        return self.dt.year

    @property
    def month(self):
        return self.dt.month

    @property
    def day(self):
        return self.dt.day

    @property
    def hour(self):
        return self.dt.hour

    @property
    def minute(self):
        return self.dt.minute

    @property
    def second(self):
        return self.dt.second

    @property
    def millisecond(self):
        return self.dt.microsecond // 1000

    @property
    def microsecond(self):
        return self.dt.microsecond

    @property
    def mask_str(self) -> str:
        return mask_to_binary(self.mask)

    # --- Comparison ---

    def get_comparable_dt(self) -> arrow.Arrow:
        return arrow.get(
            self.dt.year if not self.mask["year"] else 1,
            self.dt.month if not self.mask["month"] else 1,
            self.dt.day if not self.mask["day"] else 1,
            self.dt.hour if not self.mask["hour"] else 0,
            self.dt.minute if not self.mask["minute"] else 0,
            self.dt.second if not self.mask["second"] else 0,
        )

    def _ensure_same_mask(self, other) -> None:
        if self.mask != other.mask:
            raise ValueError(
                f"Cannot compare instances with different masks. {self.mask} != {other.mask}"
            )

    def eq(self, other, allow_different_masks: bool = False) -> bool:
        if not isinstance(other, FlexDateTimeMixin):
            return False
        if not allow_different_masks:
            self._ensure_same_mask(other)
        return self.get_comparable_dt() == other.get_comparable_dt()

    def __eq__(self, other) -> bool:
        if not isinstance(other, FlexDateTimeMixin):
            return False
        self._ensure_same_mask(other)
        return self.get_comparable_dt() == other.get_comparable_dt()

    def __lt__(self, other) -> bool:
        if not isinstance(other, FlexDateTimeMixin):
            return NotImplemented
        self._ensure_same_mask(other)
        return self.get_comparable_dt() < other.get_comparable_dt()

    # --- Output ---

    def to_short_datetime(self, output_fmt: str | None = None) -> str:
        if not self.dt:
            return "Invalid datetime"

        output_str = output_fmt or self._SHORT_DATETIME_FMT

        for fmt, part in DT_FORMATS.items():
            if part == "millisecond":
                microseconds = self.dt.microsecond
                if "SSSSSS" in output_str:
                    replacement = f"{microseconds:06d}"
                elif "SSSSS" in output_str:
                    replacement = f"{microseconds:06d}"[:5]
                elif "SSSS" in output_str:
                    replacement = f"{microseconds:06d}"[:4]
                elif "SSS" in output_str:
                    replacement = f"{microseconds:06d}"[:3]
                elif "SS" in output_str:
                    replacement = f"{microseconds // 1000:03d}"[:2]
                elif "S" in output_str:
                    replacement = f"{microseconds // 1000:03d}"[:1]
                else:
                    replacement = ""
                if self.mask[part]:
                    replacement = ""
                output_str = re.sub(r"S{1,6}", replacement, output_str)
            else:
                value = getattr(self.dt, part)
                replacement = (
                    f"{value:02d}" if fmt in ("MM", "DD", "HH", "mm", "ss") else str(value)
                )
                replacement = replacement if not self.mask[part] else ""
                output_str = output_str.replace(fmt, replacement)

        output_str = re.sub(r"(?<=\d)(\s|-|:|T)(?=\d)", r"\1", output_str)
        output_str = re.sub(r"\s+", " ", output_str).strip()
        output_str = re.sub(r"-+", "-", output_str)
        output_str = re.sub(r":+", ":", output_str)
        output_str = re.sub(self._BOUNDARY_RE, "", output_str)
        output_str = re.sub(r"\.$", "", output_str)
        output_str = re.sub(r"[-:]\s*$", "", output_str)
        return output_str

    # Alias for backward compatibility
    to_minimal_datetime = to_short_datetime

    def to_components(self) -> dict[str, int]:
        component_json = {
            "year": self.dt.year,
            "month": self.dt.month,
            "day": self.dt.day,
            "hour": self.dt.hour,
            "minute": self.dt.minute,
            "second": self.dt.second,
            "millisecond": self.dt.microsecond // 1000,
        }
        return {k: v for k, v in component_json.items() if not self.mask.get(k, False)}

    def to_flex(self) -> dict[str, str]:
        return {"dt": str(self.dt), "mask": mask_to_binary(self.mask)}

    def to_mask(self) -> dict[str, str]:
        return self.to_flex()

    def to_datetime(self) -> datetime:
        return self.dt.datetime
