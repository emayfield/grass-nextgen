# Project Instructions

## Repository
- GitHub: https://github.com/emayfield/grass-nextgen
- Periodically commit changes to this repo after significant updates
- Use descriptive commit messages summarizing what changed

## Project Overview
Grass - Bluegrass backing track generator with:
- MIDI generation with boom-chuck rhythm pattern
- MP3 conversion via FluidSynth
- Flask web interface with song library
- Real-time chord transposition and playback highlighting

## Project Structure

```
claude_practice/
├── app.py                 # Flask routes & API endpoints only (~300 lines)
├── bluegrass_midi.py      # MIDI generation logic
├── midi_to_mp3.py         # FluidSynth/ffmpeg conversion
├── songs.json             # Song database (hot-reloads on change)
├── templates/
│   └── index.html         # Main page HTML template
├── static/
│   ├── css/
│   │   └── styles.css     # All CSS styles (~500 lines)
│   └── js/
│       └── app.js         # All client-side JavaScript (~500 lines)
├── generated/             # Output directory for MP3 files
└── soundfonts/            # SoundFont files for audio rendering
```

## Architecture Notes

### Backend (app.py)
- Flask routes only - no inline HTML/CSS/JS
- Song library with mtime-based hot-reload (edit songs.json, changes appear immediately)
- Chord validation and progression parsing
- MIDI generation delegates to bluegrass_midi.py
- Audio conversion delegates to midi_to_mp3.py

### Frontend (static/js/app.js)
Organized into sections:
1. **State Management** - Global state variables
2. **Music Theory** - Key/chord transposition (semitone math)
3. **Tempo Controls** - Slider and button handlers
4. **Audio Playback** - Play/stop, chord highlighting animation
5. **Custom Song Editor** - User-created progressions
6. **Song List & Search** - Filtering, lyric search
7. **Song Display** - Chord rendering, YouTube embeds, lyrics
8. **Mobile Tabs** - Responsive layout switching

### Styles (static/css/styles.css)
Organized into sections:
1. Base styles & layout
2. Sidebar & song list
3. Main content area
4. Custom song editor
5. Song preview & chords
6. Lyrics display
7. Two-column layout (chords + demos)
8. Buttons & controls
9. Tempo slider
10. Animations & responsive design

## Development
- Python virtual environment in `venv/`
- Run server: `source venv/bin/activate && python app.py`
- Server runs at http://localhost:5000

## Key Features

### Bluegrass Rhythm
- Boom-chuck pattern: bass (root on 1, 5th on 3), mandolin chops (2 and 4), guitar
- Cut-time internally (user tempo 110 = internal 220 BPM)
- Bar duration for highlighting: `120 / tempo` seconds

### Chord Notation
- Single chord: `G`
- Split bar (two chords): `[C, G]`
- Half measure (2-beat): `[G]`

### Song Sections
- Each section has `name`, `chords` array, optional `repeats`
- Repeats display once with "(x2)" label, but timing map accounts for playback

### Transposition
- Client-side semitone calculation
- Supports all 12 major and minor keys
- Shows "(from X)" when transposed

### Chord Highlighting
- Uses `requestAnimationFrame` for smooth 60fps updates
- Tracks `currentTime` against cumulative bar durations
- Handles section repeats by mapping multiple timing entries to same displayed chord
