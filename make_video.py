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
import ag_utils

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
FRAME_PADDING = SETTINGS["frame_padding"]
DIALOG_PADDING = DIALOG_BOX["padding"]
DIALOG_MARGIN = DIALOG_BOX["margin"]
VIDEO_AR = VIDEO_W / VIDEO_H

VOICES = {}

for charTag in CHARACTERS:
    voiceTag = CHARACTERS[charTag]["voice"]
    VOICES[charTag] = PiperVoice.load(f"piper-voices/{voiceTag}.onnx")

def make_background(bg_path: Path) -> Image.Image:
    return ag_utils.generate_background(bg_src=bg_path, settings=SETTINGS)

def paste_sprite(frame: Image.Image, sprite_path: Path, align: str) -> Image.Image:
    sprite = ag_utils.generate_sprite(sprite_src=sprite_path, pos=align,
                                      settings=SETTINGS,
                                      sprite_options=SPRITE)
    frame = Image.alpha_composite(frame, sprite)
    return frame

def draw_dialog_box(frame: Image.Image, character: str, text: str) -> Image.Image:
    char_cfg = CHARACTERS[character]
    dialog_img = ag_utils.generate_dialogbox_img(settings=SETTINGS, dialog_options=DIALOG_BOX)
    text_img = ag_utils.generate_text_img(character=char_cfg, text=text,
                                          settings=SETTINGS, dialog_options=DIALOG_BOX)
    frame = Image.alpha_composite(frame, dialog_img)
    frame = Image.alpha_composite(frame, text_img)
    return frame

def generate_audio(line: dict, out_path: Path) -> float:
    char_cfg = CHARACTERS[line['character']]

    if line["audio"] not in AUDIO_CLASSES:
        exit(f"[!] Delay Class ({line["audio"]}) Not Found")

    audio_class = AUDIO_CLASSES[line["audio"]]
    duration = ag_utils.generate_audio(character=char_cfg, text=line["text"][-1],
                                       voice=VOICES[line["character"]],
                                       silence_duration=audio_class["silence"],
                                       out_path=out_path)
    
    return audio_class["before"] + duration + audio_class["after"]

def make_frame(line: dict, bg: Image.Image) -> Image.Image:
    frame = bg.copy()

    image_path = CHARACTER_SPRITE_DIR / line['character'] / f"{line['image']}.png"
    if not image_path.exists():
        image_path = DEFAULT_CHARACTER_SPRITE_DIR / line['character'] / f"{line['image']}.png"
    if not image_path.exists():
        exit(f"[!] Error: Sprite {line['character']}/{line['image']} Not Found")
        
    frame = paste_sprite(frame, image_path, line['position'])
    frame = draw_dialog_box(frame, line['character'], line['text'][0])
    return frame

def render_scene(idx: int, line: dict, bg: Image.Image, audio_path: Path, 
               duration: float,
               scene_path: Path):

    if line["audio"] not in AUDIO_CLASSES:
        exit(f"[!] Delay Class ({line["audio"]}) Not Found")

    audio_class = AUDIO_CLASSES[line["audio"]]
    
    frame = make_frame(line, bg)
    frame_path = OUTPUT_DIR / f"frame_{idx:03d}.png"
    frame.convert("RGB").save(str(frame_path))

    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1",
        "-r", str(SETTINGS["fps"]),
        "-i", str(frame_path),
        "-i", str(audio_path),
        "-af", f"adelay={int(audio_class["before"]*1000)}|{int(audio_class["before"]*1000)},apad=pad_dur={audio_class["after"]}",
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
            
            print(f"  [{idx+1}/{len(dialogue['lines'])}] {char_cfg['name']}: {line['text'][0][:45]}...")

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
