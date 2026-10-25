// Personal build: change a file's type. Drop a file on Putshi › Convert, or
// ask in chat. The result is saved next to the original (or in Downloads when
// that folder can't be written to), never over an existing file.
//
//   images  — PNG, JPG, WebP, GIF, BMP, ICO, TIFF, and PDF (one page per
//             image); iPhone HEIC/HEIF photos are read through Windows itself
//   office  — Word / Excel / PowerPoint ⇄ PDF and friends, through the
//             installed Office (or LibreOffice when that's what's there)
//   media   — audio and video through ffmpeg (installable from the card)

use std::path::{Path, PathBuf};
use std::process::Command;

use serde::Serialize;

use crate::platform;

const IMAGE_IN: &[&str] = &["png", "jpg", "jpeg", "webp", "gif", "bmp", "ico", "tif", "tiff"];
const WIC_IN: &[&str] = &["heic", "heif", "avif", "jxr", "dng"];
const WORD_IN: &[&str] = &["doc", "docx", "rtf", "odt", "txt", "md"];
const EXCEL_IN: &[&str] = &["xls", "xlsx", "csv", "ods"];
const PPT_IN: &[&str] = &["ppt", "pptx", "odp"];
const VIDEO_IN: &[&str] = &["mp4", "mov", "mkv", "avi", "webm", "wmv", "m4v", "flv"];
const AUDIO_IN: &[&str] = &["mp3", "wav", "m4a", "aac", "flac", "ogg", "opus", "wma"];

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Target {
    pub ext: String,
    pub label: String,
}

pub(crate) fn ext_of(path: &Path) -> String {
    path.extension().and_then(|e| e.to_str()).unwrap_or("").to_lowercase()
}

/// The formats worth offering for this file.
pub fn targets(path: &str) -> Vec<Target> {
    let ext = ext_of(Path::new(path));
    let list: &[(&str, &str)] = if IMAGE_IN.contains(&ext.as_str()) || WIC_IN.contains(&ext.as_str()) {
        &[("jpg", "JPG"), ("png", "PNG"), ("webp", "WebP"), ("pdf", "PDF"), ("ico", "Icon"), ("bmp", "BMP")]
    } else if WORD_IN.contains(&ext.as_str()) {
        &[("pdf", "PDF"), ("docx", "Word"), ("txt", "Text"), ("odt", "ODT"), ("rtf", "RTF")]
    } else if ext == "pdf" {
        &[("docx", "Word"), ("txt", "Text")]
    } else if EXCEL_IN.contains(&ext.as_str()) {
        &[("pdf", "PDF"), ("xlsx", "Excel"), ("csv", "CSV"), ("ods", "ODS")]
    } else if PPT_IN.contains(&ext.as_str()) {
        &[("pdf", "PDF"), ("pptx", "PowerPoint"), ("png", "Slides as PNG")]
    } else if VIDEO_IN.contains(&ext.as_str()) {
        &[("mp4", "MP4"), ("mp3", "MP3 (sound)"), ("gif", "GIF"), ("webm", "WebM"), ("mov", "MOV")]
    } else if AUDIO_IN.contains(&ext.as_str()) {
        &[("mp3", "MP3"), ("wav", "WAV"), ("m4a", "M4A"), ("flac", "FLAC"), ("ogg", "OGG")]
    } else {
        &[]
    };
    list.iter()
        .filter(|(e, _)| *e != ext && !(ext == "jpeg" && *e == "jpg"))
        .map(|(e, l)| Target { ext: e.to_string(), label: l.to_string() })
        .collect()
}

/// Where the result goes: next to the original, "name (1).ext" if taken,
/// Downloads when the original's folder is read-only.
fn output_path(src: &Path, to: &str) -> PathBuf {
    let stem = src.file_stem().and_then(|s| s.to_str()).unwrap_or("converted").to_string();
    output_named(src, &stem, to)
}

