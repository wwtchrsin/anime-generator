#!/usr/bin/env python3

import os
import subprocess
import textwrap
from pathlib import Path
import shutil
import os
from PIL import Image, ImageDraw, ImageFont
from piper import PiperVoice
import wave
import time
import uuid
import json

VOICES = {
    "irina": PiperVoice.load("piper-voices/irina/ru_RU-irina-medium.onnx")
}

SCRIPT_DIR = Path("scripts")
OUTPUT_DIR = Path("video-output")
CHARACTER_SPRITE_DIR = Path("images") / "characters"
BACKGROUND_DIR = Path("images") / "backgrounds"
VIDEO_W, VIDEO_H = 1280, 720
FPS = 24
AUDIO_LEADING_GAP = 0.4
AUDIO_TRAILING_GAP = 0.8

if OUTPUT_DIR.exists():
    shutil.rmtree(OUTPUT_DIR)
    
os.mkdir(OUTPUT_DIR)

with open(str(SCRIPT_DIR / "characters.json"), encoding="utf-8") as f:
    CHARACTERS = json.load(f)
    
with open(str(SCRIPT_DIR / "dialogues.json"), encoding="utf-8") as f:
    DIALOGUES = json.load(f)

DIALOG_BOX = {
    "height":      180,
    "margin":      30,
    "padding":     20,
    "bg_color":    (10, 10, 30, 200),
    "border_color": (180, 180, 255, 220),
    "border_width": 2,
    "text_color":  (255, 255, 255),
    "name_size":   28,
    "text_size":   24,
    "text_wrap":   55, 
}

SPRITE = {
    "height_ratio": 0.85,
    "bottom_offset": 160,
    "side_margin":  40,
}


