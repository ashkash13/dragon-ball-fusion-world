mod app;
mod camera;
mod export;
mod image_utils;
mod ocr;
mod scanner;
mod tesseract;
mod vision_bridge;

use app::CardCodeScannerApp;

fn main() -> eframe::Result<()> {
    let options = eframe::NativeOptions::default();

    eframe::run_native(
        "Card Code Scanner",
        options,
        Box::new(|_cc| Ok(Box::new(CardCodeScannerApp::default()))),
    )
}
