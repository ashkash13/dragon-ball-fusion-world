use regex::Regex;
use std::collections::BTreeSet;

pub fn extract_codes(raw: &str) -> Vec<String> {
    extract_codes_with_score(raw)
        .into_iter()
        .map(|(code, _)| code)
        .collect()
}

pub fn extract_codes_with_score(raw: &str) -> Vec<(String, i32)> {
    let normalized = normalize_ocr_text(raw);

    let re = Regex::new(r"(?i)\b([A-Z0-9]{4}\s?[A-Z0-9]{4}\s?[A-Z0-9]{4}\s?[A-Z0-9]{4})\b")
        .expect("valid regex");

    let mut results = BTreeSet::new();

    for cap in re.captures_iter(&normalized) {
        if let Some(m) = cap.get(1) {
            let raw_match = m.as_str().to_uppercase();
            let compact = compact_code(&raw_match);

            if compact.len() != 16 || !compact.chars().all(|c| c.is_ascii_alphanumeric()) {
                continue;
            }

            let fixed = generate_corrections(&compact);
            for candidate in fixed {
                let score = score_candidate(&raw_match, &candidate);
                results.insert((format_code_groups(&candidate), score));
            }
        }
    }

    let mut out: Vec<(String, i32)> = results.into_iter().collect();
    out.sort_by(|a, b| b.1.cmp(&a.1));
    out
}

fn normalize_ocr_text(raw: &str) -> String {
    raw.to_uppercase()
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || c.is_ascii_whitespace() {
                c
            } else {
                ' '
            }
        })
        .collect::<String>()
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}

fn compact_code(s: &str) -> String {
    s.chars().filter(|c| c.is_ascii_alphanumeric()).collect()
}

fn generate_corrections(code: &str) -> Vec<String> {
    let mut out = BTreeSet::new();
    out.insert(code.to_string());

    let swaps = [('O', '0'), ('I', '1'), ('S', '5'), ('B', '8'), ('Z', '2')];

    for (a, b) in swaps {
        out.insert(code.replace(a, &b.to_string()));
        out.insert(code.replace(b, &a.to_string()));
    }

    out.into_iter().collect()
}

fn score_candidate(raw_match: &str, candidate: &str) -> i32 {
    let compact_raw = compact_code(raw_match);
    let mut score = 100;

    for (r, c) in compact_raw.chars().zip(candidate.chars()) {
        if r != c {
            score -= 8;
        }
    }

    if candidate.chars().filter(|c| c.is_ascii_digit()).count() < 2 {
        score -= 10;
    }

    score
}

fn format_code_groups(code: &str) -> String {
    format!(
        "{} {} {} {}",
        &code[0..4],
        &code[4..8],
        &code[8..12],
        &code[12..16]
    )
}
