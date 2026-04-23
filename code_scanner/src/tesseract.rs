use anyhow::{anyhow, Result};
use std::path::{Path, PathBuf};

pub fn configure_tesseract_environment() -> Result<()> {
    if std::env::var_os("TESSDATA_PREFIX").is_some() {
        return Ok(());
    }

    if let Some(local) = find_tessdata_dir() {
        unsafe {
            std::env::set_var("TESSDATA_PREFIX", &local);
        }
        return Ok(());
    }

    Ok(())
}

pub fn ensure_tesseract_ready() -> Result<()> {
    configure_tesseract_environment()?;

    if let Some(prefix) = std::env::var_os("TESSDATA_PREFIX") {
        let eng = Path::new(&prefix).join("eng.traineddata");
        if eng.exists() {
            return Ok(());
        }
    }

    Err(anyhow!(
        "Tesseract is not ready. Set TESSDATA_PREFIX or place eng.traineddata in a bundled tessdata directory."
    ))
}

fn find_tessdata_dir() -> Option<PathBuf> {
    let mut candidates: Vec<PathBuf> = Vec::new();

    if let Ok(exe) = std::env::current_exe() {
        if let Some(exe_dir) = exe.parent() {
            candidates.push(exe_dir.join("tessdata"));
            candidates.push(exe_dir.join("resources").join("tessdata"));
            candidates.push(exe_dir.join("../Resources/tessdata"));
        }
    }

    candidates.push(PathBuf::from("/opt/homebrew/share/tessdata"));
    candidates.push(PathBuf::from("/usr/local/share/tessdata"));
    candidates.push(PathBuf::from(r"C:\Program Files\Tesseract-OCR\tessdata"));
    candidates.push(PathBuf::from(r"C:\Program Files (x86)\Tesseract-OCR\tessdata"));

    candidates
        .into_iter()
        .find(|p| p.exists() && p.is_dir() && p.join("eng.traineddata").exists())
        .map(|p| p.canonicalize().unwrap_or(p))
}
