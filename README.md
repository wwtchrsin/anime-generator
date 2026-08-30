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
* Backgrounds: `images/backgrounds/<background_tag>.png`
* Dialogues: `scripts/dialogues.json`
* Character list: `scripts/characters.json`
* Output file resolution and frame rate: `settings/general.json`
* Text size and dialog box: `settings/dialog-box.json`
* Sprite placement: `settings/sprite.json`

## DialogueLine interface
```javascript
{
  "character": string, //<character_tag>
  "delays": "complete" | "start" | "middle" | "end", //type of audio delays
  "position": "left" | "right", //sprite alignment
  "image": string, //<image_tag>
  "text": string, //line text
}
```

## Dialogues interface
```javascript
{
  "tag": string, //output file name
  "lang": string, //voice language
  "background": string, //<background_tag>
  "lines": DialogueLine[],
}[]
```

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
