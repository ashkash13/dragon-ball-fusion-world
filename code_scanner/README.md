# Hybrid Card Scanner Drop-In Set

## What changed
- Rust no longer depends on `opencv`.
- Rust now calls a local vision helper subprocess.
- The helper is written in Python and uses OpenCV for card detection.
- Rust keeps Tesseract OCR and your regex cleanup logic.

## Replace in your project
Copy these files into your project:
- `Cargo.toml`
- `src/main.rs`
- `src/app.rs`
- `src/camera.rs`
- `src/scanner.rs`
- `src/vision_bridge.rs`

Keep these from this drop-in set if you want exact copies:
- `src/export.rs`
- `src/image_utils.rs`
- `src/ocr.rs`
- `src/tesseract.rs`

Add these new folders:
- `vision_helper/`
- `scripts/`
- `bundled/vision_helper/`
- `bundled/tessdata/`

## Development setup on Windows
1. Create the helper venv and install packages:
   - `python -m venv vision_helper\.venv`
   - `vision_helper\.venv\Scripts\activate`
   - `pip install -r vision_helper\requirements.txt`
2. Point Rust at the dev wrapper:
   - PowerShell:
     - `$env:CARD_SCANNER_VISION_HELPER = "C:\\path\\to\\code_scanner\\vision_helper\\run_helper_windows.bat"`
3. Make sure `eng.traineddata` is available through `TESSDATA_PREFIX` or bundled `tessdata/`.
4. Run `cargo build`.

## Development setup on macOS
1. `python3 -m venv vision_helper/.venv`
2. `source vision_helper/.venv/bin/activate`
3. `pip install -r vision_helper/requirements.txt`
4. `export CARD_SCANNER_VISION_HELPER="/path/to/code_scanner/vision_helper/run_helper_mac.sh"`
5. Run `cargo build`.

## Packaging
### Windows
- Run `scripts/build_helper_windows.ps1`
- It produces `bundled/vision_helper/vision_helper.exe`
- Put `bundled/vision_helper/` and `bundled/tessdata/` next to your Rust executable or inside your installer layout.

### macOS
- Run `scripts/build_helper_mac.sh`
- It produces `bundled/vision_helper/vision_helper`
- Put it inside the `.app` resources bundle together with `tessdata`.

## Next improvement
Right now the helper returns full warped cards. The next upgrade should be returning likely code-band crops per card, which will improve OCR substantially.
