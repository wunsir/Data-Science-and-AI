from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WEBSITE = REPO_ROOT / "website"


class WebsiteStructureTests(unittest.TestCase):
    def test_three_page_structure_and_particle_home_exist(self) -> None:
        index = (WEBSITE / "index.html").read_text(encoding="utf-8")
        macro = (WEBSITE / "macro.html").read_text(encoding="utf-8")
        micro = (WEBSITE / "micro.html").read_text(encoding="utf-8")
        story = (WEBSITE / "js" / "story-data.js").read_text(encoding="utf-8")

        self.assertIn('id="particle-canvas"', index)
        self.assertIn('href: "./macro.html"', story)
        self.assertIn('href: "./micro.html"', story)
        self.assertIn('data-page="macro"', macro)
        self.assertIn('data-page="micro"', micro)
        self.assertIn("./js/story-app.js", macro)
        self.assertIn("./js/story-app.js", micro)

    def test_historical_agent_overlay_is_shared_without_agent_charts(self) -> None:
        pages = [
            (WEBSITE / name).read_text(encoding="utf-8")
            for name in ("index.html", "macro.html", "micro.html")
        ]
        for page in pages:
            self.assertIn('class="agent-launcher"', page)
            self.assertIn('class="agent-panel"', page)

        app = (WEBSITE / "js" / "story-app.js").read_text(encoding="utf-8")
        self.assertIn('scope_override: "historical"', app)
        self.assertNotIn("agentResponse.chart", app)

    def test_story_registry_has_exactly_29_unique_figure_slots(self) -> None:
        story = (WEBSITE / "js" / "story-data.js").read_text(encoding="utf-8")
        image_ids = re.findall(r'^\s*image\("([^"]+)"', story, flags=re.MULTILINE)
        interactive_ids = re.findall(
            r'^\s*interactive\("([^"]+)"', story, flags=re.MULTILINE
        )

        self.assertEqual(len(image_ids), 21)
        self.assertEqual(len(interactive_ids), 8)
        self.assertEqual(len(set(image_ids + interactive_ids)), 29)

    def test_runtime_assets_are_local_and_pinned(self) -> None:
        pages = [
            WEBSITE / "index.html",
            WEBSITE / "macro.html",
            WEBSITE / "micro.html",
            WEBSITE / "chart.html",
        ]
        external_runtime = re.compile(
            r'<(?:script|link|iframe)\b[^>]+(?:src|href)="https?://',
            flags=re.IGNORECASE,
        )
        for page in pages:
            self.assertIsNone(external_runtime.search(page.read_text(encoding="utf-8")))

        for asset in (
            "echarts.min.js",
            "echarts-gl.min.js",
            "echarts-wordcloud.min.js",
            "vue.esm-browser.prod.js",
        ):
            self.assertGreater((WEBSITE / "js" / "vendor" / asset).stat().st_size, 10_000)

    def test_retired_claims_do_not_reappear(self) -> None:
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                WEBSITE / "index.html",
                WEBSITE / "macro.html",
                WEBSITE / "micro.html",
                WEBSITE / "js" / "story-data.js",
            )
        )
        for phrase in (
            "PSM",
            "倾向得分匹配",
            "高薪模板",
            "AI筛选",
            "边际贡献",
            "因果证明",
            "时间趋势",
            "项目保留了",
        ):
            self.assertNotIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
