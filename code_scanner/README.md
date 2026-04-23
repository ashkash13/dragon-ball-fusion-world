# Card Code Scanner

A cross-platform Rust desktop app for extracting 16-character alphanumeric card codes from uploaded images.

## Current milestone

- Upload one or many images
- OCR scan with orientation handling
- Extract likely 16-character codes
- Export `codes.txt`
- Windows + macOS friendly project layout

## Planned next milestone

- Webcam capture for Windows and macOS
- Better card-region detection and cropping
- Bundled deployment with OCR runtime assets

## Development setup

### macOS

Install Tesseract:

```bash
brew install tesseract