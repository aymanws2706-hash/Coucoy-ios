// Personal build: more things to do with a file or with what's on screen —
// translate (selected text or a whole file), summarize, resize pictures,
// compress and merge PDFs, read the text in a screenshot (Windows' own OCR,
// offline), and the screenshot hotkey itself.

use std::path::{Path, PathBuf};
use std::time::Duration;

use serde_json::{json, Value};

use crate::convert;

const FAST_MODEL: &str = "claude-haiku-4-5";
const IMAGE_IN: &[&str] = &["png", "jpg", "jpeg", "webp", "gif", "bmp", "tif", "tiff", "heic", "heif", "avif"];
const OFFICE_IN: &[&str] = &["doc", "docx", "rtf", "odt", "xls", "xlsx", "ods", "ppt", "pptx", "odp"];

/// One question to Claude, the answer's text.
async fn ask(system: &str, content: Vec<Value>, max_tokens: u32) -> Result<String, String> {
    let key = crate::secrets::get("anthropic-api-key").ok_or("Add your Claude key in Settings first.")?;
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(180))
        .build()
        .map_err(|e| e.to_string())?;
    let resp = client
        .post("https://api.anthropic.com/v1/messages")
        .header("x-api-key", key)
        .header("anthropic-version", "2023-06-01")
        .json(&json!({
            "model": FAST_MODEL,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{ "role": "user", "content": content }],
        }))
        .send()
        .await
        .map_err(|e| format!("Couldn't reach Claude: {e}"))?;
    let status = resp.status();
    let v: Value = resp.json().await.map_err(|e| e.to_string())?;
    if !status.is_success() {
        let msg = v.pointer("/error/message").and_then(Value::as_str).unwrap_or("unknown error");
        return Err(format!("Claude API {status}: {msg}"));
    }
    Ok(v.get("content")
        .and_then(Value::as_array)
        .map(|b| b.iter().filter_map(|x| x.get("text").and_then(Value::as_str)).collect::<Vec<_>>().join(""))
        .unwrap_or_default()
        .trim()
        .to_string())
}

// ── Translate ────────────────────────────────────────────────────────────────

pub async fn translate_text(text: &str, to: &str) -> Result<String, String> {
    if text.trim().is_empty() {
        return Err("Nothing to translate: select some text first.".into());
    }
    let system = format!(
        "Translate the user's text into {to}. Keep the tone, names, numbers and line breaks. \
         If it is already in {to}, translate it into English instead. Answer with the translation only."
    );
    ask(&system, vec![json!({ "type": "text", "text": text })], 4000).await
}

/// The file as something Claude can read: Office files go through PDF first.
fn readable(path: &str) -> Result<(Value, Option<String>), String> {
    let ext = convert::ext_of(Path::new(path));
    let (source, temp) = if OFFICE_IN.contains(&ext.as_str()) {
        let pdf = convert::convert(path, "pdf")?;
        (pdf.clone(), Some(pdf))
    } else {
        (path.to_string(), None)
    };
    let block = crate::claude::file_block(&source).ok_or("Putshi can't read this kind of file (PDF, Office, pictures and text work).")?;
    Ok((block, temp))
}

/// Translates a whole file; the result is saved as "name (Français).docx/.txt" next to it.
pub async fn translate_file(path: &str, to: &str) -> Result<String, String> {
    let (block, temp) = readable(path)?;
    let system = format!(
        "Translate the whole document into {to}. Keep its structure: headings, paragraphs, lists and tables \
         (tables as tab-separated lines). Answer with the translated text only, no comments."
    );
    let result = ask(&system, vec![block, json!({ "type": "text", "text": "Translate this." })], 16000).await;
    if let Some(t) = temp {
        let _ = std::fs::remove_file(t);
    }
    let text = result?;
    let src = Path::new(path);
    let stem = format!("{} ({to})", src.file_stem().and_then(|s| s.to_str()).unwrap_or("translated"));
    let txt = convert::output_named(src, &stem, "txt");
    std::fs::write(&txt, text).map_err(|e| e.to_string())?;
    // A Word file comes back as a Word file when Word (or LibreOffice) is there.
    let ext = convert::ext_of(src);
    if ["doc", "docx", "odt", "rtf", "pdf"].contains(&ext.as_str()) {
        let txt_s = txt.display().to_string();
        if let Ok(docx) = tokio::task::spawn_blocking(move || convert::convert(&txt_s, "docx")).await.map_err(|e| e.to_string())? {
            let _ = std::fs::remove_file(&txt);
            return Ok(docx);
        }
    }
    Ok(txt.display().to_string())
}

