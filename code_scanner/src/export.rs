use anyhow::Result;
use std::fs::File;
use std::io::{BufWriter, Write};
use std::path::Path;

pub fn export_codes_to_file(path: &Path, codes: &[String]) -> Result<()> {
    let file = File::create(path)?;
    let mut writer = BufWriter::new(file);

    for code in codes {
        writeln!(writer, "{code}")?;
    }

    writer.flush()?;
    Ok(())
}
