import numpy as np
import cv2
from PyQt6.QtGui import QIcon, QPixmap, QImage

# Pre-compute constant geometry at import time — these never change between calls.
_SIZE = 64
_CENTER = _SIZE // 2
_RADIUS = 30
_OUTER = float(_RADIUS + 8)

_xs, _ys = np.meshgrid(np.arange(_SIZE), np.arange(_SIZE))
_dist = np.sqrt((_xs - _CENTER) ** 2 + (_ys - _CENTER) ** 2).astype(np.float32)
_glow_mask = _dist <= _OUTER
_hard_mask = _dist <= _RADIUS
_glow_alpha_base = np.where(
    _glow_mask,
    np.clip((1.0 - _dist / _OUTER) * ((_OUTER - _RADIUS) / 8.0) * 255, 0, 255),
    0,
).astype(np.uint8)
# Final alpha channel: full opacity inside hard circle, soft glow outside
_ALPHA_CHANNEL = np.where(_hard_mask, np.uint8(255), _glow_alpha_base).astype(np.uint8)


def create_score_icon(score: float) -> QIcon:
    """Create a 64×64 colour-coded circular tray icon displaying the posture score.

    Colour mapping: HSV hue 0 (red, score=0) → 60 (green, score=100).
    Renders a hard-edge circle with a soft outer glow ring, a layered drop-shadow,
    and white score text centred inside. Geometry arrays are pre-computed at module
    load time; only hue and text rendering vary per call.
    """
    img = np.zeros((_SIZE, _SIZE, 4), dtype=np.uint8)
    img[:, :, 3] = _ALPHA_CHANNEL

    # Hue 0 (red) → 60 (green) mapped from score 0–100
    hue = int(np.clip(score * 60 / 100, 0, 60))
    rgb_color = cv2.cvtColor(np.uint8([[[hue, 255, 255]]]), cv2.COLOR_HSV2BGR)[0][0]
    color = (int(rgb_color[0]), int(rgb_color[1]), int(rgb_color[2]), 255)

    font = cv2.FONT_HERSHEY_DUPLEX
    text = f"{int(score)}"
    font_scale = 2.0 if len(text) == 1 else (1.5 if len(text) == 2 else 1.2)
    thickness = 3
    text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
    text_x = (_SIZE - text_size[0]) // 2
    text_y = (_SIZE + text_size[1]) // 2

    temp = img.copy()
    for offset, alpha in zip([(2, 2), (1, 1)], [120, 180]):
        cv2.putText(
            temp,
            text,
            (text_x + offset[0], text_y + offset[1]),
            font,
            font_scale,
            (0, 0, 0, alpha),
            thickness,
        )
    cv2.putText(
        temp,
        text,
        (text_x - 1, text_y - 1),
        font,
        font_scale,
        (255, 255, 255, 100),
        thickness,
    )
    cv2.putText(temp, text, (text_x, text_y), font, font_scale, color, thickness)

    h, w, _ = temp.shape
    q_img = QImage(temp.data, w, h, 4 * w, QImage.Format.Format_RGBA8888)
    return QIcon(QPixmap.fromImage(q_img))
