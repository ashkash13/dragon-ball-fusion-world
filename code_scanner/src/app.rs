use crate::camera::camera_feature_status;
use crate::export::export_codes_to_file;
use crate::scanner::{scan_image_file, ScanResult};
use crate::vision_bridge::detect_cards_with_helper;
use eframe::egui;
use rfd::FileDialog;
use std::collections::BTreeSet;
use std::path::PathBuf;

#[derive(Default)]
pub struct CardCodeScannerApp {
    selected_files: Vec<PathBuf>,
    results: Vec<ScanResult>,
    status: String,
}

impl CardCodeScannerApp {
    fn pick_files(&mut self) {
        if let Some(files) = FileDialog::new()
            .add_filter("Images", &["png", "jpg", "jpeg", "bmp", "webp", "tiff"])
            .pick_files()
        {
            self.selected_files = files;
            self.results.clear();
            self.status = format!("Selected {} file(s).", self.selected_files.len());
        }
    }

    fn scan_files(&mut self) {
        if self.selected_files.is_empty() {
            self.status = "No files selected.".to_string();
            return;
        }

        self.status = format!(
            "Scanning {} file(s) using packaged vision helper...",
            self.selected_files.len()
        );
        self.results.clear();

        for file in &self.selected_files {
            match scan_image_file(file) {
                Ok(result) => self.results.push(result),
                Err(err) => self.results.push(ScanResult {
                    file_path: file.clone(),
                    codes: vec![],
                    raw_text_preview: String::new(),
                    error: Some(err.to_string()),
                }),
            }
        }

        let total_codes: usize = self.results.iter().map(|r| r.codes.len()).sum();
        self.status = format!(
            "Scan complete. {} file(s) processed, {} code(s) found.",
            self.results.len(),
            total_codes
        );
    }

    fn export_codes(&mut self) {
        let mut unique_codes = BTreeSet::new();

        for result in &self.results {
            for code in &result.codes {
                unique_codes.insert(code.clone());
            }
        }

        if unique_codes.is_empty() {
            self.status = "No codes available to export.".to_string();
            return;
        }

        if let Some(path) = FileDialog::new().set_file_name("codes.txt").save_file() {
            let codes: Vec<String> = unique_codes.into_iter().collect();
            match export_codes_to_file(&path, &codes) {
                Ok(_) => {
                    self.status = format!("Exported {} code(s) to {}", codes.len(), path.display())
                }
                Err(err) => {
                    self.status = format!("Failed to export codes: {}", err);
                }
            }
        }
    }

    fn helper_health_check(&mut self) {
        if let Some(first) = self.selected_files.first() {
            match detect_cards_with_helper(first) {
                Ok(resp) => {
                    self.status = format!(
                        "Vision helper reachable. {} card crop(s) returned for sample file.",
                        resp.cards.len()
                    );
                }
                Err(err) => {
                    self.status = format!("Vision helper check failed: {err}");
                }
            }
        } else {
            self.status = "Select at least one image before testing the helper.".to_string();
        }
    }
}

impl eframe::App for CardCodeScannerApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        egui::TopBottomPanel::top("top_controls").show(ctx, |ui| {
            ui.horizontal(|ui| {
                if ui.button("Upload Images").clicked() {
                    self.pick_files();
                }

                if ui.button("Test Helper").clicked() {
                    self.helper_health_check();
                }

                if ui.button("Scan Images").clicked() {
                    self.scan_files();
                }

                if ui.button("Export Codes").clicked() {
                    self.export_codes();
                }
            });

            ui.separator();
            ui.label(format!("Status: {}", self.status));
            ui.small(format!("Camera: {}", camera_feature_status()));
        });

        egui::SidePanel::left("left_panel")
            .resizable(true)
            .default_width(280.0)
            .show(ctx, |ui| {
                ui.heading("Selected Files");
                ui.separator();

                if self.selected_files.is_empty() {
                    ui.label("No files selected.");
                } else {
                    egui::ScrollArea::vertical().show(ui, |ui| {
                        for file in &self.selected_files {
                            ui.label(file.display().to_string());
                        }
                    });
                }
            });

        egui::CentralPanel::default().show(ctx, |ui| {
            ui.heading("Scan Results");
            ui.separator();

            if self.results.is_empty() {
                ui.label("No scan results yet.");
            } else {
                egui::ScrollArea::vertical().show(ui, |ui| {
                    for result in &self.results {
                        ui.group(|ui| {
                            ui.label(format!("File: {}", result.file_path.display()));

                            if let Some(err) = &result.error {
                                ui.colored_label(egui::Color32::RED, format!("Error: {}", err));
                            } else if result.codes.is_empty() {
                                ui.label("No codes found.");
                            } else {
                                ui.label(format!("Codes found: {}", result.codes.len()));
                                for code in &result.codes {
                                    ui.monospace(code);
                                }
                            }

                            if !result.raw_text_preview.is_empty() {
                                ui.separator();
                                ui.collapsing("OCR / Helper Preview", |ui| {
                                    ui.monospace(&result.raw_text_preview);
                                });
                            }
                        });

                        ui.add_space(8.0);
                    }
                });
            }
        });
    }
}