/// Like output_path, with a chosen name: "plans (English)" → "plans (English).txt".
pub(crate) fn output_named(src: &Path, stem: &str, to: &str) -> PathBuf {
    let mut dir = src.parent().map(Path::to_path_buf).unwrap_or_else(platform::home_dir);
    let probe = dir.join(".putshi-write-test");
    if std::fs::write(&probe, b"").is_err() {
        dir = platform::home_dir().join("Downloads");
    } else {
        let _ = std::fs::remove_file(&probe);
    }
    let mut out = dir.join(format!("{stem}.{to}"));
    let mut n = 1;
    while out.exists() {
        out = dir.join(format!("{stem} ({n}).{to}"));
        n += 1;
    }
    out
}

/// Converts `src` to the `to` extension; returns the new file's path.
pub fn convert(src: &str, to: &str) -> Result<String, String> {
    let src = Path::new(src);
    if !src.is_file() {
        return Err(format!("Can't find {}.", src.display()));
    }
    let to = to.trim_start_matches('.').to_lowercase();
    let from = ext_of(src);
    let out = output_path(src, &to);

    let image_in = IMAGE_IN.contains(&from.as_str()) || WIC_IN.contains(&from.as_str());
    let result = if image_in {
        image(src, &from, &to, &out)
    } else if VIDEO_IN.contains(&from.as_str()) || AUDIO_IN.contains(&from.as_str()) {
        media(src, &to, &out)
    } else if WORD_IN.contains(&from.as_str()) || from == "pdf" || EXCEL_IN.contains(&from.as_str()) || PPT_IN.contains(&from.as_str()) {
        office(src, &from, &to, &out)
    } else {
        Err(format!("Putshi doesn't know how to convert .{from} files yet; ask in the chat instead."))
    };
    match result {
        Ok(()) if out.exists() => Ok(out.display().to_string()),
        Ok(()) => Err("The converter finished but no file came out.".into()),
        Err(e) => {
            let _ = std::fs::remove_file(&out);
            Err(e)
        }
    }
}

// ── Images ───────────────────────────────────────────────────────────────────

pub(crate) fn load_image(src: &Path, from: &str) -> Result<image::DynamicImage, String> {
    if WIC_IN.contains(&from) {
        return wic::decode(src);
    }
    image::open(src).map_err(|e| format!("Couldn't read the picture: {e}"))
}

fn image(src: &Path, from: &str, to: &str, out: &Path) -> Result<(), String> {
    let img = load_image(src, from)?;
    match to {
        "jpg" | "jpeg" => {
            let rgb = flatten(&img);
            let file = std::fs::File::create(out).map_err(|e| e.to_string())?;
            let mut enc = image::codecs::jpeg::JpegEncoder::new_with_quality(std::io::BufWriter::new(file), 90);
            enc.encode_image(&rgb).map_err(|e| e.to_string())
        }
        "pdf" => pdf_from_image(&img, out),
        "ico" => {
            // Icons top out at 256 × 256.
            let side = img.width().max(img.height()).min(256);
            let icon = img.resize(side, side, image::imageops::FilterType::Lanczos3);
            icon.save_with_format(out, image::ImageFormat::Ico).map_err(|e| e.to_string())
        }
        "bmp" => image::DynamicImage::ImageRgb8(flatten(&img))
            .save_with_format(out, image::ImageFormat::Bmp)
            .map_err(|e| e.to_string()),
        other => {
            let format = image::ImageFormat::from_extension(other).ok_or(format!("Can't write .{other} pictures."))?;
            img.save_with_format(out, format).map_err(|e| e.to_string())
        }
    }
}

/// Transparent pixels on white, for formats without transparency.
fn flatten(img: &image::DynamicImage) -> image::RgbImage {
    let rgba = img.to_rgba8();
    let mut rgb = image::RgbImage::new(rgba.width(), rgba.height());
    for (x, y, p) in rgba.enumerate_pixels() {
        let a = p[3] as u32;
        let mix = |c: u8| ((c as u32 * a + 255 * (255 - a)) / 255) as u8;
        rgb.put_pixel(x, y, image::Rgb([mix(p[0]), mix(p[1]), mix(p[2])]));
    }
    rgb
}

