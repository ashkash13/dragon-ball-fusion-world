use image::{DynamicImage, GrayImage, ImageBuffer, Luma};

pub fn build_image_variants(image: &DynamicImage) -> Vec<DynamicImage> {
    vec![
        image.clone(),
        image.rotate90(),
        image.rotate180(),
        image.rotate270(),
    ]
}

pub fn preprocess_for_ocr(image: &DynamicImage) -> GrayImage {
    let gray = image.to_luma8();
    let contrasted = increase_contrast_simple(&gray);
    threshold_image(&contrasted, 165)
}

fn increase_contrast_simple(img: &GrayImage) -> GrayImage {
    let mut out = GrayImage::new(img.width(), img.height());

    for (x, y, pixel) in img.enumerate_pixels() {
        let v = pixel[0] as f32;
        let adjusted = ((v - 128.0) * 1.4 + 128.0).clamp(0.0, 255.0) as u8;
        out.put_pixel(x, y, Luma([adjusted]));
    }

    out
}

fn threshold_image(img: &GrayImage, threshold: u8) -> GrayImage {
    let mut out: GrayImage = ImageBuffer::new(img.width(), img.height());

    for (x, y, pixel) in img.enumerate_pixels() {
        let v = if pixel[0] > threshold { 255 } else { 0 };
        out.put_pixel(x, y, Luma([v]));
    }

    out
}