import json
from typing import Any, ClassVar

import arrow
from pydantic import (
    BaseModel,
    Field,
    PrivateAttr,
    field_serializer,
    field_validator,
    model_validator,
)

import flexible_datetime.pydantic_arrow  # noqa: F401
from flexible_datetime._base import DatetimeOutputFormat as OutputFormat
from flexible_datetime._base import FlexDateTimeMixin, binary_to_mask, default_mask, mask_to_binary


class FlexDateTime(FlexDateTimeMixin, BaseModel):
    dt: arrow.Arrow = Field(default_factory=arrow.utcnow)
    mask: dict = Field(default_factory=default_mask)

    _SHORT_DATETIME_FMT: ClassVar[str] = "YYYY-MM-DD HH:mm:ss"
    _BOUNDARY_RE: ClassVar[str] = r"^\D+|\D+$"
    _default_output_format: ClassVar[OutputFormat] = OutputFormat.minimal_datetime
    _output_format: OutputFormat = PrivateAttr(default=_default_output_format)

    def __init__(self, *args, **kwargs):
        if args and args[0] is None:
            raise ValueError("Cannot parse None as a FlexDateTime.")
        if not args and not kwargs:
            super().__init__(dt=arrow.utcnow())
        elif args:
            dt, mask = self._resolve_datetime_input(*args, **kwargs)
            super().__init__(dt=dt, mask=mask)
        else:
            super().__init__(**kwargs)

    @model_validator(mode="before")
    def custom_validate_before(cls, values):
        if not values or isinstance(values, dict):
            return values
        dt, mask = cls._resolve_datetime_input(values)
        return {"dt": dt, "mask": mask}

    def model_dump(self, *args, **kwargs) -> dict[str, Any]:
        if self._default_output_format == OutputFormat.datetime:
            return {"dt": str(self.dt)}
        return super().model_dump(*args, **kwargs)

    def model_dump_json(self, *args, **kwargs):
        if self._default_output_format == OutputFormat.datetime:
            return json.dumps({"dt": str(self.dt)})
        return super().model_dump_json(*args, **kwargs)

    @field_serializer("mask")
    def serialize_mask(self, mask: dict) -> str:
        return mask_to_binary(mask)

    @field_validator("mask", mode="before")
    def deserialize_mask(cls, value):
        if isinstance(value, str):
            return binary_to_mask(value)
        return value

    def to_str(self, output_fmt: str | None = None) -> str:
        return self.to_short_datetime(output_fmt)

    def __str__(self) -> str:
        if self._output_format == OutputFormat.datetime:
            return str(self.dt)
        elif self._output_format == OutputFormat.minimal_datetime:
            return self.to_short_datetime()
        elif self._output_format == OutputFormat.components:
            return str(self.to_components())
        return str(self.to_flex())

    def __repr__(self) -> str:
        return self.model_dump_json()