/// A one-page PDF with the picture filling an A4-proportioned page.
fn pdf_from_image(img: &image::DynamicImage, out: &Path) -> Result<(), String> {
    let rgb = flatten(img);
    let (w, h) = (rgb.width(), rgb.height());
    let mut jpeg = Vec::new();
    image::codecs::jpeg::JpegEncoder::new_with_quality(&mut jpeg, 90)
        .encode_image(&rgb)
        .map_err(|e| e.to_string())?;
    // Page in points: the long side 842 pt (A4), keeping the picture's shape.
    let (pw, ph) = if w >= h { (842.0, 842.0 * h as f64 / w as f64) } else { (842.0 * w as f64 / h as f64, 842.0) };
    let content = format!("q {pw:.2} 0 0 {ph:.2} 0 0 cm /Im0 Do Q");
    let mut pdf: Vec<u8> = b"%PDF-1.4\n%\xE2\xE3\xCF\xD3\n".to_vec();
    let mut offsets = Vec::new();
    let mut obj = |pdf: &mut Vec<u8>, body: &[u8]| {
        offsets.push(pdf.len());
        pdf.extend_from_slice(format!("{} 0 obj\n", offsets.len()).as_bytes());
        pdf.extend_from_slice(body);
        pdf.extend_from_slice(b"\nendobj\n");
    };
    obj(&mut pdf, b"<< /Type /Catalog /Pages 2 0 R >>");
    obj(&mut pdf, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>");
    obj(
        &mut pdf,
        format!(
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {pw:.2} {ph:.2}] /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>"
        )
        .as_bytes(),
    );
    let mut image_obj = format!(
        "<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length {} >>\nstream\n",
        jpeg.len()
    )
    .into_bytes();
    image_obj.extend_from_slice(&jpeg);
    image_obj.extend_from_slice(b"\nendstream");
    obj(&mut pdf, &image_obj);
    let mut contents = format!("<< /Length {} >>\nstream\n", content.len()).into_bytes();
    contents.extend_from_slice(content.as_bytes());
    contents.extend_from_slice(b"\nendstream");
    obj(&mut pdf, &contents);
    let xref = pdf.len();
    pdf.extend_from_slice(format!("xref\n0 {}\n0000000000 65535 f \n", offsets.len() + 1).as_bytes());
    for o in &offsets {
        pdf.extend_from_slice(format!("{o:010} 00000 n \n").as_bytes());
    }
    pdf.extend_from_slice(format!("trailer\n<< /Size {} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n", offsets.len() + 1).as_bytes());
    std::fs::write(out, pdf).map_err(|e| e.to_string())
}

// ── Office documents ─────────────────────────────────────────────────────────

fn ps_quote(p: &Path) -> String {
    format!("'{}'", p.display().to_string().replace('\'', "''"))
}

