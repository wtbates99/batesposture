import numpy as np
import cv2
from PyQt6.QtGui import QIcon, QPixmap, QImage


def create_score_icon(score):
    img = np.zeros((64, 64, 4), dtype=np.uint8)
    img[:, :, 3] = 0

    center = (32, 32)
    radius = 30

    for r in range(radius + 8, radius - 1, -1):
        for y in range(64):
            for x in range(64):
                dist = np.sqrt((x - center[0]) ** 2 + (y - center[1]) ** 2)
                if dist <= r:
                    alpha = int(255 * (1 - dist / r) * (r - radius + 8) / (8))
                    if r == radius:
                        alpha = min(255, alpha * 1.5)
                    img[y, x, 3] = max(img[y, x, 3], alpha)

    hue = int(score * 60 / 100)
    hue = min(60, max(0, hue))
    rgb_color = cv2.cvtColor(np.uint8([[[hue, 255, 255]]]), cv2.COLOR_HSV2BGR)[0][0]
    color = (int(rgb_color[0]), int(rgb_color[1]), int(rgb_color[2]), 255)
    font = cv2.FONT_HERSHEY_DUPLEX
    text = f"{int(score)}"
    font_scale = 2.0 if len(text) == 1 else (1.5 if len(text) == 2 else 1.2)
    thickness = 3
    text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
    text_x = (64 - text_size[0]) // 2
    text_y = (64 + text_size[1]) // 2
    temp = img.copy()
    shadow_offsets = [(2, 2), (1, 1)]
    shadow_alphas = [120, 180]
    for offset, alpha in zip(shadow_offsets, shadow_alphas):
        shadow_color = (0, 0, 0, alpha)
        cv2.putText(
            temp,
            text,
            (text_x + offset[0], text_y + offset[1]),
            font,
            font_scale,
            shadow_color,
            thickness,
        )

    highlight_color = (255, 255, 255, 100)
    cv2.putText(
        temp,
        text,
        (text_x - 1, text_y - 1),
        font,
        font_scale,
        highlight_color,
        thickness,
    )

    cv2.putText(temp, text, (text_x, text_y), font, font_scale, color, thickness)

    height, width, channel = temp.shape
    bytes_per_line = 4 * width
    q_img = QImage(
        temp.data, width, height, bytes_per_line, QImage.Format.Format_RGBA8888
    )
    return QIcon(QPixmap.fromImage(q_img))
