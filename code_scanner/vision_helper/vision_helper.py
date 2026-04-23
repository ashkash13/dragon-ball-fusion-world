import argparse
import json
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

CARD_WARP_WIDTH = 500
CARD_WARP_HEIGHT = 760
MIN_CARD_AREA_RATIO = 0.01
MAX_CARD_AREA_RATIO = 0.35
MIN_CARD_WIDTH = 120
MIN_CARD_HEIGHT = 160
CARD_ASPECT_MIN = 1.15
CARD_ASPECT_MAX = 2.25
ROW_Y_THRESHOLD = 100.0
IOU_THRESHOLD = 0.35


def order_points(pts: np.ndarray) -> np.ndarray:
    pts = np.array(pts, dtype=np.float32)
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)

    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(diff)]
    bl = pts[np.argmax(diff)]
    return np.array([tl, tr, br, bl], dtype=np.float32)


def rect_iou(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b

    x1 = max(ax, bx)
    y1 = max(ay, by)
    x2 = min(ax + aw, bx + bw)
    y2 = min(ay + ah, by + bh)

    iw = max(0, x2 - x1)
    ih = max(0, y2 - y1)
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    return 0.0 if union <= 0 else inter / union


def detect_cards(image_bgr):
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    _, non_white = cv2.threshold(blurred, 235, 255, cv2.THRESH_BINARY_INV)
    edges = cv2.Canny(blurred, 60, 160)

    close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21))
    dilate_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))

    merged_non_white = cv2.morphologyEx(non_white, cv2.MORPH_CLOSE, close_kernel, iterations=2)
    merged_non_white = cv2.dilate(merged_non_white, dilate_kernel, iterations=2)

    merged_edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, close_kernel, iterations=2)
    merged_edges = cv2.dilate(merged_edges, dilate_kernel, iterations=2)

    combined = cv2.bitwise_or(merged_non_white, merged_edges)

    contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = image_bgr.shape[0] * image_bgr.shape[1]

    candidates = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < image_area * MIN_CARD_AREA_RATIO or area > image_area * MAX_CARD_AREA_RATIO:
            continue

        x, y, w, h = cv2.boundingRect(contour)
        if w < MIN_CARD_WIDTH or h < MIN_CARD_HEIGHT:
            continue

        aspect = h / float(w)
        if not (CARD_ASPECT_MIN <= aspect <= CARD_ASPECT_MAX):
            continue

        rot = cv2.minAreaRect(contour)
        box = cv2.boxPoints(rot)
        ordered = order_points(box)
        candidates.append({
            "rect": (x, y, w, h),
            "points": ordered,
            "area": area,
        })

    candidates.sort(key=lambda c: c["area"], reverse=True)
    kept = []
    for candidate in candidates:
        if any(rect_iou(candidate["rect"], existing["rect"]) > IOU_THRESHOLD for existing in kept):
            continue
        kept.append(candidate)

    kept.sort(key=lambda c: (
        round(float(np.mean(c["points"][:, 1])) / ROW_Y_THRESHOLD),
        float(np.mean(c["points"][:, 0])),
    ))

    return kept, combined


def warp_card(image_bgr, points):
    dst = np.array([
        [0, 0],
        [CARD_WARP_WIDTH - 1, 0],
        [CARD_WARP_WIDTH - 1, CARD_WARP_HEIGHT - 1],
        [0, CARD_WARP_HEIGHT - 1],
    ], dtype=np.float32)

    matrix = cv2.getPerspectiveTransform(points.astype(np.float32), dst)
    return cv2.warpPerspective(image_bgr, matrix, (CARD_WARP_WIDTH, CARD_WARP_HEIGHT))


def build_output_dir(input_path: Path) -> Path:
    base = Path(tempfile.gettempdir()) / f"card_scanner_helper_{input_path.stem}"
    base.mkdir(parents=True, exist_ok=True)
    return base


def scan_image(input_path: Path):
    image = cv2.imread(str(input_path), cv2.IMREAD_COLOR)
    if image is None:
        return {
            "ok": False,
            "cards": [],
            "debug_messages": [],
            "error": f"Failed to read image: {input_path}",
        }

    cards, debug_mask = detect_cards(image)
    output_dir = build_output_dir(input_path)

    debug_messages = [f"detected {len(cards)} card candidates", f"debug output: {output_dir}"]
    cv2.imwrite(str(output_dir / "debug_mask.png"), debug_mask)

    response_cards = []
    for idx, card in enumerate(cards):
        warped = warp_card(image, card["points"])
        crop_path = output_dir / f"card_{idx:02}.png"
        cv2.imwrite(str(crop_path), warped)
        response_cards.append({
            "card_index": idx,
            "crop_path": str(crop_path),
            "confidence": 0.90,
        })

    return {
        "ok": True,
        "cards": response_cards,
        "debug_messages": debug_messages,
        "error": None,
    }


def parse_args():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    scan_image_cmd = sub.add_parser("scan-image")
    scan_image_cmd.add_argument("--input", required=True)

    return parser.parse_args()


def main():
    args = parse_args()

    if args.command == "scan-image":
        result = scan_image(Path(args.input))
        json.dump(result, sys.stdout)
        return 0 if result["ok"] else 1

    json.dump({
        "ok": False,
        "cards": [],
        "debug_messages": [],
        "error": f"Unknown command: {args.command}",
    }, sys.stdout)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
