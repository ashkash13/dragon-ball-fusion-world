use crate::ocr::extract_codes_with_score;
use crate::tesseract::ensure_tesseract_ready;
use anyhow::{Context, Result};
use leptess::{LepTess, Variable};
use opencv::{
    core::{self, AlgorithmHint, Mat, Point, Point2f, Rect, Scalar, Size, Vector},
    imgcodecs,
    imgproc,
    prelude::*,
};
use std::collections::BTreeSet;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone)]
pub struct ScanResult {
    pub file_path: PathBuf,
    pub codes: Vec<String>,
    pub raw_text_preview: String,
    pub error: Option<String>,
}

pub fn scan_image_file(path: &Path) -> Result<ScanResult> {
    ensure_tesseract_ready()?;

    let image_path = path
        .to_str()
        .ok_or_else(|| anyhow::anyhow!("Invalid UTF-8 path"))?;

    let src = imgcodecs::imread(image_path, imgcodecs::IMREAD_COLOR)
        .with_context(|| format!("Failed to read image: {}", path.display()))?;

    if src.empty() {
        return Err(anyhow::anyhow!("Loaded image is empty"));
    }

    let mut raw_preview_parts = Vec::new();
    let mut all_codes = BTreeSet::new();

    let cards = detect_cards(&src)?;
    raw_preview_parts.push(format!("Detected cards: {}", cards.len()));

    if cards.is_empty() {
        raw_preview_parts.push("No cards detected. Falling back to full-image scanning.".to_string());
        scan_full_image_fallback(path, &src, &mut all_codes, &mut raw_preview_parts)?;
    } else {
        for (card_idx, card) in cards.iter().enumerate() {
            let warped = warp_card(&src, card)?;
            let regions = build_code_regions(&warped)?;

            let mut best_for_card: Option<(String, i32)> = None;

            for (region_idx, region) in regions.iter().enumerate() {
                let variants = build_region_variants(region)?;

                for (variant_idx, variant) in variants.iter().enumerate() {
                    let temp_path = create_temp_image_path(path, card_idx, region_idx, variant_idx);

                    let ok = imgcodecs::imwrite(
                        temp_path.to_str().unwrap(),
                        variant,
                        &Vector::<i32>::new(),
                    )?;
                    if !ok {
                        continue;
                    }

                    let ocr_text = run_ocr_on_image(&temp_path)
                        .with_context(|| format!("OCR failed for {}", temp_path.display()))?;

                    let _ = fs::remove_file(&temp_path);

                    if !ocr_text.trim().is_empty() {
                        raw_preview_parts.push(format!(
                            "--- Card {} Region {} Variant {} ---\n{}",
                            card_idx, region_idx, variant_idx, ocr_text
                        ));
                    }

                    for (code, score) in extract_codes_with_score(&ocr_text) {
                        match &best_for_card {
                            Some((_, best_score)) if *best_score >= score => {}
                            _ => best_for_card = Some((code, score)),
                        }
                    }
                }
            }

            if let Some((best_code, best_score)) = best_for_card {
                raw_preview_parts.push(format!(
                    "Best code for card {}: {} (score {})",
                    card_idx, best_code, best_score
                ));
                all_codes.insert(best_code);
            } else {
                raw_preview_parts.push(format!("No valid code found for card {}", card_idx));
            }
        }
    }

    Ok(ScanResult {
        file_path: path.to_path_buf(),
        codes: all_codes.into_iter().collect(),
        raw_text_preview: raw_preview_parts.join("\n\n"),
        error: None,
    })
}

fn scan_full_image_fallback(
    original_path: &Path,
    src: &Mat,
    all_codes: &mut BTreeSet<String>,
    raw_preview_parts: &mut Vec<String>,
) -> Result<()> {
    let regions = build_fallback_regions(src)?;

    for (region_idx, region) in regions.iter().enumerate() {
        let variants = build_region_variants(region)?;

        for (variant_idx, variant) in variants.iter().enumerate() {
            let temp_path = create_fallback_temp_image_path(original_path, region_idx, variant_idx);

            let ok = imgcodecs::imwrite(
                temp_path.to_str().unwrap(),
                variant,
                &Vector::<i32>::new(),
            )?;
            if !ok {
                continue;
            }

            let ocr_text = run_ocr_on_image(&temp_path)?;
            let _ = fs::remove_file(&temp_path);

            if !ocr_text.trim().is_empty() {
                raw_preview_parts.push(format!(
                    "--- Fallback Region {} Variant {} ---\n{}",
                    region_idx, variant_idx, ocr_text
                ));
            }

            for (code, _) in extract_codes_with_score(&ocr_text) {
                all_codes.insert(code);
            }
        }
    }

    Ok(())
}

