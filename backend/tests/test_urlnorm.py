import pytest

from firefly.models import Platform
from firefly.services.urlnorm import (
    InvalidURL,
    detect_platform,
    extract_urls,
    normalize_url,
    threads_post_parts,
)


def test_strips_tracking_and_canonicalizes_threads_host():
    u = normalize_url("http://threads.net/@alice/post/ABC123?utm_source=x&igshid=y&fbclid=z#frag")
    assert u == "https://www.threads.com/@alice/post/ABC123"
    assert detect_platform(u) == Platform.threads
    assert threads_post_parts(u) == ("alice", "ABC123")


def test_keeps_meaningful_query_sorted():
    assert normalize_url("https://example.org/a?b=2&a=1&utm_medium=m") == "https://example.org/a?a=1&b=2"


def test_invalid():
    with pytest.raises(InvalidURL):
        normalize_url("   ")
    with pytest.raises(InvalidURL):
        normalize_url("ftp://x/y")


def test_extract_urls():
    assert extract_urls("看這個 https://www.threads.com/@a/post/X1 和 http://ex.org/p.") == ["https://www.threads.com/@a/post/X1", "http://ex.org/p"]
