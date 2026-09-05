#!/usr/bin/env python3

import subprocess
from pathlib import Path
import shutil
import os
import opentimelineio as otio
from PIL import Image, ImageDraw, ImageFont
from piper import PiperVoice
import wave
import json
import string
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
OUTPUT_DIR  = PROJECT_DIR / Path("timeline-output")
CHARACTER_SPRITE_DIR = PROJECT_DIR / Path("images") / "characters"
BACKGROUND_DIR = PROJECT_DIR / Path("images") / "backgrounds"

if not PROJECT_DIR.exists():
    os.mkdir(PROJECT_DIR)

if OUTPUT_DIR.exists():
    shutil.rmtree(OUTPUT_DIR)
    
os.mkdir(OUTPUT_DIR)

with open(str(DEFAULT_SETTINGS_DIR / "general.json"), encoding="utf-8") as f:
    SETTINGS = json.load(f)

with open(str(DEFAULT_SETTINGS_DIR / "audio.json"), encoding="utf-8") as f:
    AUDIO_CLASSES = json.load(f)
    
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

if (SETTINGS_DIR / "audio.json").exists():
    with open(str(SETTINGS_DIR / "audio.json"), encoding="utf-8") as f:
        AUDIO_CLASSES = json.load(f)

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
FPS = SETTINGS["fps"]

VOICES = {}

for charTag in CHARACTERS:
    voiceTag = CHARACTERS[charTag]["voice"]
    VOICES[charTag] = PiperVoice.load(f"piper-voices/{voiceTag}.onnx")


def get_file_tag(idx):
    result = ""
    while True:
        result = string.ascii_lowercase[idx % 26] + result
        idx = idx // 26 - 1
        if idx < 0:
            break
    return result


def rt(frames: float) -> otio.opentime.RationalTime:
    return otio.opentime.RationalTime(frames, FPS)

def tr(start: float, dur: float) -> otio.opentime.TimeRange:
    return otio.opentime.TimeRange(rt(start), rt(dur))

def make_clip(name: str, path: Path, duration_frames: float,
              start_frame: float = 0) -> otio.schema.Clip:
    """Create OTIO clip and return reference"""
    return otio.schema.Clip(
        name=name,
        media_reference=otio.schema.ExternalReference(
            target_url=str(path),
            available_range=tr(0, duration_frames),
        ),
        source_range=tr(start_frame, duration_frames),
    )

def make_gap(duration_frames: float) -> otio.schema.Gap:
    return otio.schema.Gap(source_range=tr(0, duration_frames))

def load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()



