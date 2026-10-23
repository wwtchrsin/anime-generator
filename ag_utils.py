import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from piper import PiperVoice
import wave
import time
import uuid
import os

def load_font(font_type: str, size: int) -> ImageFont.FreeTypeFont:
    if font_type == "chinese":
        candidates = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
        ]
    else: 
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def generate_dialogbox_img(settings: dict, dialog_options: dict) -> Image.Image:
    video_w = settings["video_width"]
    video_h = settings["video_height"]
    frame_padding = settings["frame_padding"]
    dialog_margin = dialog_options["margin"]
    
    img = Image.new("RGBA", (video_w, video_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    area_width = video_w - frame_padding["left"] - frame_padding["right"]
    area_height = video_h - frame_padding["top"] - frame_padding["bottom"]
    short_side = min(area_width, area_height)

    dialog_margin_left = int(dialog_margin["left"] * short_side)
    dialog_margin_top = int(dialog_margin["top"] * short_side)
    dialog_margin_right = int(dialog_margin["right"] * short_side)
    dialog_margin_bottom = int(dialog_margin["bottom"] * short_side)

    dialog_height = int(dialog_options["height"] * area_height)
    dialog_border_width = int(round(dialog_options["border_width"] * short_side))
    
    draw.rounded_rectangle(
        [dialog_margin_left + frame_padding["left"], 
         video_h - dialog_height - dialog_margin_bottom - frame_padding["bottom"],
         video_w - dialog_margin_right - frame_padding["right"], 
         video_h - dialog_margin_bottom - frame_padding["bottom"]],
        radius=12,
        fill=tuple(dialog_options["bg_color"]),
        outline=tuple(dialog_options["border_color"]),
        width=dialog_border_width,
    )

    return img

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

def generate_text_img(character: dict, text: str, settings: dict, dialog_options: dict) -> Image.Image:
    video_w = settings["video_width"]
    video_h = settings["video_height"]
    frame_padding = settings["frame_padding"]
    dialog_margin = dialog_options["margin"]
    dialog_padding = dialog_options["padding"]

    area_width = video_w - frame_padding["left"] - frame_padding["right"]
    area_height = video_h - frame_padding["top"] - frame_padding["bottom"]
    short_side = min(area_width, area_height)

    dialog_margin_left = int(dialog_margin["left"] * short_side)
    dialog_margin_top = int(dialog_margin["top"] * short_side)
    dialog_margin_right = int(dialog_margin["right"] * short_side)
    dialog_margin_bottom = int(dialog_margin["bottom"] * short_side)
    dialog_padding_left = int(dialog_padding["left"] * short_side)
    dialog_padding_top = int(dialog_padding["top"] * short_side)
    dialog_padding_right = int(dialog_padding["right"] * short_side)
    dialog_padding_bottom = int(dialog_padding["bottom"] * short_side)
    
    dialog_height = int(dialog_options["height"] * area_height)
    dialog_name_size = int(round(dialog_options["name_size"] * short_side))
    dialog_text_size = int(round(dialog_options["text_size"] * short_side))
    
    max_text_width = (area_width - dialog_margin_left - dialog_margin_right 
                      - dialog_padding_left - dialog_padding_right)

    img = Image.new("RGBA", (video_w, video_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_name = load_font(dialog_options["font_type"], dialog_name_size)
    font_text = load_font(dialog_options["font_type"], dialog_text_size)

    px = dialog_margin_left + dialog_padding_left + frame_padding["left"]
    py = video_h - dialog_height - dialog_margin_bottom + dialog_padding_top - frame_padding["bottom"]

    # character name
    draw.text((px, py), character['name'], font=font_name, fill=tuple(character["name_color"]))
    py += dialog_name_size + 8

    # character line
    wrapped = auto_wrap(text, font_text, max_text_width)
    draw.text((px, py), wrapped, font=font_text, fill=tuple(dialog_options["text_color"]))

    return img

def generate_audio(character: dict, text: str, voice: PiperVoice, silence_duration: float, out_path: Path) -> float:
    if len(text[-1]) > 0:
        timestamp = int(time.time() * 1000)
        out_dir = Path(out_path).parent
        temp_path = out_dir / f"{timestamp}_{uuid.uuid4().hex[:8]}.wav"
        with wave.open(str(temp_path), "w") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(voice.config.sample_rate)
            
            for audio_bytes in voice.synthesize(text):
                wav_file.writeframes(audio_bytes.audio_int16_bytes)

        subprocess.run([
            "ffmpeg", "-i", str(temp_path), "-af", 
            f"rubberband=pitch={character['voice_pitch']},atempo={character['voice_tempo']}",
            "-ac", "2",
            str(out_path)
        ], capture_output=True)
        
        os.remove(str(temp_path))
    else:
        subprocess.run([
            "ffmpeg", 
            "-f", "lavfi",
            "-i", f"anullsrc=r={voice.config.sample_rate}:cl=stereo",
            "-t", str(silence_duration),
            "-c:a", "pcm_s16le",
            str(out_path)
        ], capture_output=True)

    # defining duration
    result = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(out_path),
    ], capture_output=True, text=True)
    
    return float(result.stdout.strip())

def generate_sprite(sprite_src: Path, pos: str, settings: dict, sprite_options: dict) -> Image.Image:
    video_w = settings["video_width"]
    video_h = settings["video_height"]
    frame_padding = settings["frame_padding"]
    area_width = video_w - frame_padding["left"] - frame_padding["right"]
    area_height = video_h - frame_padding["top"] - frame_padding["bottom"]
    img = Image.new("RGBA", (video_w, video_h), (0, 0, 0, 0))
    
    sprite_image = Image.open(sprite_src).convert("RGBA")
    
    sprite_side_margin = int(sprite_options["side_margin"] * area_width)
    sprite_bottom_offset = int(sprite_options["bottom_offset"] * area_height)
    target_h = int(area_height * sprite_options["max_height"])
    ratio = target_h / sprite_image.height
    target_w = int(sprite_image.width * ratio)
    sprite_image = sprite_image.resize((target_w, target_h), Image.LANCZOS)
    
    y = video_h - target_h - sprite_bottom_offset - frame_padding["bottom"]
    if pos == "left":
        x = sprite_side_margin + frame_padding["left"]
    elif pos == "right":
        x = video_w - target_w - sprite_side_margin - frame_padding["right"]
    else:
        x = int((video_w - target_w - frame_padding["left"]) * 0.5) + frame_padding["left"]
        
    img.paste(sprite_image, (x, y), sprite_image)
    return img

def generate_background(bg_src: Path, settings: dict) -> Path:
    video_w = settings["video_width"]
    video_h = settings["video_height"]
    video_ar = video_w / video_h
    
    if bg_src.exists():
        img = Image.open(bg_src).convert("RGBA")
        
        image_ar = img.width / img.height
        if image_ar > video_ar:
            temp_height = img.height
            temp_width = img.height * video_ar
            left = (img.width - temp_width) // 2
            top = 0
            right = temp_width + left
            bottom = temp_height
        else:
            temp_width = img.width
            temp_height = img.width / video_ar
            left = 0
            top = (img.height - temp_height) // 2
            right = temp_width
            bottom = temp_height + top
            
        cropped_img = img.crop((left, top, right, bottom))
        return cropped_img.resize((video_w, video_h), Image.LANCZOS)
    else:
        # fallback
        img = Image.new("RGBA", (video_w, video_h), (30, 30, 60, 255))
        draw = ImageDraw.Draw(img)
        for y in range(video_h):
            r = int(20 + y / video_h * 30)
            g = int(20 + y / video_h * 20)
            b = int(50 + y / video_h * 60)
            draw.line([(0, y), (video_w, y)], fill=(r, g, b, 255))
        return img
    