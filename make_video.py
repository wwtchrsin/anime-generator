#!/usr/bin/env python3

import os
import subprocess
from pathlib import Path
import shutil
import os
from PIL import Image, ImageDraw, ImageFont
from piper import PiperVoice
import wave
import time
import uuid
import json
import sys

PROJECT_NAME = "example"

if len(sys.argv) > 1:
    PROJECT_NAME = sys.argv[1]

DEFAULT_PROJECT_DIR = Path("projects") / "example"
PROJECT_DIR = Path("projects") / PROJECT_NAME
DEFAULT_SETTINGS_DIR = DEFAULT_PROJECT_DIR / Path("settings")
DEFAULT_SCRIPT_DIR = DEFAULT_PROJECT_DIR / Path("scripts")
DEFAULT_CHARACTER_SPRITE_DIR = DEFAULT_PROJECT_DIR / Path("images") / "characters"
DEFAULT_BACKGROUND_DIR = DEFAULT_PROJECT_DIR / Path("images") / "backgrounds"
SETTINGS_DIR = PROJECT_DIR / Path("settings")
SCRIPT_DIR = PROJECT_DIR / Path("scripts")
OUTPUT_DIR = PROJECT_DIR / Path("video-output")
CHARACTER_SPRITE_DIR = PROJECT_DIR / Path("images") / "characters"
BACKGROUND_DIR = PROJECT_DIR / Path("images") / "backgrounds"

if not PROJECT_DIR.exists():
    os.mkdir(PROJECT_DIR)

if OUTPUT_DIR.exists():
    shutil.rmtree(OUTPUT_DIR)
    
os.mkdir(OUTPUT_DIR)

with open(str(DEFAULT_SETTINGS_DIR / "general.json"), encoding="utf-8") as f:
    SETTINGS = json.load(f)
    
with open(str(DEFAULT_SETTINGS_DIR / "dialog-box.json"), encoding="utf-8") as f:
    DIALOG_BOX = json.load(f)
    
with open(str(DEFAULT_SETTINGS_DIR / "sprite.json"), encoding="utf-8") as f:
    SPRITE = json.load(f)

with open(str(DEFAULT_SCRIPT_DIR / "characters.json"), encoding="utf-8") as f:
    CHARACTERS = json.load(f)
    
with open(str(DEFAULT_SCRIPT_DIR / "dialogues.json"), encoding="utf-8") as f:
    DIALOGUES = json.load(f)

if (SETTINGS_DIR / "general.json").exists():
    with open(str(SETTINGS_DIR / "general.json"), encoding="utf-8") as f:
        SETTINGS = json.load(f)

if (SETTINGS_DIR / "dialog-box.json").exists():
    with open(str(SETTINGS_DIR / "dialog-box.json"), encoding="utf-8") as f:
        DIALOG_BOX = json.load(f)

if (SETTINGS_DIR / "sprite.json").exists():
    with open(str(SETTINGS_DIR / "sprite.json"), encoding="utf-8") as f:
        SPRITE = json.load(f)

if (SCRIPT_DIR / "characters.json").exists():
    with open(str(SCRIPT_DIR / "characters.json"), encoding="utf-8") as f:
        CHARACTERS = json.load(f)

if (SCRIPT_DIR / "dialogues.json").exists():
    with open(str(SCRIPT_DIR / "dialogues.json"), encoding="utf-8") as f:
        DIALOGUES = json.load(f)
    
VIDEO_W = SETTINGS["video_width"]
VIDEO_H = SETTINGS["video_height"]
VIDEO_AR = VIDEO_W / VIDEO_H

VOICES = {}

for charTag in CHARACTERS:
    voiceTag = CHARACTERS[charTag]["voice"]
    VOICES[charTag] = PiperVoice.load(f"piper-voices/{voiceTag}.onnx")

def load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def get_audio_delays(line: dict) -> tuple[float, float]:
    audio_delay = SETTINGS["audio_delay"]
    audio_pad = SETTINGS["audio_pad"]
    
    if line["delays"] == "start" or line["delays"] == "no":
        audio_pad = SETTINGS["audio_pad_min"]
        
    if line["delays"] == "end" or line["delays"] == "no":
        audio_delay = SETTINGS["audio_delay_min"]
    
    return (audio_delay, audio_pad)

def make_background(bg_path: Path) -> Image.Image:
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
    
    image_ar = img.width / img.height
    if image_ar > VIDEO_AR:
        temp_height = img.height
        temp_width = img.height * VIDEO_AR
        left = (img.width - temp_width) // 2
        top = 0
        right = temp_width + left
        bottom = temp_height
    else:
        temp_width = img.width
        temp_height = img.width / VIDEO_AR
        left = 0
        top = (img.height - temp_height) // 2
        right = temp_width
        bottom = temp_height + top
        
    cropped_img = img.crop((left, top, right, bottom))
    return cropped_img.resize((VIDEO_W, VIDEO_H), Image.LANCZOS)


