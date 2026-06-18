#!/usr/bin/env python3

import subprocess
import textwrap
from pathlib import Path
import shutil
import os
import opentimelineio as otio
from PIL import Image, ImageDraw, ImageFont
from piper import PiperVoice
import wave
import json

VOICES = {
    "irina": PiperVoice.load("piper-voices/irina/ru_RU-irina-medium.onnx")
}

SCRIPT_DIR = Path("scripts")
OUTPUT_DIR  = Path("timeline-output")
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
    "height": 180,
    "margin": 30,
    "padding": 20,
    "bg_color": (10, 10, 30, 200),
    "border_color": (180, 180, 255, 220),
    "border_width": 2,
    "text_color": (255, 255, 255),
    "name_size": 28,
    "text_size": 24,
    "text_wrap": 55,
}

SPRITE = {
    "height_ratio": 0.85,
    "bottom_margin": 0,
    "side_margin": 120,
}

def rt(frames: float) -> otio.opentime.RationalTime:
    return otio.opentime.RationalTime(frames, FPS)

def tr(start: float, dur: float) -> otio.opentime.TimeRange:
    return otio.opentime.TimeRange(rt(start), rt(dur))

def make_clip(name: str, path: Path, duration_frames: float,
              start_frame: float = 0) -> otio.schema.Clip:
    """Создаёт OTIO клип со ссылкой на файл."""
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
    cfg = DIALOG_BOX
    img = Image.new("RGBA", (VIDEO_W, VIDEO_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    m = cfg["margin"]
    draw.rounded_rectangle(
        [m, VIDEO_H - cfg["height"] - m,
         VIDEO_W - m, VIDEO_H - m],
        radius=12,
        fill=cfg["bg_color"],
        outline=cfg["border_color"],
        width=cfg["border_width"],
    )
    path = root_dir / "images" / "dialogbox.png"
    img.save(str(path))
    return path


def generate_text_png(root_dir: Path, idx: int, line: dict) -> Path:
    cfg = DIALOG_BOX
    char_cfg = CHARACTERS[line['character']]

    img = Image.new("RGBA", (VIDEO_W, VIDEO_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_name = load_font(cfg["name_size"])
    font_text = load_font(cfg["text_size"])

    m  = cfg["margin"]
    px = m + cfg["padding"]
    py = VIDEO_H - cfg["height"] - m + cfg["padding"]

    # character name
    draw.text((px, py), char_cfg['name'], font=font_name, fill=tuple(char_cfg["name_color"]))
    py += cfg["name_size"] + 8

    # character line
    wrapped = textwrap.fill(line['text'], width=cfg["text_wrap"])
    draw.text((px, py), wrapped, font=font_text, fill=cfg["text_color"])

    path = root_dir / "images" / f"text_{idx:03d}_{line['character']}.png"
    img.save(str(path))
    return path


def generate_audio(root_dir: Path, idx: int, line: dict) -> tuple[Path, float]:
    char_cfg = CHARACTERS[line['character']]
    wav_temp_path = root_dir / "audio" / f"audio_{idx:03d}_temp.wav"
    wav_path = root_dir / "audio" / f"audio_{idx:03d}.wav"
    
    with wave.open(str(wav_temp_path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(VOICES[char_cfg['voice']].config.sample_rate)
        
        for audio_bytes in VOICES[char_cfg['voice']].synthesize(line['text']):
            wav_file.writeframes(audio_bytes.audio_int16_bytes)

    subprocess.run([
        "ffmpeg", "-i", str(wav_temp_path), "-af", 
        f"rubberband=pitch={char_cfg['voice_pitch']},atempo={char_cfg['voice_tempo']}",
        str(wav_path)
    ], capture_output=True)
    
    os.remove(str(wav_temp_path))

    # defining duration
    result = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(wav_path),
    ], capture_output=True, text=True)
    
    duration_sec = AUDIO_LEADING_GAP + float(result.stdout.strip()) + AUDIO_TRAILING_GAP
    duration_frames = duration_sec * FPS

    return wav_path, duration_frames
    
def add_sprite(root_dir: Path, character: str, tag: str, pos: str) -> Path:
    sprite_src = CHARACTER_SPRITE_DIR / f"{character}-{tag}.png"
    sprite_path = root_dir / "images" / f"{character}-{tag}-{pos}.png"
    
    if sprite_path.exists():
        return sprite_path
    
    img = Image.new("RGBA", (VIDEO_W, VIDEO_H), (0, 0, 0, 0))
    
    sprite_image = Image.open(sprite_src).convert("RGBA")
    target_h = int(VIDEO_H * SPRITE["height_ratio"])
    ratio = target_h / sprite_image.height
    target_w = int(sprite_image.width * ratio)
    sprite_image = sprite_image.resize((target_w, target_h), Image.LANCZOS)
    
    y = VIDEO_H - target_h - SPRITE["bottom_margin"]
    if pos == "left":
        x = SPRITE["side_margin"]
    elif pos == "right":
        x = VIDEO_W - target_w - SPRITE["side_margin"]
    else:
        x = int((VIDEO_W - target_w) * 0.5)
        
    img.paste(sprite_image, (x, y), sprite_image)
    img.save(str(sprite_path))
    
    return sprite_path
      
def build_timeline(dtag: str, scenes: list[dict], bg: str, lang: str) -> otio.schema.Timeline:
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

    root_dir = OUTPUT_DIR / dtag
    total_frames = sum(s["frames"] for s in scenes)
    bg_src = BACKGROUND_DIR / f"{bg}.jpg"
    bg_path = root_dir / "images" / f"background-{bg}.jpg"
    shutil.copyfile(bg_src, bg_path)
    
    dialogbox_path = generate_dialogbox_png(root_dir)

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
    v3.append(make_clip("dialogbox", dialogbox_path, total_frames))
    tracks.append(v3)

    #V4: text
    v4 = otio.schema.Track(name="text", kind=otio.schema.TrackKind.Video)
    for i, s in enumerate(scenes):
        v4.append(make_clip(f"text_{i:03d}", s["text_path"], s["frames"]))
    tracks.append(v4)

    # A1: audio
    audio_gap_frames = AUDIO_LEADING_GAP * FPS
    a1 = otio.schema.Track(name="dialogue", kind=otio.schema.TrackKind.Audio)
    for i, s in enumerate(scenes):
        a1.append(make_gap(audio_gap_frames))
        a1.append(make_clip(f"audio_{i:03d}", s["audio_path"], s["frames"] - audio_gap_frames))
    tracks.append(a1)

    return timeline

def main():
    for dialogue_index, dialogue in enumerate(DIALOGUES):
        print(f"\n[*] Creating dialogue {dialogue_index+1}/{len(DIALOGUES)} ({dialogue['tag']})...\n")
        
        root_dir = OUTPUT_DIR / dialogue['tag']
        os.mkdir(root_dir)
        os.mkdir(root_dir / "images")
        os.mkdir(root_dir / "audio")
        
        scenes = []

        for idx, line in enumerate(dialogue['lines']):
            char_tag = line['character']
            char_cfg = CHARACTERS[char_tag]
            print(f"  [{idx+1}/{len(dialogue['lines'])}] {char_cfg['name']}: {line['text'][:45]}...")

            text_png = generate_text_png(root_dir, idx, line)
            audio_wav, frames = generate_audio(root_dir, idx, line)
            sprite_png = add_sprite(root_dir, char_tag, tag=line['image'], pos=line['position'])

            scenes.append({
                "character": char_tag,
                "text_path": text_png,
                "audio_path": audio_wav,
                "image_path": sprite_png,
                "frames":    frames,
            })
            print(f"    {frames/FPS:.1f}s  ({int(frames)} frames)")

        print("  Assembling timeline...")
        timeline = build_timeline(dialogue['tag'], scenes, bg=dialogue['background'], lang=dialogue['lang'])

        otio_path = root_dir / f"{dialogue['tag']}.otio"
        otio.adapters.write_to_file(timeline, str(otio_path))

        total = sum(s["frames"] for s in scenes) / FPS
        print(f"\n  Done!")
        print(f"    Timeline : {otio_path}")
        print(f"    Duration : {total:.1f}s")


if __name__ == "__main__":
    main()