fn detect_cards(src: &Mat) -> Result<Vec<[Point2f; 4]>> {
    let mut gray = Mat::default();
    imgproc::cvt_color(
        src,
        &mut gray,
        imgproc::COLOR_BGR2GRAY,
        0,
        AlgorithmHint::ALGO_HINT_DEFAULT,
    )?;

    let mut blurred = Mat::default();
    imgproc::gaussian_blur(
        &gray,
        &mut blurred,
        Size::new(5, 5),
        0.0,
        0.0,
        core::BORDER_DEFAULT,
        AlgorithmHint::ALGO_HINT_DEFAULT,
    )?;

    // Stronger binarization for white background + dark card edges/text
    let mut thresh = Mat::default();
    imgproc::threshold(
        &blurred,
        &mut thresh,
        0.0,
        255.0,
        imgproc::THRESH_BINARY_INV | imgproc::THRESH_OTSU,
    )?;

    // Close small gaps so card borders become more continuous
    let kernel = imgproc::get_structuring_element(
        imgproc::MORPH_RECT,
        Size::new(5, 5),
        Point::new(-1, -1),
    )?;

    let mut morphed = Mat::default();
    imgproc::morphology_ex(
        &thresh,
        &mut morphed,
        imgproc::MORPH_CLOSE,
        &kernel,
        Point::new(-1, -1),
        2,
        core::BORDER_CONSTANT,
        Scalar::default(),
    )?;

    let mut contours = Vector::<Vector<Point>>::new();
    imgproc::find_contours(
        &morphed,
        &mut contours,
        imgproc::RETR_LIST,
        imgproc::CHAIN_APPROX_SIMPLE,
        Point::new(0, 0),
    )?;

    let image_area = (src.cols() * src.rows()) as f64;
    let mut candidates: Vec<(Rect, [Point2f; 4], f64)> = Vec::new();

    for contour in contours {
        let area = imgproc::contour_area(&contour, false)?;
        if area < image_area * 0.005 || area > image_area * 0.25 {
            continue;
        }

        let peri = imgproc::arc_length(&contour, true)?;
        let mut approx = Vector::<Point>::new();
        imgproc::approx_poly_dp(&contour, &mut approx, 0.03 * peri, true)?;

        if approx.len() != 4 {
            continue;
        }

        let pts = approx.to_vec();
        let rect = imgproc::bounding_rect(&approx)?;

        if rect.width < 80 || rect.height < 120 {
            continue;
        }

        let aspect = rect.height as f32 / rect.width as f32;
        if !(1.2..=2.2).contains(&aspect) {
            continue;
        }

        let ordered = order_points(&pts)?;
        candidates.push((rect, ordered, area));
    }

    // Remove near-duplicate detections
    candidates.sort_by(|a, b| b.2.partial_cmp(&a.2).unwrap_or(std::cmp::Ordering::Equal));

    let mut kept: Vec<(Rect, [Point2f; 4], f64)> = Vec::new();

    for cand in candidates {
        let mut overlaps_existing = false;
        for existing in &kept {
            if rect_iou(&cand.0, &existing.0) > 0.4 {
                overlaps_existing = true;
                break;
            }
        }
        if !overlaps_existing {
            kept.push(cand);
        }
    }

    let mut cards: Vec<[Point2f; 4]> = kept.into_iter().map(|(_, pts, _)| pts).collect();

    // Sort top-to-bottom, then left-to-right
    cards.sort_by(|a, b| {
        let ay = a.iter().map(|p| p.y).sum::<f32>() / 4.0;
        let by = b.iter().map(|p| p.y).sum::<f32>() / 4.0;

        if (ay - by).abs() < 80.0 {
            let ax = a.iter().map(|p| p.x).sum::<f32>() / 4.0;
            let bx = b.iter().map(|p| p.x).sum::<f32>() / 4.0;
            ax.partial_cmp(&bx).unwrap_or(std::cmp::Ordering::Equal)
        } else {
            ay.partial_cmp(&by).unwrap_or(std::cmp::Ordering::Equal)
        }
    });

    Ok(cards)
}

fn rect_iou(a: &Rect, b: &Rect) -> f32 {
    let x1 = a.x.max(b.x);
    let y1 = a.y.max(b.y);
    let x2 = (a.x + a.width).min(b.x + b.width);
    let y2 = (a.y + a.height).min(b.y + b.height);

    let inter_w = (x2 - x1).max(0);
    let inter_h = (y2 - y1).max(0);
    let inter_area = (inter_w * inter_h) as f32;

    let a_area = (a.width * a.height) as f32;
    let b_area = (b.width * b.height) as f32;
    let union = a_area + b_area - inter_area;

    if union <= 0.0 {
        0.0
    } else {
        inter_area / union
    }
}

fn order_points(pts: &[Point]) -> Result<[Point2f; 4]> {
    if pts.len() != 4 {
        return Err(anyhow::anyhow!("Expected exactly 4 points"));
    }

    let pts_f: Vec<Point2f> = pts
        .iter()
        .map(|p| Point2f::new(p.x as f32, p.y as f32))
        .collect();

    let mut tl = pts_f[0];
    let mut tr = pts_f[0];
    let mut br = pts_f[0];
    let mut bl = pts_f[0];

    let mut min_sum = f32::MAX;
    let mut max_sum = f32::MIN;
    let mut min_diff = f32::MAX;
    let mut max_diff = f32::MIN;

    for p in &pts_f {
        let sum = p.x + p.y;
        let diff = p.x - p.y;

        if sum < min_sum {
            min_sum = sum;
            tl = *p;
        }
        if sum > max_sum {
            max_sum = sum;
            br = *p;
        }
        if diff < min_diff {
            min_diff = diff;
            bl = *p;
        }
        if diff > max_diff {
            max_diff = diff;
            tr = *p;
        }
    }

    Ok([tl, tr, br, bl])
}

