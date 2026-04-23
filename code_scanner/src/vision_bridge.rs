use anyhow::{anyhow, Context, Result};
use serde::{Deserialize, Serialize};
use std::env;
use std::path::{Path, PathBuf};
use std::process::Command;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HelperCardRegion {
    pub card_index: usize,
    pub crop_path: String,
    pub confidence: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HelperScanResponse {
    pub ok: bool,
    pub cards: Vec<HelperCardRegion>,
    pub debug_messages: Vec<String>,
    pub error: Option<String>,
}

pub fn detect_cards_with_helper(image_path: &Path) -> Result<HelperScanResponse> {
    let helper = resolve_helper_path()?;

    let output = Command::new(&helper)
        .arg("scan-image")
        .arg("--input")
        .arg(image_path)
        .output()
        .with_context(|| format!("Failed to launch vision helper: {}", helper.display()))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
        return Err(anyhow!(
            "Vision helper failed (status {}): {}{}{}",
            output.status,
            stderr,
            if !stderr.is_empty() && !stdout.is_empty() { " | stdout: " } else { "" },
            stdout
        ));
    }

    let stdout = String::from_utf8(output.stdout)
        .context("Vision helper output was not valid UTF-8")?;

    let response: HelperScanResponse = serde_json::from_str(&stdout)
        .with_context(|| format!("Vision helper returned invalid JSON: {stdout}"))?;

    if !response.ok {
        return Err(anyhow!(
            "Vision helper reported failure: {}",
            response.error.unwrap_or_else(|| "unknown helper error".to_string())
        ));
    }

    Ok(response)
}

fn resolve_helper_path() -> Result<PathBuf> {
    if let Some(from_env) = env::var_os("CARD_SCANNER_VISION_HELPER") {
        let path = PathBuf::from(from_env);
        if path.exists() {
            return Ok(path);
        }
    }

    let exe = env::current_exe().context("Unable to resolve current executable path")?;
    let exe_dir = exe
        .parent()
        .ok_or_else(|| anyhow!("Executable has no parent directory"))?;

    let candidates: Vec<PathBuf> = if cfg!(target_os = "windows") {
        vec![
            exe_dir.join("vision_helper").join("vision_helper.exe"),
            exe_dir.join("vision_helper.exe"),
            exe_dir.join("resources").join("vision_helper").join("vision_helper.exe"),
            exe_dir.join("vision_helper").join("run_helper_windows.bat"),
        ]
    } else {
        vec![
            exe_dir.join("vision_helper").join("vision_helper"),
            exe_dir.join("vision_helper"),
            exe_dir.join("../Resources/vision_helper/vision_helper"),
            exe_dir.join("vision_helper").join("run_helper_mac.sh"),
        ]
    };

    candidates
        .into_iter()
        .find(|p| p.exists())
        .ok_or_else(|| anyhow!(
            "Could not find packaged vision helper. Set CARD_SCANNER_VISION_HELPER to override."
        ))
}