pub async fn summarize_file(path: &str) -> Result<String, String> {
    let (block, temp) = readable(path)?;
    let result = ask(
        "Summarize the document for a busy person: one line saying what it is, then the 3–6 points that matter \
         (dates, amounts, decisions, what's asked of the reader). Same language as the document. Plain text with • bullets.",
        vec![block, json!({ "type": "text", "text": "Summarize this." })],
        1200,
    )
    .await;
    if let Some(t) = temp {
        let _ = std::fs::remove_file(t);
    }
    result
}

// ── Pictures ─────────────────────────────────────────────────────────────────

/// Fits a picture inside `max` pixels (longest side); same format, "name (1920px).jpg".
pub fn resize_image(path: &str, max: u32) -> Result<String, String> {
    let src = Path::new(path);
    let ext = convert::ext_of(src);
    if !IMAGE_IN.contains(&ext.as_str()) {
        return Err("Only pictures can be resized.".into());
    }
    let img = convert::load_image(src, &ext)?;
    let out_ext = if ["heic", "heif", "avif", "tif", "tiff", "bmp", "gif"].contains(&ext.as_str()) { "jpg" } else { ext.as_str() };
    let resized = if img.width().max(img.height()) > max { img.resize(max, max, image::imageops::FilterType::Lanczos3) } else { img };
    let stem = format!("{} ({max}px)", src.file_stem().and_then(|s| s.to_str()).unwrap_or("picture"));
    let out = convert::output_named(src, &stem, out_ext);
    let result = if out_ext == "jpg" || out_ext == "jpeg" {
        let rgb = image::DynamicImage::ImageRgb8(resized.to_rgb8());
        let file = std::fs::File::create(&out).map_err(|e| e.to_string())?;
        let mut enc = image::codecs::jpeg::JpegEncoder::new_with_quality(std::io::BufWriter::new(file), 88);
        enc.encode_image(&rgb).map_err(|e| e.to_string())
    } else {
        resized.save(&out).map_err(|e| e.to_string())
    };
    result.map(|_| out.display().to_string())
}

// ── PDFs ─────────────────────────────────────────────────────────────────────

/// Ghostscript's command-line program, if installed.
fn ghostscript() -> Option<PathBuf> {
    for root in [r"C:\Program Files\gs", r"C:\Program Files (x86)\gs"] {
        let Ok(entries) = std::fs::read_dir(root) else { continue };
        let mut dirs: Vec<_> = entries.flatten().map(|e| e.path()).collect();
        dirs.sort();
        for d in dirs.iter().rev() {
            for exe in ["gswin64c.exe", "gswin32c.exe"] {
                let p = d.join("bin").join(exe);
                if p.is_file() {
                    return Some(p);
                }
            }
        }
    }
    None
}

pub fn install_ghostscript() -> Result<(), String> {
    let mut cmd = std::process::Command::new("winget");
    cmd.args([
        "install", "--id", "ArtifexSoftware.GhostScript", "-e", "--silent",
        "--accept-package-agreements", "--accept-source-agreements",
    ]);
    crate::platform::no_console(&mut cmd);
    let out = cmd.output().map_err(|e| format!("Couldn't run winget: {e}"))?;
    if ghostscript().is_some() {
        Ok(())
    } else {
        Err(format!("Ghostscript didn't install: {}", String::from_utf8_lossy(&out.stdout).lines().last().unwrap_or("")))
    }
}

/// Makes a PDF smaller (pictures at 150 dpi). "NEEDS_GHOSTSCRIPT" when missing.
pub fn compress_pdf(path: &str) -> Result<String, String> {
    let src = Path::new(path);
    if convert::ext_of(src) != "pdf" {
        return Err("Only PDFs can be compressed.".into());
    }
    let gs = ghostscript().ok_or("NEEDS_GHOSTSCRIPT")?;
    let stem = format!("{} (small)", src.file_stem().and_then(|s| s.to_str()).unwrap_or("document"));
    let out = convert::output_named(src, &stem, "pdf");
    let mut cmd = std::process::Command::new(gs);
    cmd.args(["-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.5", "-dPDFSETTINGS=/ebook", "-dNOPAUSE", "-dQUIET", "-dBATCH"])
        .arg(format!("-sOutputFile={}", out.display()))
        .arg(src);
    crate::platform::no_console(&mut cmd);
    let status = cmd.output().map_err(|e| e.to_string())?;
    if !out.exists() {
        return Err(format!("Ghostscript failed: {}", String::from_utf8_lossy(&status.stderr).lines().next().unwrap_or("")));
    }
    let before = std::fs::metadata(src).map(|m| m.len()).unwrap_or(0);
    let after = std::fs::metadata(&out).map(|m| m.len()).unwrap_or(0);
    if after >= before && before > 0 {
        let _ = std::fs::remove_file(&out);
        return Err("It's already as small as it gets.".into());
    }
    Ok(out.display().to_string())
}

