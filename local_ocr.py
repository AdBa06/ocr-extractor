"""Offline OCR and ruled-table reconstruction for image-only PDF pages."""

from __future__ import annotations

from functools import lru_cache
from statistics import median
import re

import cv2
import numpy as np
from PIL import Image

import config


@lru_cache(maxsize=1)
def _engine():
    from rapidocr import RapidOCR

    return RapidOCR()


def ocr_page(image: Image.Image) -> tuple[str, list[list[list[str]]], list[dict]]:
    array = np.asarray(image.convert("RGB"))
    result = _engine()(array)
    if result is None or result.txts is None:
        return "", [], []

    words = []
    for box, text, score in zip(result.boxes, result.txts, result.scores):
        if float(score) < config.OCR_MIN_CONFIDENCE or not str(text).strip():
            continue
        xs = [float(point[0]) for point in box]
        ys = [float(point[1]) for point in box]
        cleaned_text = re.sub(r"\bB[I|l]k\b", "Blk", str(text).strip())
        words.append({
            "text": cleaned_text, "x0": min(xs), "x1": max(xs),
            "top": min(ys), "bottom": max(ys), "confidence": float(score),
            "source": "ocr",
        })
    words.sort(key=lambda item: (item["top"], item["x0"], item["text"]))
    return _lines(words), _ruled_tables(array, words), words


def _lines(words: list[dict]) -> str:
    if not words:
        return ""
    lines: list[list[dict]] = []
    for word in words:
        center = (word["top"] + word["bottom"]) / 2
        target = None
        for line in reversed(lines[-4:]):
            centers = [(item["top"] + item["bottom"]) / 2 for item in line]
            heights = [item["bottom"] - item["top"] for item in line]
            if abs(center - median(centers)) <= max(5.0, median(heights) * 0.55):
                target = line
                break
        if target is None:
            target = []
            lines.append(target)
        target.append(word)
    lines.sort(key=lambda line: (min(item["top"] for item in line), min(item["x0"] for item in line)))
    return "\n".join(" ".join(item["text"] for item in sorted(line, key=lambda item: item["x0"])) for line in lines)


def _clusters(values: list[int], tolerance: int = 4) -> list[int]:
    if not values:
        return []
    groups = [[values[0]]]
    for value in values[1:]:
        if value - groups[-1][-1] <= tolerance:
            groups[-1].append(value)
        else:
            groups.append([value])
    return [round(sum(group) / len(group)) for group in groups]


def _ruled_tables(image: np.ndarray, words: list[dict]) -> list[list[list[str]]]:
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    binary = cv2.threshold(gray, 210, 255, cv2.THRESH_BINARY_INV)[1]
    height, width = gray.shape
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN,
                                cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(25, height // 45))))
    contours = cv2.findContours(vertical, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
    segments = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if h >= height * 0.075 and w <= max(12, width * 0.02):
            segments.append((x + w // 2, y, y + h))
    if len(segments) < 3:
        return []

    # Vertical rules belonging to a table substantially overlap in Y.
    candidates = []
    for anchor in segments:
        group = [segment for segment in segments
                 if min(anchor[2], segment[2]) - max(anchor[1], segment[1]) >= min(anchor[2] - anchor[1], segment[2] - segment[1]) * 0.7]
        xs = _clusters(sorted(segment[0] for segment in group))
        if len(xs) >= 3:
            candidates.append((len(xs), xs, max(segment[1] for segment in group), min(segment[2] for segment in group)))
    if not candidates:
        return []
    _, xs, top, bottom = max(candidates, key=lambda item: (item[0], item[3] - item[2]))

    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN,
                                  cv2.getStructuringElement(cv2.MORPH_RECT, (max(30, width // 35), 1)))
    contours = cv2.findContours(horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
    y_values = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w >= (xs[-1] - xs[0]) * 0.65 and x <= xs[0] + 15 and x + w >= xs[-1] - 15:
            y_values.append(y + h // 2)
    ys = [value for value in _clusters(sorted(y_values)) if top - 12 <= value <= bottom + 12]
    if len(ys) < 2:
        return []
    if abs(ys[0] - top) > 10:
        ys.insert(0, top)
    if abs(ys[-1] - bottom) > 10:
        ys.append(bottom)

    table = []
    for y0, y1 in zip(ys, ys[1:]):
        row = []
        for x0, x1 in zip(xs, xs[1:]):
            inside = [item for item in words
                      if x0 - 3 <= (item["x0"] + item["x1"]) / 2 <= x1 + 3
                      and y0 - 3 <= (item["top"] + item["bottom"]) / 2 <= y1 + 3]
            inside.sort(key=lambda item: (item["top"], item["x0"]))
            row.append("\n".join(item["text"] for item in inside))
        table.append(row)
    return [table] if table else []
