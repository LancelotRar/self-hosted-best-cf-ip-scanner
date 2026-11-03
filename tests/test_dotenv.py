import pytest

from scanner.dotenv import DotenvError, parse_dotenv, quote_value


def test_parses_comments_quotes_and_inline_comments():
    text = """
# comment
PROBE_HOST=probe.example.com
CRON_SCHEDULE=30 */6 * * *
UA="Mozilla/5.0 # not comment"
TOKEN='a # b'
"""
    assert parse_dotenv(text) == {
        "PROBE_HOST": "probe.example.com",
        "CRON_SCHEDULE": "30 */6 * * *",
        "UA": "Mozilla/5.0 # not comment",
        "TOKEN": "a # b",
    }


def test_duplicate_key_last_wins_and_crlf_is_handled():
    assert parse_dotenv("A=1\r\nA=2\r\n") == {"A": "2"}


@pytest.mark.parametrize("text", ["A=${B}", 'A="${B}"', "export A=1", "A='x\ny'"])
def test_rejects_unsupported_syntax(text):
    with pytest.raises(DotenvError):
        parse_dotenv(text)


def test_quote_value_roundtrip():
    for value in ["plain", "30 */6 * * *", "a # b", "it's ok", ""]:
        assert parse_dotenv(f"K={quote_value(value)}")["K"] == value
