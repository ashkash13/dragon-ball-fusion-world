#[cfg(feature = "camera")]
pub fn camera_feature_status() -> &'static str {
    "Camera feature enabled. Webcam capture implementation comes next."
}

#[cfg(not(feature = "camera"))]
pub fn camera_feature_status() -> &'static str {
    "Camera feature not enabled in this build."
}