/// Puts several PDFs into one, in the order given: "first name (merged).pdf".
pub fn merge_pdfs(paths: &[String]) -> Result<String, String> {
    use lopdf::{Document, Object, ObjectId};
    use std::collections::BTreeMap;

    if paths.len() < 2 {
        return Err("Drop two PDFs or more to merge them.".into());
    }
    let mut max_id = 1;
    let mut pages: BTreeMap<ObjectId, Object> = BTreeMap::new();
    let mut objects: BTreeMap<ObjectId, Object> = BTreeMap::new();
    let mut merged = Document::with_version("1.5");
    for p in paths {
        let mut doc = Document::load(p).map_err(|e| format!("Couldn't read {}: {e}", Path::new(p).display()))?;
        doc.renumber_objects_with(max_id);
        max_id = doc.max_id + 1;
        for (_, id) in doc.get_pages() {
            if let Ok(obj) = doc.get_object(id) {
                pages.insert(id, obj.to_owned());
            }
        }
        objects.extend(doc.objects);
    }
    let mut catalog: Option<(ObjectId, Object)> = None;
    let mut pages_root: Option<(ObjectId, Object)> = None;
    for (id, obj) in objects {
        match obj.type_name().unwrap_or("") {
            "Catalog" => {
                if catalog.is_none() {
                    catalog = Some((id, obj));
                }
            }
            "Pages" => {
                if let Ok(dict) = obj.as_dict() {
                    let mut dict = dict.clone();
                    if let Some((_, ref old)) = pages_root {
                        if let Ok(old) = old.as_dict() {
                            dict.extend(old);
                        }
                    }
                    pages_root = Some((pages_root.map(|(i, _)| i).unwrap_or(id), Object::Dictionary(dict)));
                }
            }
            "Page" | "Outlines" | "Outline" => {}
            _ => {
                merged.objects.insert(id, obj);
            }
        }
    }
    let (pages_id, pages_obj) = pages_root.ok_or("No pages found.")?;
    let (catalog_id, catalog_obj) = catalog.ok_or("Not a valid PDF.")?;
    for (id, obj) in &pages {
        if let Ok(dict) = obj.as_dict() {
            let mut dict = dict.clone();
            dict.set("Parent", pages_id);
            merged.objects.insert(*id, Object::Dictionary(dict));
        }
    }
    if let Ok(dict) = pages_obj.as_dict() {
        let mut dict = dict.clone();
        dict.set("Count", pages.len() as u32);
        dict.set("Kids", pages.keys().map(|id| Object::Reference(*id)).collect::<Vec<_>>());
        merged.objects.insert(pages_id, Object::Dictionary(dict));
    }
    if let Ok(dict) = catalog_obj.as_dict() {
        let mut dict = dict.clone();
        dict.set("Pages", pages_id);
        dict.remove(b"Outlines");
        merged.objects.insert(catalog_id, Object::Dictionary(dict));
    }
    merged.trailer.set("Root", catalog_id);
    merged.max_id = merged.objects.len() as u32;
    merged.renumber_objects();
    merged.compress();
    let first = Path::new(&paths[0]);
    let stem = format!("{} (merged)", first.file_stem().and_then(|s| s.to_str()).unwrap_or("document"));
    let out = convert::output_named(first, &stem, "pdf");
    merged.save(&out).map_err(|e| e.to_string())?;
    Ok(out.display().to_string())
}

// ── Screenshot text (OCR) ────────────────────────────────────────────────────

#[cfg(windows)]
pub fn ocr(path: &str) -> Result<String, String> {
    use windows::Graphics::Imaging::{BitmapPixelFormat, SoftwareBitmap};
    use windows::Media::Ocr::OcrEngine;
    use windows::Storage::Streams::DataWriter;

    let src = Path::new(path);
    let img = convert::load_image(src, &convert::ext_of(src))?;
    // Windows' OCR reads up to about 10 000 px; keep well inside.
    let max = OcrEngine::MaxImageDimension().unwrap_or(4096);
    let img = if img.width().max(img.height()) > max { img.resize(max, max, image::imageops::FilterType::Triangle) } else { img };
    let mut bgra = img.to_rgba8();
    for p in bgra.pixels_mut() {
        p.0.swap(0, 2);
    }
    let (w, h) = (bgra.width() as i32, bgra.height() as i32);
    let map = |e: windows::core::Error| e.message().to_string();
    let writer = DataWriter::new().map_err(map)?;
    writer.WriteBytes(bgra.as_raw()).map_err(map)?;
    let buffer = writer.DetachBuffer().map_err(map)?;
    let bitmap = SoftwareBitmap::CreateCopyFromBuffer(&buffer, BitmapPixelFormat::Bgra8, w, h).map_err(map)?;
    let engine = OcrEngine::TryCreateFromUserProfileLanguages().map_err(|_| "No text-recognition language is installed in Windows.".to_string())?;
    let result = engine.RecognizeAsync(&bitmap).map_err(map)?.get().map_err(map)?;
    let lines = result.Lines().map_err(map)?;
    let mut out = Vec::new();
    for line in lines {
        out.push(line.Text().map_err(map)?.to_string());
    }
    let text = out.join("\n");
    if text.trim().is_empty() {
        Err("No text found in the picture.".into())
    } else {
        Ok(text)
    }
}

