from __future__ import annotations

import re
import unittest
from pathlib import Path

PACK = Path(__file__).resolve().parents[1]


class PackTests(unittest.TestCase):
    def test_required_files_exist(self) -> None:
        required = {
            "README.md",
            "SOURCE_MANIFEST.md",
            "install.sh",
            "chief-send.sh",
            "profile/RELAY_ONLY",
            "profile/config.yaml",
            "profile/envfile.py",
            "profile/upsert_env.py",
            "profile/chief_slack_post.py",
            "events-bridge/bridge_core.py",
            "events-bridge/server.py",
            "events-bridge/com.digitalmavericks.chief-slack-events.plist.template",
            "scripts/render_plist.py",
        }
        self.assertEqual({path for path in required if not (PACK / path).is_file()}, set())

    def test_public_pack_contains_no_probable_live_secret(self) -> None:
        prohibited = [
            re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
            re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
            re.compile(r"SLACK_(?:BOT_TOKEN|SIGNING_SECRET)\s*=\s*[^${<\n][^\n]+"),
        ]
        for path in PACK.rglob("*"):
            if not path.is_file() or path.suffix in {".pyc"}:
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in prohibited:
                with self.subTest(path=path, pattern=pattern.pattern):
                    self.assertIsNone(pattern.search(text))

    def test_no_llm_or_gateway_activation(self) -> None:
        installer = (PACK / "install.sh").read_text(encoding="utf-8")
        self.assertNotIn("gateway start", installer)
        self.assertNotIn("model.default", installer)
        config = (PACK / "profile/config.yaml").read_text(encoding="utf-8")
        self.assertNotRegex(config, r"(?m)^\s*(model|provider|fallback)\s*:")
        plist = (
            PACK
            / "events-bridge/com.digitalmavericks.chief-slack-events.plist.template"
        ).read_text(encoding="utf-8")
        self.assertNotRegex(plist.lower(), r"hermes.*gateway|openai|anthropic|model")
        self.assertIn("__PROFILE_HOME__/events-bridge/server.py", plist)

    def test_phase2_documents_required_slack_scope_and_canonical_channel(self) -> None:
        readme = (PACK / "README.md").read_text(encoding="utf-8")
        installer = (PACK / "install.sh").read_text(encoding="utf-8")
        self.assertIn("app_mentions:read", readme)
        self.assertIn("C0BL2AM4KCY", readme)
        self.assertIn('canonical_channel_id="C0BL2AM4KCY"', installer)


if __name__ == "__main__":
    unittest.main()