fn powershell(script: &str) -> Result<(), String> {
    let mut cmd = Command::new("powershell");
    cmd.args(["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script]);
    platform::no_console(&mut cmd);
    let out = cmd.output().map_err(|e| e.to_string())?;
    if out.status.success() {
        Ok(())
    } else {
        let err = String::from_utf8_lossy(&out.stderr);
        Err(err.lines().find(|l| !l.trim().is_empty()).unwrap_or("Office couldn't do it.").trim().to_string())
    }
}

fn office(src: &Path, from: &str, to: &str, out: &Path) -> Result<(), String> {
    let s = ps_quote(src);
    let o = ps_quote(out);
    // Office's own save formats.
    let script = if WORD_IN.contains(&from) || from == "pdf" {
        let fmt = match to {
            "pdf" => 17,
            "docx" => 16,
            "txt" => 2,
            "rtf" => 6,
            "odt" => 23,
            _ => return libreoffice(src, to, out),
        };
        format!(
            "$ErrorActionPreference='Stop'; $w=New-Object -ComObject Word.Application; $w.Visible=$false; $w.DisplayAlerts=0; \
             try {{ $d=$w.Documents.Open({s}, $false, $true); $d.SaveAs2({o}, {fmt}); $d.Close($false) }} finally {{ $w.Quit() }}"
        )
    } else if EXCEL_IN.contains(&from) {
        let action = match to {
            "pdf" => format!("$b.ExportAsFixedFormat(0, {o})"),
            "xlsx" => format!("$b.SaveAs({o}, 51)"),
            "csv" => format!("$b.SaveAs({o}, 6)"),
            "ods" => format!("$b.SaveAs({o}, 60)"),
            _ => return libreoffice(src, to, out),
        };
        format!(
            "$ErrorActionPreference='Stop'; $e=New-Object -ComObject Excel.Application; $e.Visible=$false; $e.DisplayAlerts=$false; \
             try {{ $b=$e.Workbooks.Open({s}); {action}; $b.Close($false) }} finally {{ $e.Quit() }}"
        )
    } else {
        let fmt = match to {
            "pdf" => 32,
            "pptx" => 24,
            "png" => 18,
            _ => return libreoffice(src, to, out),
        };
        format!(
            "$ErrorActionPreference='Stop'; $p=New-Object -ComObject PowerPoint.Application; \
             try {{ $pr=$p.Presentations.Open({s}, $true, $false, $false); $pr.SaveAs({o}, {fmt}); $pr.Close() }} finally {{ $p.Quit() }}"
        )
    };
    match powershell(&script) {
        Ok(()) => Ok(()),
        Err(office_err) => libreoffice(src, to, out).map_err(|lo_err| {
            if lo_err.contains("isn't installed") {
                format!("Needs Microsoft Office or LibreOffice. Office said: {office_err}")
            } else {
                lo_err
            }
        }),
    }
}

fn libreoffice(src: &Path, to: &str, out: &Path) -> Result<(), String> {
    let exe = platform::find_on_path("soffice").or_else(|| {
        let p = PathBuf::from(r"C:\Program Files\LibreOffice\program\soffice.exe");
        p.exists().then_some(p)
    });
    let Some(exe) = exe else { return Err("LibreOffice isn't installed.".into()) };
    let tmp = std::env::temp_dir().join(format!("putshi-convert-{}", std::process::id()));
    let _ = std::fs::create_dir_all(&tmp);
    let mut cmd = Command::new(exe);
    cmd.args(["--headless", "--convert-to", to, "--outdir"]).arg(&tmp).arg(src);
    platform::no_console(&mut cmd);
    let status = cmd.status().map_err(|e| e.to_string())?;
    let made = tmp.join(format!("{}.{to}", src.file_stem().and_then(|s| s.to_str()).unwrap_or("out")));
    if !status.success() || !made.exists() {
        return Err("LibreOffice couldn't convert it.".into());
    }
    std::fs::rename(&made, out)
        .or_else(|_| std::fs::copy(&made, out).map(|_| ()))
        .map_err(|e| e.to_string())
}

// ── Audio and video ──────────────────────────────────────────────────────────

pub fn ffmpeg_path() -> Option<PathBuf> {
    platform::find_on_path("ffmpeg").or_else(|| {
        // winget puts a link here, and PATH isn't refreshed until a new login.
        let link = std::env::var_os("LOCALAPPDATA")
            .map(PathBuf::from)?
            .join(r"Microsoft\WinGet\Links\ffmpeg.exe");
        link.exists().then_some(link)
    })
}

/// Installs ffmpeg with winget (the card's "Install ffmpeg" button).
pub fn install_ffmpeg() -> Result<(), String> {
    let mut cmd = Command::new("winget");
    cmd.args([
        "install", "--id", "Gyan.FFmpeg", "-e", "--silent",
        "--accept-source-agreements", "--accept-package-agreements",
    ]);
    platform::no_console(&mut cmd);
    let status = cmd.status().map_err(|e| format!("winget isn't available: {e}"))?;
    if status.success() || ffmpeg_path().is_some() {
        Ok(())
    } else {
        Err("winget couldn't install ffmpeg.".into())
    }
}

fn media(src: &Path, to: &str, out: &Path) -> Result<(), String> {
    let Some(ffmpeg) = ffmpeg_path() else {
        return Err("NEEDS_FFMPEG".into());
    };
    let mut cmd = Command::new(ffmpeg);
    cmd.arg("-y").arg("-i").arg(src);
    match to {
        "mp3" => {
            cmd.args(["-vn", "-b:a", "192k"]);
        }
        "m4a" => {
            cmd.args(["-vn", "-c:a", "aac", "-b:a", "192k"]);
        }
        "wav" | "flac" | "ogg" => {
            cmd.arg("-vn");
        }
        "gif" => {
            cmd.args(["-vf", "fps=12,scale=640:-1:flags=lanczos", "-loop", "0"]);
        }
        "mp4" => {
            cmd.args(["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-movflags", "+faststart"]);
        }
        _ => {}
    }
    cmd.arg(out);
    platform::no_console(&mut cmd);
    let output = cmd.output().map_err(|e| e.to_string())?;
    if output.status.success() {
        Ok(())
    } else {
        let err = String::from_utf8_lossy(&output.stderr);
        Err(err.lines().rev().find(|l| !l.trim().is_empty()).unwrap_or("ffmpeg failed.").trim().to_string())
    }
}

// ── HEIC and friends, read by Windows (WIC) ──────────────────────────────────

#[cfg(windows)]
mod wic {
    use std::path::Path;

    use windows::core::HSTRING;
    use windows::Win32::Graphics::Imaging::{
        CLSID_WICImagingFactory, GUID_WICPixelFormat32bppRGBA, IWICImagingFactory, WICBitmapDitherTypeNone,
        WICBitmapPaletteTypeCustom, WICDecodeMetadataCacheOnDemand,
    };
    use windows::Win32::System::Com::{CoCreateInstance, CoInitializeEx, CLSCTX_INPROC_SERVER, COINIT_MULTITHREADED};

    pub fn decode(path: &Path) -> Result<image::DynamicImage, String> {
        unsafe {
            let _ = CoInitializeEx(None, COINIT_MULTITHREADED);
            let factory: IWICImagingFactory =
                CoCreateInstance(&CLSID_WICImagingFactory, None, CLSCTX_INPROC_SERVER).map_err(|e| e.message().to_string())?;
            let decoder = factory
                .CreateDecoderFromFilename(
                    &HSTRING::from(path.as_os_str()),
                    None,
                    windows::Win32::Foundation::GENERIC_READ,
                    WICDecodeMetadataCacheOnDemand,
                )
                .map_err(|_| {
                    "Windows can't read this photo. For iPhone HEIC photos, install “HEIF Image Extensions” from the Microsoft Store."
                        .to_string()
                })?;
            let frame = decoder.GetFrame(0).map_err(|e| e.message().to_string())?;
            let converter = factory.CreateFormatConverter().map_err(|e| e.message().to_string())?;
            converter
                .Initialize(&frame, &GUID_WICPixelFormat32bppRGBA, WICBitmapDitherTypeNone, None, 0.0, WICBitmapPaletteTypeCustom)
                .map_err(|e| e.message().to_string())?;
            let (mut w, mut h) = (0u32, 0u32);
            converter.GetSize(&mut w, &mut h).map_err(|e| e.message().to_string())?;
            let mut buf = vec![0u8; (w * h * 4) as usize];
            converter.CopyPixels(std::ptr::null(), w * 4, &mut buf).map_err(|e| e.message().to_string())?;
            image::RgbaImage::from_raw(w, h, buf)
                .map(image::DynamicImage::ImageRgba8)
                .ok_or_else(|| "Couldn't read the photo.".to_string())
        }
    }
}

#[cfg(not(windows))]
mod wic {
    pub fn decode(_path: &std::path::Path) -> Result<image::DynamicImage, String> {
        Err("HEIC photos need Windows.".into())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn png_to_jpg_pdf_ico_webp() {
        let dir = std::env::temp_dir().join(format!("putshi-conv-test-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let src = dir.join("pic.png");
        let mut img = image::RgbaImage::new(300, 200);
        for (x, y, p) in img.enumerate_pixels_mut() {
            *p = image::Rgba([(x % 256) as u8, (y % 256) as u8, 128, if x < 20 { 0 } else { 255 }]);
        }
        img.save(&src).unwrap();
        for to in ["jpg", "pdf", "ico", "webp", "bmp", "png"] {
            let out = convert(src.to_str().unwrap(), to).unwrap();
            let bytes = std::fs::read(&out).unwrap();
            assert!(bytes.len() > 100, "{to} too small");
            if to == "pdf" {
                assert!(bytes.starts_with(b"%PDF-1.4"));
            }
        }
        // Converting to png again doesn't overwrite: "pic (1).png".
        assert!(dir.join("pic (1).png").exists());
        assert!(targets(src.to_str().unwrap()).iter().all(|t| t.ext != "png"));
        std::fs::remove_dir_all(&dir).unwrap();
    }
}
