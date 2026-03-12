import pytest

from flexible_datetime import FDTOutputFormat, flex_datetime


@pytest.fixture
def fdt():
    return flex_datetime("2000-01-02T12:34:56+00:00")


def test_minimal_datetime_ymd(fdt: flex_datetime):
    fdt.use_only("year", "month", "day")
    fdt._output_format = FDTOutputFormat.minimal_datetime

    assert str(fdt) == "2000-01-02"


def test_minimal_datetime_ym(fdt: flex_datetime):
    fdt.use_only("year", "month")
    fdt._output_format = FDTOutputFormat.minimal_datetime

    assert str(fdt) == "2000-01"


def test_datetime(fdt: flex_datetime):
    fdt.use_only(["year", "month", "day"])
    fdt._output_format = FDTOutputFormat.datetime

    assert str(fdt) == "2000-01-02T12:34:56+00:00"


def test_flex(fdt: flex_datetime):
    fdt.use_only(["year", "month", "day"])
    fdt._output_format = FDTOutputFormat.mask
    s = str(fdt.to_flex())

    assert str(fdt) == s


def test_components_ymd(fdt: flex_datetime):
    fdt.use_only(["year", "month", "day"])
    fdt._output_format = FDTOutputFormat.components
    d = {"year": 2000, "month": 1, "day": 2}
    assert fdt.to_components() == d
    assert str(fdt) == str(d)


if __name__ == "__main__":
    pytest.main([__file__])
