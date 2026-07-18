from __future__ import annotations

from ..ui.score_icon import create_score_icon


def test_score_icon_renders_for_full_score_range(qapp):
    for score in (-10, 0, 50, 100, 150):
        pixmap = create_score_icon(score).pixmap(64, 64)
        assert not pixmap.isNull()
        assert pixmap.width() == 64
        assert pixmap.height() == 64
