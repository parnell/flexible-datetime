import pytest

from flexible_datetime import FlexDateTime
from flexible_datetime.flexible_datetime import OutputFormat


@pytest.fixture
def fdt():
    return FlexDateTime("2000-01-02T12:34:56+00:00")


def test_minimal_datetime_ymd(fdt: FlexDateTime):
    fdt.use_only("year", "month", "day")
    fdt._output_format = OutputFormat.minimal_datetime

    assert str(fdt) == "2000-01-02"


def test_minimal_datetime_ym(fdt: FlexDateTime):
    fdt.use_only("year", "month")
    fdt._output_format = OutputFormat.minimal_datetime

    assert str(fdt) == "2000-01"


def test_datetime(fdt: FlexDateTime):
    fdt.use_only(["year", "month", "day"])
    fdt._output_format = OutputFormat.datetime

    assert str(fdt) == "2000-01-02T12:34:56+00:00"


def test_flex(fdt: FlexDateTime):
    fdt.use_only(["year", "month", "day"])
    fdt._output_format = OutputFormat.mask
    s = str(fdt.to_flex())

    assert str(fdt) == s


def test_components_ymd(fdt: FlexDateTime):
    fdt.use_only(["year", "month", "day"])
    fdt._output_format = OutputFormat.components
    d = {"year": 2000, "month": 1, "day": 2}
    assert fdt.to_components() == d
    assert str(fdt) == str(d)


if __name__ == "__main__":
    pytest.main([__file__])
