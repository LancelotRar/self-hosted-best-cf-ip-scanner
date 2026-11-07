import pytest

from scanner import config
from scanner.schema import BY_NAME, KNOWN_KEYS, PARAMS, coerce, format_value


def test_every_param_roundtrips_through_format_and_coerce():
    for spec in PARAMS:
        encoded = format_value(spec, spec.default)
        assert coerce(spec, encoded) == spec.default, spec.name


def test_scanner_params_are_exposed_on_config():
    for spec in PARAMS:
        if spec.consumer == "scanner":
            assert hasattr(config, spec.name), spec.name


def test_known_keys_is_exactly_the_schema():
    assert KNOWN_KEYS == frozenset(BY_NAME)


def test_names_are_unique():
    names = [spec.name for spec in PARAMS]
    assert len(names) == len(set(names))


@pytest.mark.parametrize(
    ("name", "raw"),
    [
        ("TCP_TIMEOUT", "abc"),
        ("PROBE_PORTS", "70000"),
        ("SKIP_LOCATIONS", "maybe"),
        ("SAMPLE_STRIDE", "1.5"),
    ],
)
def test_coerce_rejects_invalid_values(name, raw):
    with pytest.raises(ValueError):
        coerce(BY_NAME[name], raw)


def test_ports_coerce_returns_int_tuple():
    assert coerce(BY_NAME["PROBE_PORTS"], "443, 2053") == (443, 2053)
