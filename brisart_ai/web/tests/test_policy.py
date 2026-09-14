"""Tests for brisart_ai/web/policy.py -- robots.txt + local/private-host safety policy."""
import unittest
from brisart_ai.web.policy import USER_AGENT, is_local_or_private_host, is_localhost


class TestIsLocalOrPrivateHost(unittest.TestCase):
    def test_localhost_string(self):
        self.assertTrue(is_local_or_private_host("localhost"))

    def test_localhost_suffix(self):
        self.assertTrue(is_local_or_private_host("myapp.localhost"))

    def test_local_suffix(self):
        self.assertTrue(is_local_or_private_host("printer.local"))

    def test_loopback_ipv4(self):
        self.assertTrue(is_local_or_private_host("127.0.0.1"))

    def test_private_ipv4_ranges(self):
        for ip in ("10.0.0.1", "172.16.0.1", "192.168.1.1"):
            self.assertTrue(is_local_or_private_host(ip), msg=f"{ip} should be private")

    def test_loopback_ipv6(self):
        self.assertTrue(is_local_or_private_host("::1"))

    def test_link_local_ipv4(self):
        self.assertTrue(is_local_or_private_host("169.254.1.1"))

    def test_public_hostname_is_not_local(self):
        self.assertFalse(is_local_or_private_host("example.com"))

    def test_public_ip_is_not_local(self):
        self.assertFalse(is_local_or_private_host("8.8.8.8"))

    def test_empty_hostname_treated_as_local(self):
        self.assertTrue(is_local_or_private_host(""))

    def test_bracketed_ipv6_literal(self):
        self.assertTrue(is_local_or_private_host("[::1]"))

    def test_is_localhost_alias_matches_is_local_or_private_host(self):
        self.assertEqual(is_localhost("127.0.0.1"), is_local_or_private_host("127.0.0.1"))
        self.assertEqual(is_localhost("example.com"), is_local_or_private_host("example.com"))


class TestUserAgent(unittest.TestCase):
    def test_user_agent_contains_brisartai(self):
        self.assertIn("BrisartAI", USER_AGENT)


if __name__ == "__main__":
    unittest.main()
