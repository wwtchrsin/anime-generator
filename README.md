# Anime-Generator - A small python utility that allow you to generate video clips in the style of visual novels

## Installation
```bash
pip install -r requirements.txt
```
The utility uses ffmpeg so make sure it is installed on your system as well

## Creating project
Projects are located in the **projects** directory and utilize the resources and settings 
from the **example** project by default. You can override them
by placing the corresponding files in the project directory.

## Project structure
* Character sprite: `images/characters/<character_tag>/<image_tag>.png`
* Background: `images/backgrounds/<background_tag>.png`
* Dialogues: `scripts/dialogues.json`
* Character list: `scripts/characters.json`
* Output file resolution and frame rate: `settings/general.json`
* Text size and dialog box: `settings/dialog-box.json`
* Sprite size and position: `settings/sprite.json`

## DialogueLine interface
```javascript
{
  "character": string, //<character_tag>
  "delays": "both" | "start" | "end" | "no", //audio delays
  "position": "left" | "right", //sprite alignment
  "image": string, //<image_tag>
  "text": string[], //first array element used to generate text,
                    //last array element used to generate audio,
                    //a single element is both first and last
}
```

## Dialogues interface
```javascript
{
  "tag": string, //output file name
  "background": string, //<background_tag>
  "lines": DialogueLine[],
}[]
```

## Voices
The utility uses `piper-voice` model for voice generation. All voices available to 
the utility are located in the **piper-voices** directory. Any additional voices you 
might need can be downloaded from the model's official page. Make sure to copy to the 
**piper-voices** directory both .onnx and .onnx.json files. In the character 
description (`scripts/characters.json`) you specify the voice using the voice file 
name without its extension.

## Generating video
```bash
./make_video.py <project_name>
```
The output files will be located in the `projects/<project_name>/video-output` directory

## Generating OTIO Timelines
```bash
./make_timeline.py <project_name>
```
The output files will be located in the `projects/<project_name>/timeline-output` directory
