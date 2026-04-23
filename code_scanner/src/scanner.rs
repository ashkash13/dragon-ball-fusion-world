use crate::ocr::extract_codes_with_score;
use crate::tesseract::ensure_tesseract_ready;
use crate::vision_bridge::detect_cards_with_helper;
use anyhow::{Context, Result};
use leptess::{LepTess, Variable};
use std::collections::BTreeSet;
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

    let helper_response = detect_cards_with_helper(path)?;

    let mut raw_preview_parts = Vec::new();
    let mut all_codes = BTreeSet::new();

    raw_preview_parts.push(format!("Helper detected cards: {}", helper_response.cards.len()));
    for msg in &helper_response.debug_messages {
        raw_preview_parts.push(format!("[helper] {msg}"));
    }

    if helper_response.cards.is_empty() {
        raw_preview_parts.push("No card crops returned by helper.".to_string());
    }

    for card in &helper_response.cards {
        let crop_path = Path::new(&card.crop_path);
        let ocr_text = run_ocr_on_image(crop_path)
            .with_context(|| format!("OCR failed for helper crop {}", crop_path.display()))?;

        if !ocr_text.trim().is_empty() {
            raw_preview_parts.push(format!(
                "--- Card {} OCR (confidence {:.2}) ---\n{}",
                card.card_index,
                card.confidence,
                ocr_text.trim()
            ));
        }

        let mut best_for_card: Option<(String, i32)> = None;

        for (code, score) in extract_codes_with_score(&ocr_text) {
            match &best_for_card {
                Some((_, best_score)) if *best_score >= score => {}
                _ => best_for_card = Some((code, score)),
            }
        }

        if let Some((best_code, best_score)) = best_for_card {
            raw_preview_parts.push(format!(
                "Best code for card {}: {} (score {})",
                card.card_index, best_code, best_score
            ));
            all_codes.insert(best_code);
        } else {
            raw_preview_parts.push(format!(
                "No valid code found for helper card {}",
                card.card_index
            ));
        }
    }

    Ok(ScanResult {
        file_path: path.to_path_buf(),
        codes: all_codes.into_iter().collect(),
        raw_text_preview: raw_preview_parts.join("\n\n"),
        error: None,
    })
}

fn run_ocr_on_image(path: &Path) -> Result<String> {
    let mut lt = LepTess::new(None, "eng")?;
    lt.set_variable(
        Variable::TesseditCharWhitelist,
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ",
    )?;
    lt.set_variable(Variable::TesseditPagesegMode, "7")?;
    lt.set_image(path)?;
    Ok(lt.get_utf8_text()?.trim().to_string())
}
