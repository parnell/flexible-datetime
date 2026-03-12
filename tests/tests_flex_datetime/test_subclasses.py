import pytest

from flexible_datetime import (
    dict_datetime,
    iso_datetime,
    mask_datetime,
    short_datetime,
)


@pytest.fixture
def sample_datetime():
    return "2023-06-15T14:30:45"


@pytest.fixture
def partial_datetime():
    return "2023-06"


def test_dict_datetime_output(sample_datetime):
    ct = dict_datetime(sample_datetime)
    expected = {"year": 2023, "month": 6, "day": 15, "hour": 14, "minute": 30, "second": 45}
    assert ct.to_components() == expected


def test_minimal_time_output(sample_datetime):
    mt = short_datetime(sample_datetime)
    assert str(mt) == "2023-06-15T14:30:45"


def test_iso_datetime_output(sample_datetime):
    it = iso_datetime(sample_datetime)
    assert str(it) == "2023-06-15T14:30:45+00:00"


def test_mask_datetime_output(sample_datetime):
    mt = short_datetime(sample_datetime)
    expected = {"dt": "2023-06-15T14:30:45+00:00", "mask": "0000001"}
    assert mt.to_flex() == expected


def test_partial_dates():
    """Test how each format handles partial dates"""
    dt = "2023-06"

    # Component time should only include provided components
    ct = dict_datetime(dt)
    assert ct.to_components() == {"year": 2023, "month": 6}

    # Minimal time should show only provided components
    mt = short_datetime(dt)
    assert str(mt) == "2023-06"

    # ISO time shows full datetime
    it = iso_datetime(dt)
    assert str(it) == "2023-06-01T00:00:00+00:00"

    # Masked time shows full datetime with mask
    mt = mask_datetime(dt)
    expected = {"dt": "2023-06-01T00:00:00+00:00", "mask": "0011111"}
    assert mt.to_flex() == expected


def test_inheritance_features():
    """Test that the new classes inherit all flex_datetime features"""
    ct = dict_datetime("2023-06-15")

    # Test masking
    ct.apply_mask(day=True)
    assert ct.to_components() == {"year": 2023, "month": 6}

    # Test component access
    assert ct.year == 2023
    assert ct.month == 6

    # Test comparison with masked components
    ct1 = dict_datetime("2023-06-15")
    ct2 = dict_datetime("2023-06-20")
    ct1.apply_mask(day=True)
    ct2.apply_mask(day=True)
    assert ct1 == ct2


def test_format_override():
    """Test that we can still override the default format"""
    ct = dict_datetime("2023-06-15")

    # Default is components
    assert isinstance(ct.to_components(), dict)

    # Override to minimal
    assert ct.to_str("minimal_datetime") == "2023-06-15"

    # Override to ISO
    assert ct.to_str("datetime") == "2023-06-15T00:00:00+00:00"

    # Override to flex
    flex_output = ct.to_flex()
    assert isinstance(flex_output, dict)
    assert "dt" in flex_output
    assert "mask" in flex_output


if __name__ == "__main__":
    pytest.main(["-v", __file__])