#[cfg(not(windows))]
pub fn ocr(_path: &str) -> Result<String, String> {
    Err("Reading text from pictures is a Windows feature.".into())
}

// ── Hotkeys: screenshot, translate the selection ─────────────────────────────

/// Saves the picture on the clipboard as a PNG; returns its path.
pub fn clipboard_image_to_file(app: &tauri::AppHandle) -> Option<String> {
    use tauri_plugin_clipboard_manager::ClipboardExt;
    let img = app.clipboard().read_image().ok()?;
    let (w, h) = (img.width(), img.height());
    let buf = image::RgbaImage::from_raw(w, h, img.rgba().to_vec())?;
    let dir = crate::platform::local_dir().join("snips");
    let _ = std::fs::create_dir_all(&dir);
    // Keep the last 20.
    if let Ok(entries) = std::fs::read_dir(&dir) {
        let mut files: Vec<_> = entries.flatten().map(|e| e.path()).collect();
        files.sort();
        while files.len() >= 20 {
            let _ = std::fs::remove_file(files.remove(0));
        }
    }
    let t = crate::platform::local_time();
    let path = dir.join(format!(
        "Screenshot {:04}-{:02}-{:02} {:02}.{:02}.{:02}.png",
        t.year, t.month, t.day, t.hour, t.minute, t.second
    ));
    buf.save(&path).ok()?;
    Some(path.display().to_string())
}

/// Opens Windows' own snipping bar; when a new picture lands on the clipboard
/// (within a minute), tells the island.
pub fn start_snip(app: &tauri::AppHandle) {
    use tauri::Emitter;
    let before = crate::desk::clipboard_seq();
    let mut cmd = std::process::Command::new("explorer.exe");
    cmd.arg("ms-screenclip:");
    let _ = cmd.spawn();
    let app = app.clone();
    std::thread::spawn(move || {
        for _ in 0..240 {
            std::thread::sleep(Duration::from_millis(250));
            if crate::desk::clipboard_seq() != before {
                std::thread::sleep(Duration::from_millis(200));
                if let Some(path) = clipboard_image_to_file(&app) {
                    let _ = app.emit("snip", path);
                }
                return;
            }
        }
    });
}

/// Copies whatever is selected in the app in front (Ctrl+C), reads it, and
/// puts the clipboard back the way it was.
#[cfg(windows)]
pub fn copy_selection(app: &tauri::AppHandle) -> Option<String> {
    use tauri_plugin_clipboard_manager::ClipboardExt;
    use windows::Win32::UI::Input::KeyboardAndMouse::{
        SendInput, INPUT, INPUT_0, INPUT_KEYBOARD, KEYBDINPUT, KEYEVENTF_KEYUP, VIRTUAL_KEY, VK_CONTROL, VK_MENU, VK_SHIFT,
    };
    let previous = app.clipboard().read_text().ok();
    let before = crate::desk::clipboard_seq();
    let key = |vk: VIRTUAL_KEY, up: bool| INPUT {
        r#type: INPUT_KEYBOARD,
        Anonymous: INPUT_0 {
            ki: KEYBDINPUT { wVk: vk, dwFlags: if up { KEYEVENTF_KEYUP } else { Default::default() }, ..Default::default() },
        },
    };
    // The hotkey's own Ctrl/Alt/Shift may still be down: let them go first.
    std::thread::sleep(Duration::from_millis(120));
    let c = VIRTUAL_KEY(b'C' as u16);
    unsafe {
        SendInput(&[key(VK_MENU, true), key(VK_SHIFT, true)], std::mem::size_of::<INPUT>() as i32);
        SendInput(&[key(VK_CONTROL, false), key(c, false), key(c, true), key(VK_CONTROL, true)], std::mem::size_of::<INPUT>() as i32);
    }
    for _ in 0..20 {
        std::thread::sleep(Duration::from_millis(25));
        if crate::desk::clipboard_seq() != before {
            break;
        }
    }
    if crate::desk::clipboard_seq() == before {
        return None;
    }
    let text = app.clipboard().read_text().ok();
    if let Some(prev) = previous {
        let _ = app.clipboard().write_text(prev);
    }
    text.filter(|t| !t.trim().is_empty())
}

#[cfg(not(windows))]
pub fn copy_selection(_app: &tauri::AppHandle) -> Option<String> {
    None
}
