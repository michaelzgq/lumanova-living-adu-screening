from __future__ import annotations

import unittest

from app.source_context import resolve_source_context


class SourceContextTests(unittest.TestCase):
    def test_explicit_query_params_override_header_inference(self) -> None:
        resolved = resolve_source_context(
            {
                "source": "wechat_sgv",
                "utm_medium": "social",
                "utm_campaign": "wave1",
            },
            {"User-Agent": "MicroMessenger"},
        )

        self.assertEqual(resolved["source_tag"], "wechat_sgv")
        self.assertEqual(resolved["utm_source"], "wechat_sgv")
        self.assertEqual(resolved["utm_medium"], "social")
        self.assertEqual(resolved["utm_campaign"], "wave1")

    def test_wechat_user_agent_infers_wechat(self) -> None:
        resolved = resolve_source_context({}, {"User-Agent": "Mozilla/5.0 MicroMessenger/8.0"})

        self.assertEqual(resolved["source_tag"], "wechat")
        self.assertEqual(resolved["utm_source"], "wechat")
        self.assertEqual(resolved["utm_medium"], "social")

    def test_xiaohongshu_referer_infers_xiaohongshu(self) -> None:
        resolved = resolve_source_context({}, {"Referer": "https://www.xiaohongshu.com/explore/abc"})

        self.assertEqual(resolved["source_tag"], "xiaohongshu")
        self.assertEqual(resolved["utm_source"], "xiaohongshu")
        self.assertEqual(resolved["utm_medium"], "social")

    def test_unknown_source_defaults_to_direct(self) -> None:
        resolved = resolve_source_context({}, {"User-Agent": "Mozilla/5.0 Safari"})

        self.assertEqual(resolved["source_tag"], "direct_or_unknown")
        self.assertEqual(resolved["utm_source"], "direct_or_unknown")
        self.assertEqual(resolved["utm_medium"], "direct")


if __name__ == "__main__":
    unittest.main()
