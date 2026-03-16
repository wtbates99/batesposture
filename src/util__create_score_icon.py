import numpy as np
import cv2
from PyQt6.QtGui import QIcon, QPixmap, QImage


def create_score_icon(score: float) -> QIcon:
    """Create a 64×64 colour-coded circular tray icon displaying the posture score.

    Colour mapping: HSV hue 0 (red, score=0) → 60 (green, score=100).
    Renders a hard-edge circle with a soft outer glow ring, a layered drop-shadow,
    and white score text centred inside. Uses vectorised NumPy coordinate grids
    and OpenCV putText rather than nested pixel loops for performance.
    """
    size = 64
    img = np.zeros((size, size, 4), dtype=np.uint8)

    center = size // 2
    radius = 30

    # Build coordinate grids once
    xs, ys = np.meshgrid(np.arange(size), np.arange(size))
    dist = np.sqrt((xs - center) ** 2 + (ys - center) ** 2).astype(np.float32)

    # Soft glow ring: blend alpha from outer edge to hard circle boundary
    outer = float(radius + 8)
    glow_mask = dist <= outer
    glow_alpha = np.where(
        glow_mask,
        np.clip((1.0 - dist / outer) * ((outer - radius) / 8.0) * 255, 0, 255),
        0,
    ).astype(np.uint8)

    # Hard circle keeps full opacity
    hard_mask = dist <= radius
    glow_alpha = np.where(hard_mask, 255, glow_alpha).astype(np.uint8)
    img[:, :, 3] = glow_alpha

    # Hue 0 (red) → 60 (green) mapped from score 0–100
    hue = int(np.clip(score * 60 / 100, 0, 60))
    rgb_color = cv2.cvtColor(np.uint8([[[hue, 255, 255]]]), cv2.COLOR_HSV2BGR)[0][0]
    color = (int(rgb_color[0]), int(rgb_color[1]), int(rgb_color[2]), 255)

    font = cv2.FONT_HERSHEY_DUPLEX
    text = f"{int(score)}"
    font_scale = 2.0 if len(text) == 1 else (1.5 if len(text) == 2 else 1.2)
    thickness = 3
    text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
    text_x = (size - text_size[0]) // 2
    text_y = (size + text_size[1]) // 2

    temp = img.copy()
    for offset, alpha in zip([(2, 2), (1, 1)], [120, 180]):
        cv2.putText(
            temp, text, (text_x + offset[0], text_y + offset[1]),
            font, font_scale, (0, 0, 0, alpha), thickness,
        )
    cv2.putText(temp, text, (text_x - 1, text_y - 1), font, font_scale, (255, 255, 255, 100), thickness)
    cv2.putText(temp, text, (text_x, text_y), font, font_scale, color, thickness)

    h, w, _ = temp.shape
    q_img = QImage(temp.data, w, h, 4 * w, QImage.Format.Format_RGBA8888)
    return QIcon(QPixmap.fromImage(q_img))