def load_font(size: int) -> ImageFont.FreeTypeFont:
    """Загружает системный шрифт с поддержкой кириллицы."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def make_background(bg_path: Path) -> Image.Image:
    """Загружает и масштабирует фон до размера видео."""
    if bg_path.exists():
        img = Image.open(bg_path).convert("RGBA")
    else:
        # fallback
        img = Image.new("RGBA", (VIDEO_W, VIDEO_H), (30, 30, 60, 255))
        draw = ImageDraw.Draw(img)
        for y in range(VIDEO_H):
            r = int(20 + y / VIDEO_H * 30)
            g = int(20 + y / VIDEO_H * 20)
            b = int(50 + y / VIDEO_H * 60)
            draw.line([(0, y), (VIDEO_W, y)], fill=(r, g, b, 255))
    return img.resize((VIDEO_W, VIDEO_H), Image.LANCZOS)


def paste_sprite(frame: Image.Image, sprite_path: Path, align: str) -> Image.Image:
    """Накладывает PNG спрайт персонажа на кадр."""
    if not sprite_path.exists():
        # fallback
        sprite = Image.new("RGBA", (200, 400), (200, 150, 150, 180))
        draw = ImageDraw.Draw(sprite)
        draw.rectangle([0, 0, 199, 399], outline=(255, 200, 200), width=3)
    else:
        sprite = Image.open(sprite_path).convert("RGBA")

    # scaling
    target_h = int(VIDEO_H * SPRITE["height_ratio"])
    ratio = target_h / sprite.height
    target_w = int(sprite.width * ratio)
    sprite = sprite.resize((target_w, target_h), Image.LANCZOS)

    # positioning
    y = VIDEO_H - target_h + SPRITE["bottom_offset"]
    if align == "left":
        x = SPRITE["side_margin"]
    else:
        x = VIDEO_W - target_w - SPRITE["side_margin"]

    frame.paste(sprite, (x, y), sprite)
    return frame


def draw_dialog_box(frame: Image.Image, character: str, text: str) -> Image.Image:
    """Рисует диалоговое окно с именем и текстом реплики."""
    cfg = DIALOG_BOX
    char_cfg = CHARACTERS[character]

    m   = cfg["margin"]
    box_x = m
    box_y = VIDEO_H - cfg["height"] - m
    box_w = VIDEO_W - m * 2
    box_h = cfg["height"]

    # creating background
    overlay = Image.new("RGBA", (VIDEO_W, VIDEO_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle(
        [box_x, box_y, box_x + box_w, box_y + box_h],
        radius=12,
        fill=cfg["bg_color"],
        outline=cfg["border_color"],
        width=cfg["border_width"],
    )
    frame = Image.alpha_composite(frame, overlay)
    
    draw = ImageDraw.Draw(frame)
    font_name = load_font(cfg["name_size"])
    font_text = load_font(cfg["text_size"])

    px = box_x + cfg["padding"]
    py = box_y + cfg["padding"]

    # character name
    draw.text((px, py), character, font=font_name, fill=tuple(char_cfg["name_color"]))
    py += cfg["name_size"] + 8

    # line text
    wrapped = textwrap.fill(text, width=cfg["text_wrap"])
    draw.text((px, py), wrapped, font=font_text, fill=cfg["text_color"])

    return frame


def generate_audio(line: dict, out_path: Path) -> float:
    char_cfg = CHARACTERS[line['character']]
    timestamp = int(time.time() * 1000)
    temp_path = OUTPUT_DIR / f"{timestamp}_{uuid.uuid4().hex[:8]}.wav"
    
    with wave.open(str(temp_path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(VOICES[char_cfg['voice']].config.sample_rate)
        
        for audio_bytes in VOICES[char_cfg['voice']].synthesize(line['text']):
            wav_file.writeframes(audio_bytes.audio_int16_bytes)
    
    subprocess.run([
        "ffmpeg", "-i", str(temp_path), "-af", 
        f"rubberband=pitch={char_cfg['voice_pitch']},atempo={char_cfg['voice_tempo']}",
        str(out_path)
    ], capture_output=True)
    
    os.remove(str(temp_path))
    
    # defining duration
    result = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(out_path),
    ], capture_output=True, text=True)
    
    return AUDIO_LEADING_GAP + float(result.stdout.strip()) + AUDIO_TRAILING_GAP


def make_frame(line: dict, bg: Image.Image) -> Image.Image:
    """Собирает один кадр: фон + спрайт + диалоговое окно."""
    frame = bg.copy()
    char_cfg = CHARACTERS[line['character']]
    image_path = CHARACTER_SPRITE_DIR / f"{line['character']}-{line['image']}.png"
    frame = paste_sprite(frame, image_path, line['position'])
    frame = draw_dialog_box(frame, line['character'], line['text'])
    return frame


def render_scene(idx: int, line: dict, bg: Image.Image, audio_path: Path, 
               duration: float,
               scene_path: Path):
    """Рендерит одну сцену (статичный кадр + аудио) в MP4."""
    frame = make_frame(line, bg)
    frame_path = OUTPUT_DIR / f"frame_{idx:03d}.png"
    frame.convert("RGB").save(str(frame_path))

    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(frame_path),
        "-i", str(audio_path),
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-t", str(duration),
        str(scene_path),
    ], check=True, capture_output=True)

    frame_path.unlink()


def concat_scenes(scene_paths: list[Path], output_path: Path):
    """Склеивает все сцены в один финальный файл."""
    list_file = OUTPUT_DIR / "concat_list.txt"
    with open(list_file, "w") as f:
        for p in scene_paths:
            f.write(f"file '{p.resolve()}'\n")

    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(output_path),
    ], check=True, capture_output=True)

    list_file.unlink()


def main():
    for dialogue_index, dialogue in enumerate(DIALOGUES):
        print(f"\n[*] Creating dialogue {dialogue_index+1}/{len(DIALOGUES)} ({dialogue['tag']})...\n")
        bg = make_background(BACKGROUND_DIR / f"{dialogue['background']}.jpg")

        scene_paths = []

        for idx, line in enumerate(dialogue['lines']):
            char_cfg = CHARACTERS[line['character']]
            
            print(f"  [{idx+1}/{len(dialogue['lines'])}] {char_cfg['name']}: {line['text'][:45]}...")

            audio_path = OUTPUT_DIR / f"{dialogue['tag']}_audio_{idx:03d}.wav"
            scene_path = OUTPUT_DIR / f"{dialogue['tag']}_scene_{idx:03d}.mp4"

            duration = generate_audio(line, audio_path)
            render_scene(idx, line, bg, audio_path, duration, scene_path)
            audio_path.unlink()

            scene_paths.append(scene_path)
            print(f"   Scene is ready")

        print("\n   Merging scenes...")
        final_path = OUTPUT_DIR / f"{dialogue['tag']}.mp4"
        concat_scenes(scene_paths, final_path)
        
        for p in scene_paths:
            p.unlink()

        print(f"\n Dialogue '{dialogue['tag']}' sucessfully created!")


if __name__ == "__main__":
    main()
