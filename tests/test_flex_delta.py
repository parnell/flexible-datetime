from datetime import date, datetime, timedelta

import arrow
import pytest
from dateutil.relativedelta import relativedelta
from pydantic import BaseModel

from flexible_datetime import FlexDateTime, flex_datetime, flex_delta


def test_parse_combined_duration_string():
    delta = flex_delta("2w1d")
    assert delta.components["weeks"] == 2
    assert delta.components["days"] == 1
    assert str(delta) == "2w1d"


def test_parse_month_and_year_units():
    delta = flex_delta("1y2mo")
    assert delta.components["years"] == 1
    assert delta.components["months"] == 2
    assert str(delta) == "1y2mo"


def test_parse_from_dict_and_kwargs():
    assert flex_delta({"duration": "2w1d"}) == flex_delta("2w1d")
    assert flex_delta(weeks=2, days=1) == flex_delta("2w1d")


def test_to_timedelta_for_fixed_units():
    delta = flex_delta("2w1d3h15min")
    assert delta.to_timedelta() == timedelta(weeks=2, days=1, hours=3, minutes=15)


def test_to_timedelta_rejects_calendar_units():
    with pytest.raises(ValueError, match="years or months"):
        flex_delta("1mo").to_timedelta()


def test_to_relativedelta_for_calendar_units():
    delta = flex_delta("1y2mo3d")
    assert delta.to_relativedelta() == relativedelta(years=1, months=2, days=3)


def test_date_arithmetic_uses_relativedelta_semantics():
    start = date(2024, 1, 31)
    assert start + flex_delta("1mo") == date(2024, 2, 29)


def test_date_subtraction_uses_relativedelta_semantics():
    start = date(2024, 3, 31)
    assert start - flex_delta("1mo") == date(2024, 2, 29)


def test_datetime_arithmetic():
    start = datetime(2024, 1, 1, 8, 30, 0)
    result = start + flex_delta("2w1d")
    assert result == datetime(2024, 1, 16, 8, 30, 0)


def test_datetime_subtraction():
    start = datetime(2024, 1, 16, 8, 30, 0)
    result = start - flex_delta("2w1d")
    assert result == datetime(2024, 1, 1, 8, 30, 0)


def test_arrow_arithmetic():
    start = arrow.get("2024-01-01T08:30:00+00:00")
    result = start + flex_delta("1d")
    assert result == arrow.get("2024-01-02T08:30:00+00:00")


def test_arrow_subtraction():
    start = arrow.get("2024-01-02T08:30:00+00:00")
    result = start - flex_delta("1d")
    assert result == arrow.get("2024-01-01T08:30:00+00:00")


def test_flex_datetime_arithmetic_preserves_mask():
    start = flex_datetime("2024-01")
    result = start + flex_delta("1mo")
    assert isinstance(result, flex_datetime)
    assert result.dt.month == 2
    assert result.mask == start.mask


def test_flex_datetime_subtraction_preserves_mask():
    start = flex_datetime("2024-03")
    result = start - flex_delta("1mo")
    assert isinstance(result, flex_datetime)
    assert result.dt.month == 2
    assert result.mask == start.mask


def test_flex_datetime_model_arithmetic_preserves_mask():
    start = FlexDateTime("2024-01")
    result = start + flex_delta("1mo")
    assert isinstance(result, FlexDateTime)
    assert result.dt.month == 2
    assert result.mask == start.mask


def test_flex_datetime_model_subtraction_preserves_mask():
    start = FlexDateTime("2024-03")
    result = start - flex_delta("1mo")
    assert isinstance(result, FlexDateTime)
    assert result.dt.month == 2
    assert result.mask == start.mask


def test_m_means_minutes_and_mo_means_months():
    assert flex_delta("15m").components["minutes"] == 15
    assert flex_delta("2mo").components["months"] == 2
    assert str(flex_delta("15min")) == "15m"


def test_duration_addition_normalizes_fixed_units():
    result = flex_delta("1w") + flex_delta("7d")
    assert result == flex_delta("2w")


def test_duration_subtraction():
    result = flex_delta("2w1d") - flex_delta("1w")
    assert result == flex_delta("1w1d")


def test_constructor_accepts_timedelta():
    assert flex_delta(timedelta(days=15)) == flex_delta("2w1d")


def test_pydantic_validation():
    class M(BaseModel):
        delta: flex_delta

    model = M.model_validate({"delta": "2w1d"})
    assert model.delta == flex_delta("2w1d")
