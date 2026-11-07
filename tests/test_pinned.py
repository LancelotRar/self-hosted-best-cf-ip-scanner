from scanner.outputs import generate_subscriptions, write_pinned_list
from scanner.pinned import format_line, parse_line, parse_pinned, pinned_errors


def test_parse_line_defaults_port_and_keeps_label():
    assert parse_line("1.2.3.4") == ("1.2.3.4", 443, "")
    assert parse_line("1.2.3.4:8443#手动添加") == ("1.2.3.4", 8443, "手动添加")
    assert parse_line("  1.2.3.4:2053  #  备注  ") == ("1.2.3.4", 2053, "备注")


def test_parse_line_rejects_bad_input():
    assert parse_line("") is None
    assert parse_line("# 注释") is None
    assert parse_line("not-an-ip") is None
    assert parse_line("1.2.3.4:70000") is None
    assert parse_line("1.2.3.4:abc") is None
    assert parse_line("2001:db8::1") is None


def test_parse_pinned_dedupes_same_ip_and_port():
    entries, skipped = parse_pinned(
        "1.2.3.4:443#a\n1.2.3.4:443#b\n1.2.3.4:8443\nbad\n"
    )
    assert entries == [
        ("1.2.3.4", 443, "a"),
        ("1.2.3.4", 8443, ""),
    ]
    assert skipped == 1


def test_pinned_errors_report_line_numbers():
    assert pinned_errors("1.2.3.4:443\nbad\n") == [(2, "bad")]


def test_format_line_omits_hash_without_label():
    assert format_line(("1.2.3.4", 443, "手动")) == "1.2.3.4:443#手动"
    assert format_line(("1.2.3.4", 443, "")) == "1.2.3.4:443"


def _detail_csv(tmp_path):
    path = tmp_path / "detail.csv"
    path.write_text(
        "IP,端口,TCP握手平均延迟(ms),TCP握手丢包率,国家代码,国旗,边缘机房代码\n"
        "1.2.3.4,443,10.0,0.00,US,🇺🇸,LAX\n",
        encoding="utf-8",
    )
    return path


def test_pinned_list_is_written_to_its_own_file(tmp_path):
    name = write_pinned_list(tmp_path, "PINNED", ["9.9.9.9:443#手动", "8.8.8.8:443"])
    assert name == "PINNED.txt"
    lines = (tmp_path / "PINNED.txt").read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("# 2 条")
    assert lines[1:] == ["9.9.9.9:443#手动", "8.8.8.8:443"]


def test_pinned_list_accepts_custom_name_with_extension(tmp_path):
    assert write_pinned_list(tmp_path, "my-fixed.txt", ["1.2.3.4:443"]) == "my-fixed.txt"
    assert (tmp_path / "my-fixed.txt").is_file()


def test_empty_pinned_list_removes_stale_file(tmp_path):
    write_pinned_list(tmp_path, "PINNED", ["1.2.3.4:443"])
    assert write_pinned_list(tmp_path, "PINNED", []) is None
    assert not (tmp_path / "PINNED.txt").exists()


def test_pinned_file_is_separate_from_subscription_lists(tmp_path):
    generate_subscriptions(
        _detail_csv(tmp_path), tmp_path, overall_tops=(1,), country_enabled=False
    )
    write_pinned_list(tmp_path, "PINNED", ["9.9.9.9:443#手动"])

    global_text = (tmp_path / "GLOBAL1.txt").read_text(encoding="utf-8")
    assert "9.9.9.9" not in global_text
    assert "9.9.9.9:443#手动" in (tmp_path / "PINNED.txt").read_text(encoding="utf-8")
