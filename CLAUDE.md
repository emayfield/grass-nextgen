# Project Instructions

## Repository
- GitHub: https://github.com/emayfield/grass-nextgen
- Periodically commit changes to this repo after significant updates
- Use descriptive commit messages summarizing what changed

## Project Overview
Bluegrass backing track generator with:
- MIDI generation (bluegrass_midi.py)
- MP3 conversion via FluidSynth (midi_to_mp3.py)
- Flask web interface with song library (app.py)
- Song database (songs.json)

## Development
- Python virtual environment in `venv/`
- Run server: `source venv/bin/activate && python app.py`
- Server runs at http://localhost:5000

## Key Features
- Boom-chuck rhythm: bass (root on 1, 5th on 3), mandolin chops (2 and 4), guitar
- Split bars: `[C, G]` for two chords in one bar
- Half measures: `[G]` for 2-beat bars
- Key transposition with live chord preview
- Bluegrass tempo is doubled internally (110 BPM = 220 actual)
