
test::
	pytest tests/test*.py
	pytest tests/tests_flexdatetime
	pytest tests/tests_flextime

format::
	toml-sort pyproject.toml

build:: format
	rm -rf dist/*
	uv build

publish:: build
	uv publish