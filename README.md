# Dragon Ball Fusion World — Tooling Suite

This repository contains desktop tools for automating Dragon Ball Fusion World card code management.

---

## Projects

### 1. [`code_scanner/`](code_scanner/)

Scans Dragon Ball Fusion World redemption cards and extracts their 16-character codes.

- Live camera scanning with a webcam
- Batch image upload (multiple cards per photo supported)
- Powered by Google Gemini vision AI (free tier)
- Exports a plain `codes.txt` file — one code per line

→ See [code_scanner/README.md](code_scanner/README.md) for full setup and usage instructions.

---

### 2. Code Redeemer *(coming soon)*

Takes the `codes.txt` output from the scanner and programmatically enters the codes into the Dragon Ball Fusion World game client.

---

## Repository Structure

```
dragon-ball-fusion-world/
├── code_scanner/        # Tool 1: scan cards → extract codes → codes.txt
└── (code_redeemer/)     # Tool 2: read codes.txt → enter into game client
```

## Reference Images

The `WhatsApp_Image_*.jpeg` files in the root are sample card photos used during development.