def paste_sprite(frame: Image.Image, sprite_path: Path, align: str) -> Image.Image:
    if not sprite_path.exists():
        # fallback
        sprite = Image.new("RGBA", (200, 400), (200, 150, 150, 180))
        draw = ImageDraw.Draw(sprite)
        draw.rectangle([0, 0, 199, 399], outline=(255, 200, 200), width=3)
    else:
        sprite = Image.open(sprite_path).convert("RGBA")

    # scaling
    sprite_side_margin = int(SPRITE["side_margin"] * VIDEO_W)
    sprite_bottom_offset = int(SPRITE["bottom_offset"] * VIDEO_H)
    target_h = int(VIDEO_H * SPRITE["max_height"])
    ratio = target_h / sprite.height
    target_w = int(sprite.width * ratio)
    sprite = sprite.resize((target_w, target_h), Image.LANCZOS)

    # positioning
    y = VIDEO_H - target_h + sprite_bottom_offset
    if align == "left":
        x = sprite_side_margin
    else:
        x = VIDEO_W - target_w - sprite_side_margin

    frame.paste(sprite, (x, y), sprite)
    return frame


def auto_wrap(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
    words = text.split()
    lines = []
    curr_line = ""
    
    for word in words:
        upd_line = f"{curr_line} {word}".strip()
        bbox = font.getbbox(upd_line)
        width = bbox[2] - bbox[0]
        
        if width < max_width:
            curr_line = upd_line
        else:
            if curr_line:
                lines.append(curr_line)
            curr_line = word
        
    if curr_line:
        lines.append(curr_line)
    
    return "\n".join(lines)


def draw_dialog_box(frame: Image.Image, character: str, text: str) -> Image.Image:
    char_cfg = CHARACTERS[character]
    short_side = min(VIDEO_W, VIDEO_H)
    
    dialog_margin = int(DIALOG_BOX["margin"] * short_side)
    dialog_padding = int(DIALOG_BOX["padding"] * short_side)
    dialog_height = int(DIALOG_BOX["height"] * VIDEO_H)
    dialog_border_width = int(round(DIALOG_BOX["border_width"] * short_side))
    dialog_name_size = int(round(DIALOG_BOX["name_size"] * short_side))
    dialog_text_size = int(round(DIALOG_BOX["text_size"] * short_side))
    
    max_text_width = VIDEO_W - dialog_margin * 2 - dialog_padding * 2
    box_x = dialog_margin
    box_y = VIDEO_H - dialog_height - dialog_margin
    box_w = VIDEO_W - dialog_margin * 2
    box_h = dialog_height

    # creating background
    overlay = Image.new("RGBA", (VIDEO_W, VIDEO_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle(
        [box_x, box_y, box_x + box_w, box_y + box_h],
        radius=12,
        fill=tuple(DIALOG_BOX["bg_color"]),
        outline=tuple(DIALOG_BOX["border_color"]),
        width=dialog_border_width,
    )
    frame = Image.alpha_composite(frame, overlay)
    
    draw = ImageDraw.Draw(frame)
    font_name = load_font(dialog_name_size)
    font_text = load_font(dialog_text_size)

    px = box_x + dialog_padding
    py = box_y + dialog_padding

    # character name
    draw.text((px, py), char_cfg["name"], font=font_name, fill=tuple(char_cfg["name_color"]))
    py += dialog_name_size + 8

    # line text
    wrapped = auto_wrap(text, font_text, max_text_width)
    draw.text((px, py), wrapped, font=font_text, fill=tuple(DIALOG_BOX["text_color"]))

    return frame


def generate_audio(line: dict, out_path: Path) -> float:
    char_cfg = CHARACTERS[line['character']]
    timestamp = int(time.time() * 1000)
    temp_path = OUTPUT_DIR / f"{timestamp}_{uuid.uuid4().hex[:8]}.wav"
    
    with wave.open(str(temp_path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(VOICES[line['character']].config.sample_rate)
        
        for audio_bytes in VOICES[line['character']].synthesize(line['text']):
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
    
    audio_delay, audio_pad = get_audio_delays(line)
    
    return audio_delay + float(result.stdout.strip()) + audio_pad


def make_frame(line: dict, bg: Image.Image) -> Image.Image:
    frame = bg.copy()
    image_path = CHARACTER_SPRITE_DIR / line['character'] / f"{line['image']}.png"
    if not image_path.exists():
        image_path = DEFAULT_CHARACTER_SPRITE_DIR / line['character'] / f"{line['image']}.png"
    if not image_path.exists():
        exit("[!] Error: Sprite Not Found")
        
    frame = paste_sprite(frame, image_path, line['position'])
    frame = draw_dialog_box(frame, line['character'], line['text'])
    return frame


def render_scene(idx: int, line: dict, bg: Image.Image, audio_path: Path, 
               duration: float,
               scene_path: Path):
    
    audio_delay, audio_pad = get_audio_delays(line)
    
    frame = make_frame(line, bg)
    frame_path = OUTPUT_DIR / f"frame_{idx:03d}.png"
    frame.convert("RGB").save(str(frame_path))

    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1",
        "-r", str(SETTINGS["fps"]),
        "-i", str(frame_path),
        "-i", str(audio_path),
        "-af", f"adelay={int(audio_delay*1000)}|{int(audio_delay*1000)},apad=pad_dur={audio_pad}",
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
    print(f"\n[*] Working on project '{PROJECT_NAME}'...\n")
    for dialogue_index, dialogue in enumerate(DIALOGUES):
        print(f"\n[*] Creating dialogue {dialogue_index+1}/{len(DIALOGUES)} ({dialogue['tag']})...\n")
        bg_name = f"{dialogue['background']}.png"
        bg_path = BACKGROUND_DIR / bg_name
        if not bg_path.exists():
            bg_path = DEFAULT_BACKGROUND_DIR / bg_name
        if not bg_path.exists():
            exit("[!] Error: Background Not Found")
            
        bg = make_background(bg_path)

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

os._exit(0)
