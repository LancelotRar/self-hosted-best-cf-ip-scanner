import ipaddress

from scanner.ippool import (
    commented_networks,
    count_addresses,
    merge_to_runs,
    parse_library,
    sample_representatives,
    subtract_runs,
    window_count,
)


def test_window_count_matches_sampled_representatives():
    """窗口计数必须与真实采样条数一致，否则面板显示的「参与探测」会和扫描器对不上。"""
    runs = merge_to_runs(
        [
            ipaddress.ip_network("104.16.0.0/24"),
            ipaddress.ip_network("104.16.1.0/24"),
            ipaddress.ip_network("104.16.8.0/25"),
            ipaddress.ip_network("104.16.9.5/32"),
        ]
    )
    for stride in (1, 2, 7, 256, 1024):
        samples = sample_representatives(runs, stride=stride, seed=7)
        assert window_count(runs, stride) == len(samples)


def test_commented_networks_only_counts_entry_like_comment_lines():
    text = (
        "# 104.22.0.0/24\n"
        "#104.22.1.0/24\n"
        "# --- 注释：104.23.0.0/16 实测无合格产出 ---\n"
        "# 1.1.1.1:8443\n"
        "104.16.0.0/24\n"
    )
    networks = commented_networks(text)
    assert [str(network) for network in networks] == [
        "104.22.0.0/24",
        "104.22.1.0/24",
        "1.1.1.1/32",
    ]
    assert count_addresses(merge_to_runs(networks)) == 256 + 256 + 1


def test_subtract_runs_carves_out_a_subset():
    """注释掉 /13 里的 /14，剩下的应该是 104.20.0.0/14。"""
    active = merge_to_runs([ipaddress.ip_network("104.16.0.0/13")])
    excluded = merge_to_runs([ipaddress.ip_network("104.16.0.0/14")])
    remaining = subtract_runs(active, excluded)
    assert remaining == [
        (int(ipaddress.ip_address("104.20.0.0")), int(ipaddress.ip_address("104.23.255.255")))
    ]
    assert count_addresses(remaining) == 262144


def test_subtract_runs_ignores_exclusions_outside_the_library():
    active = merge_to_runs([ipaddress.ip_network("104.16.0.0/24")])
    excluded = merge_to_runs([ipaddress.ip_network("1.1.1.0/24")])
    assert subtract_runs(active, excluded) == active


def test_subtract_runs_supports_multiple_holes():
    active = merge_to_runs([ipaddress.ip_network("10.0.0.0/24")])
    excluded = merge_to_runs(
        [ipaddress.ip_network("10.0.0.0/26"), ipaddress.ip_network("10.0.0.192/26")]
    )
    remaining = subtract_runs(active, excluded)
    assert [(start, end) for start, end in remaining] == [
        (int(ipaddress.ip_address("10.0.0.64")), int(ipaddress.ip_address("10.0.0.191")))
    ]


def test_parse_library_reads_text_and_reports_skipped_lines():
    """带端口的条目不属于采样池，计为跳过；其余非法行同样计入。"""
    networks, skipped = parse_library(
        "cidr\n104.16.0.0/24\n1.1.1.1:8443\nnot-an-ip\n"
    )
    assert [str(network) for network in networks] == ["104.16.0.0/24"]
    assert skipped == 2