fn warp_card(src: &Mat, pts: &[Point2f; 4]) -> Result<Mat> {
    let width = 500;
    let height = 760;

    let src_pts = Mat::from_slice(pts)?;
    let dst_points = [
        Point2f::new(0.0, 0.0),
        Point2f::new(width as f32 - 1.0, 0.0),
        Point2f::new(width as f32 - 1.0, height as f32 - 1.0),
        Point2f::new(0.0, height as f32 - 1.0),
    ];
    let dst_pts = Mat::from_slice(&dst_points)?;

    let transform = imgproc::get_perspective_transform(&src_pts, &dst_pts, 0)?;

    let mut warped = Mat::default();
    imgproc::warp_perspective(
        src,
        &mut warped,
        &transform,
        Size::new(width, height),
        imgproc::INTER_LINEAR,
        core::BORDER_CONSTANT,
        Scalar::default(),
    )?;

    Ok(warped)
}

fn build_code_regions(card: &Mat) -> Result<Vec<Mat>> {
    let w = card.cols();
    let h = card.rows();

    let candidates = [
        Rect::new(w / 10, (h * 68) / 100, (w * 8) / 10, h / 10),
        Rect::new(w / 12, (h * 66) / 100, (w * 10) / 12, h / 9),
        Rect::new(w / 8, (h * 70) / 100, (w * 6) / 8, h / 12),
    ];

    let mut out = Vec::new();

    for rect in candidates {
        let roi = Mat::roi(card, rect)?;
        let mut copy = Mat::default();
        roi.copy_to(&mut copy)?;
        out.push(preprocess_region(&copy)?);
    }

    Ok(out)
}

fn build_fallback_regions(src: &Mat) -> Result<Vec<Mat>> {
    let w = src.cols();
    let h = src.rows();

    let candidates = [
        Rect::new(0, h / 2, w, h / 2),
        Rect::new(0, (h * 2) / 3, w, h / 3),
        Rect::new(w / 8, (h * 5) / 8, (w * 3) / 4, h / 5),
    ];

    let mut out = Vec::new();
    for rect in candidates {
        let roi = Mat::roi(src, rect)?;
        let mut copy = Mat::default();
        roi.copy_to(&mut copy)?;
        out.push(preprocess_region(&copy)?);
    }

    Ok(out)
}

fn preprocess_region(region: &Mat) -> Result<Mat> {
    let mut gray = Mat::default();
    imgproc::cvt_color(
        region,
        &mut gray,
        imgproc::COLOR_BGR2GRAY,
        0,
        AlgorithmHint::ALGO_HINT_DEFAULT,
    )?;

    let mut enlarged = Mat::default();
    imgproc::resize(
        &gray,
        &mut enlarged,
        Size::new(0, 0),
        3.0,
        3.0,
        imgproc::INTER_CUBIC,
    )?;

    let mut thresh = Mat::default();
    imgproc::threshold(
        &enlarged,
        &mut thresh,
        0.0,
        255.0,
        imgproc::THRESH_BINARY | imgproc::THRESH_OTSU,
    )?;

    Ok(thresh)
}

fn build_region_variants(region: &Mat) -> Result<Vec<Mat>> {
    let mut out = Vec::new();
    out.push(region.clone());

    let mut inv = Mat::default();
    core::bitwise_not(region, &mut inv, &core::no_array())?;
    out.push(inv);

    Ok(out)
}

fn run_ocr_on_image(path: &Path) -> Result<String> {
    let mut lt = LepTess::new(None, "eng")?;
    lt.set_variable(
        Variable::TesseditCharWhitelist,
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ",
    )?;
    lt.set_variable(Variable::TesseditPagesegMode, "7")?;
    lt.set_image(path)?;
    Ok(lt.get_utf8_text()?)
}

fn create_temp_image_path(
    original: &Path,
    card_index: usize,
    region_index: usize,
    variant_index: usize,
) -> PathBuf {
    let file_name = original
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("scan_input");

    let pid = std::process::id();
    std::env::temp_dir().join(format!(
        "{file_name}_card_{card_index}_region_{region_index}_variant_{variant_index}_{pid}.png"
    ))
}

fn create_fallback_temp_image_path(
    original: &Path,
    region_index: usize,
    variant_index: usize,
) -> PathBuf {
    let file_name = original
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("scan_input");

    let pid = std::process::id();
    std::env::temp_dir().join(format!(
        "{file_name}_fallback_region_{region_index}_variant_{variant_index}_{pid}.png"
    ))
}