def generate_dialogbox_png(root_dir: Path) -> Path:
    img = Image.new("RGBA", (VIDEO_W, VIDEO_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    short_side = min(VIDEO_W, VIDEO_H)
    dialog_margin = int(DIALOG_BOX["margin"] * short_side)
    dialog_height = int(DIALOG_BOX["height"] * VIDEO_H)
    dialog_border_width = int(round(DIALOG_BOX["border_width"] * short_side))
    
    draw.rounded_rectangle(
        [dialog_margin, VIDEO_H - dialog_height - dialog_margin,
         VIDEO_W - dialog_margin, VIDEO_H - dialog_margin],
        radius=12,
        fill=tuple(DIALOG_BOX["bg_color"]),
        outline=tuple(DIALOG_BOX["border_color"]),
        width=dialog_border_width,
    )
    path = root_dir / "images" / "dialogbox.png"
    img.save(str(path))
    return path
    

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

def generate_text_png(root_dir: Path, idx: int, line: dict) -> Path:
    char_cfg = CHARACTERS[line['character']]
    short_side = min(VIDEO_W, VIDEO_H)
    
    dialog_margin = int(DIALOG_BOX["margin"] * short_side)
    dialog_padding = int(DIALOG_BOX["padding"] * short_side)
    dialog_height = int(DIALOG_BOX["height"] * VIDEO_H)
    dialog_name_size = int(round(DIALOG_BOX["name_size"] * short_side))
    dialog_text_size = int(round(DIALOG_BOX["text_size"] * short_side))
    
    max_text_width = VIDEO_W - dialog_margin * 2 - dialog_padding * 2

    img = Image.new("RGBA", (VIDEO_W, VIDEO_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_name = load_font(dialog_name_size)
    font_text = load_font(dialog_text_size)

    px = dialog_margin + dialog_padding
    py = VIDEO_H - dialog_height - dialog_margin + dialog_padding

    # character name
    draw.text((px, py), char_cfg['name'], font=font_name, fill=tuple(char_cfg["name_color"]))
    py += dialog_name_size + 8

    # character line
    wrapped = auto_wrap(line['text'][0], font_text, max_text_width)
    draw.text((px, py), wrapped, font=font_text, fill=tuple(DIALOG_BOX["text_color"]))

    filetag =  get_file_tag(idx)
    path = root_dir / "images" / f"text_{filetag}_{line['character']}.png"
    img.save(str(path))
    return path


def generate_audio(root_dir: Path, idx: int, line: dict) -> tuple[Path, float]:
    char_cfg = CHARACTERS[line['character']]
    filetag = get_file_tag(idx)
    wav_temp_path = root_dir / "audio" / f"audio_{filetag}_temp.wav"
    wav_path = root_dir / "audio" / f"audio_{filetag}.wav"

    if line["audio"] not in AUDIO_CLASSES:
        exit(f"[!] Delay Class ({line["audio"]}) Not Found")

    audio_class = AUDIO_CLASSES[line["audio"]]

    if len(line["text"][-1]) > 0:
        with wave.open(str(wav_temp_path), "w") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(VOICES[line['character']].config.sample_rate)
            
            for audio_bytes in VOICES[line['character']].synthesize(line['text'][-1]):
                wav_file.writeframes(audio_bytes.audio_int16_bytes)

        subprocess.run([
            "ffmpeg", "-i", str(wav_temp_path), "-af", 
            f"rubberband=pitch={char_cfg['voice_pitch']},atempo={char_cfg['voice_tempo']}",
            str(wav_path)
        ], capture_output=True)
        
        os.remove(str(wav_temp_path))
    else:
        subprocess.run([
            "ffmpeg", 
            "-f", "lavfi",
            "-i", f"anullsrc=r={VOICES[line['character']].config.sample_rate}:cl=mono",
            "-t", str(audio_class["silence"]),
            "-c:a", "pcm_s16le",
            str(wav_path)
        ], capture_output=True)

    # defining duration
    result = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(wav_path),
    ], capture_output=True, text=True)
    
    duration_sec = audio_class["before"] + float(result.stdout.strip()) + audio_class["after"]
    duration_frames = duration_sec * FPS

    return wav_path, duration_frames, audio_class["before"]
    
def add_sprite(root_dir: Path, character: str, tag: str, pos: str) -> Path:
    sprite_path = root_dir / "images" / f"{character}-{tag}-{pos}.png"
    
    if sprite_path.exists():
        return sprite_path
    
    sprite_src = CHARACTER_SPRITE_DIR / character / f"{tag}.png"
    if not sprite_src.exists():
        sprite_src = DEFAULT_CHARACTER_SPRITE_DIR / character / f"{tag}.png"
    if not sprite_src.exists():
        exit(f"[!] Error: Sprite {character}/{tag} Not Found")
    
    img = Image.new("RGBA", (VIDEO_W, VIDEO_H), (0, 0, 0, 0))
    
    sprite_image = Image.open(sprite_src).convert("RGBA")
    
    sprite_side_margin = int(SPRITE["side_margin"] * VIDEO_W)
    sprite_bottom_offset = int(SPRITE["bottom_offset"] * VIDEO_H)
    target_h = int(VIDEO_H * SPRITE["max_height"])
    ratio = target_h / sprite_image.height
    target_w = int(sprite_image.width * ratio)
    sprite_image = sprite_image.resize((target_w, target_h), Image.LANCZOS)
    
    y = VIDEO_H - target_h - sprite_bottom_offset
    if pos == "left":
        x = sprite_side_margin
    elif pos == "right":
        x = VIDEO_W - target_w - sprite_side_margin
    else:
        x = int((VIDEO_W - target_w) * 0.5)
        
    img.paste(sprite_image, (x, y), sprite_image)
    img.save(str(sprite_path))
    
    return sprite_path
    
def make_background(root_dir: Path, bgTag: str) -> Path:
    bg_name = f"{bgTag}.png"
    bg_src = BACKGROUND_DIR / bg_name
    if not bg_src.exists():
        bg_src = DEFAULT_BACKGROUND_DIR / bg_name
    if not bg_src.exists():
        exit("[!] Error: Background Not Found")
        
    print(bg_src)
    bg_path = root_dir / "images" / f"background-{bgTag}.png"
    
    if bg_src.exists():
        img = Image.open(bg_src).convert("RGBA")
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
    resized_img = cropped_img.resize((VIDEO_W, VIDEO_H), Image.LANCZOS)
    resized_img.save(str(bg_path))
    
    return bg_path
    
      
def build_timeline(dtag: str, scenes: list[dict], bg_path: Path, dialog_path: Path) -> otio.schema.Timeline:
    """
    Tracks
      V1  background
      V2  character sprites
      V3  dialogbox
      V4  text png
      A1  dialogue audio
    """
    
    timeline = otio.schema.Timeline(name=dtag)
    tracks = timeline.tracks
    total_frames = sum(s["frames"] for s in scenes)

    # V1: background
    v1 = otio.schema.Track(name="background", kind=otio.schema.TrackKind.Video)
    v1.append(make_clip("background", bg_path, total_frames))
    tracks.append(v1)

    # V2: sprites
    v2 = otio.schema.Track(name="character", kind=otio.schema.TrackKind.Video)
    for s in scenes:
        if s['image_path'].exists():
            v2.append(make_clip(s["character"], s['image_path'], s["frames"]))
        else:
            v2.append(make_gap(s["frames"]))
    tracks.append(v2)

    # V3: dialog box
    v3 = otio.schema.Track(name="dialogbox", kind=otio.schema.TrackKind.Video)
    v3.append(make_clip("dialogbox", dialog_path, total_frames))
    tracks.append(v3)

    #V4: text
    v4 = otio.schema.Track(name="text", kind=otio.schema.TrackKind.Video)
    for i, s in enumerate(scenes):
        filetag = get_file_tag(i)
        v4.append(make_clip(f"text_{filetag}", s["text_path"], s["frames"]))
    tracks.append(v4)

    # A1: audio
    audio_gap_frames = s['audio_delay'] * FPS
    a1 = otio.schema.Track(name="dialogue", kind=otio.schema.TrackKind.Audio)
    for i, s in enumerate(scenes):
        filetag = get_file_tag(i)
        a1.append(make_gap(audio_gap_frames))
        a1.append(make_clip(f"audio_{filetag}", s["audio_path"], s["frames"] - audio_gap_frames))
    tracks.append(a1)

    return timeline

def main():
    print(f"\n[*] Working on project '{PROJECT_NAME}'...\n")
    for dialogue_index, dialogue in enumerate(DIALOGUES):
        print(f"\n[*] Creating dialogue {dialogue_index+1}/{len(DIALOGUES)} ({dialogue['tag']})...\n")
        
        root_dir = OUTPUT_DIR / dialogue['tag']
        os.mkdir(root_dir)
        os.mkdir(root_dir / "images")
        os.mkdir(root_dir / "audio")
        
        bg_path = make_background(root_dir, dialogue['background'])
        dialog_path = generate_dialogbox_png(root_dir)
        
        scenes = []

        for idx, line in enumerate(dialogue['lines']):
            char_tag = line['character']

            char_cfg = CHARACTERS[char_tag]
            print(f"  [{idx+1}/{len(dialogue['lines'])}] {char_cfg['name']}: {line['text'][0][:45]}...")

            text_png = generate_text_png(root_dir, idx, line)
            audio_wav, frames, delay = generate_audio(root_dir, idx, line)
            sprite_png = add_sprite(root_dir, char_tag, tag=line['image'], pos=line['position'])

            scenes.append({
                "character": char_tag,
                "text_path": text_png,
                "audio_path": audio_wav,
                "audio_delay": delay,
                "image_path": sprite_png,
                "frames":    frames,
            })
            print(f"    {frames/FPS:.1f}s  ({int(frames)} frames)")

        print("  Assembling timeline...")
        timeline = build_timeline(dialogue['tag'], scenes, bg_path=bg_path, dialog_path=dialog_path)

        otio_path = root_dir / f"{dialogue['tag']}.otio"
        otio.adapters.write_to_file(timeline, str(otio_path))

        total = sum(s["frames"] for s in scenes) / FPS
        print(f"\n  Done!")
        print(f"    Timeline : {otio_path}")
        print(f"    Duration : {total:.1f}s")


if __name__ == "__main__":
    main()
