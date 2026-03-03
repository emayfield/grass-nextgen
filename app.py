"""
Bluegrass Backing Track Generator - Web Interface

A Flask web app that generates bluegrass backing tracks from chord progressions.
"""

import json
import os
import re
import tempfile
import uuid
from pathlib import Path

from flask import Flask, render_template, request, send_file, jsonify
from youtubesearchpython import VideosSearch

from bluegrass_midi import (
    generate_bluegrass_midi, load_songs, list_songs,
    get_song_progression, generate_song, transpose_progression,
    COMMON_KEYS
)
from midi_to_mp3 import convert_midi_to_mp3, find_soundfont


# =============================================================================
# App Configuration
# =============================================================================

app = Flask(__name__)

# Directory for generated files
OUTPUT_DIR = Path(__file__).parent / "generated"
OUTPUT_DIR.mkdir(exist_ok=True)


# =============================================================================
# Song Library (with hot-reload support)
# =============================================================================

SONGS_PATH = Path(__file__).parent / "songs.json"
SONGS_DATA = None
SONGS_MTIME = 0


def get_songs_data():
    """Get songs data, reloading if file has changed."""
    global SONGS_DATA, SONGS_MTIME

    if not SONGS_PATH.exists():
        return None

    current_mtime = SONGS_PATH.stat().st_mtime
    if current_mtime != SONGS_MTIME:
        try:
            SONGS_DATA = load_songs(SONGS_PATH)
            SONGS_MTIME = current_mtime
            print(f"Reloaded songs.json ({len(SONGS_DATA)} songs)")
        except Exception as e:
            print(f"Warning: Could not load songs.json: {e}")

    return SONGS_DATA


def save_songs_data(songs_data):
    """Save songs data back to songs.json."""
    global SONGS_MTIME
    with open(SONGS_PATH, 'w') as f:
        json.dump(songs_data, f, indent=2)
    SONGS_MTIME = SONGS_PATH.stat().st_mtime


# =============================================================================
# Chord Parsing & Validation
# =============================================================================

def validate_chord(chord):
    """Validate a single chord name."""
    valid_roots = set('ABCDEFG')
    if not chord or chord[0].upper() not in valid_roots:
        raise ValueError(f"Invalid chord: {chord}")
    return chord.strip()


def parse_progression(progression_str):
    """
    Parse a chord progression string with support for split bars.

    Examples:
        "G C D G" -> ['G', 'C', 'D', 'G']
        "G [C, G] D G" -> ['G', ['C', 'G'], 'D', 'G']
        "G [Am,D] G" -> ['G', ['Am', 'D'], 'G']
    """
    progression_str = progression_str.strip()
    result = []

    # Pattern to match either [chord, chord] or single chord
    pattern = r'\[([^\]]+)\]|(\S+)'

    for match in re.finditer(pattern, progression_str):
        if match.group(1):
            # Split bar: [C, G] or [C,G]
            parts = [p.strip() for p in match.group(1).split(',')]
            if len(parts) != 2:
                raise ValueError(f"Split bars must have exactly 2 chords: [{match.group(1)}]")
            validate_chord(parts[0])
            validate_chord(parts[1])
            result.append(parts)
        else:
            # Single chord
            chord = match.group(2)
            validate_chord(chord)
            result.append(chord)

    if not result:
        raise ValueError("No chords found in progression")

    return result


# =============================================================================
# Routes
# =============================================================================

@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')


@app.route('/generate', methods=['POST'])
def generate():
    """Generate a backing track from custom chord progression."""
    try:
        # Parse form data
        progression_str = request.form.get('progression', '').strip()
        tempo = int(request.form.get('tempo', 110))
        repeats = int(request.form.get('repeats', 2))

        # Validate
        if not progression_str:
            return jsonify({'success': False, 'error': 'Please enter a chord progression'})

        if not 60 <= tempo <= 200:
            return jsonify({'success': False, 'error': 'Tempo must be between 60 and 200 BPM'})

        if not 1 <= repeats <= 16:
            return jsonify({'success': False, 'error': 'Repeats must be between 1 and 16'})

        # Parse chords
        try:
            chords = parse_progression(progression_str)
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)})

        # Create full progression with repeats
        full_progression = chords * repeats

        # Generate unique filename
        file_id = uuid.uuid4().hex[:8]
        safe_name = progression_str.replace(' ', '-').replace('#', 's')[:30]
        base_name = f"bluegrass_{safe_name}_{tempo}bpm_{file_id}"

        midi_path = OUTPUT_DIR / f"{base_name}.mid"
        mp3_path = OUTPUT_DIR / f"{base_name}.mp3"

        # Generate MIDI
        _, duration = generate_bluegrass_midi(
            full_progression,
            tempo=tempo,
            output_file=str(midi_path)
        )

        # Convert to MP3 with exact duration for seamless looping
        soundfont = find_soundfont()
        if not soundfont:
            return jsonify({'success': False, 'error': 'No SoundFont available for audio rendering'})

        success = convert_midi_to_mp3(
            str(midi_path),
            str(mp3_path),
            soundfont_path=str(soundfont),
            duration=duration
        )

        if not success:
            return jsonify({'success': False, 'error': 'Failed to convert MIDI to MP3'})

        # Clean up MIDI file
        midi_path.unlink(missing_ok=True)

        return jsonify({
            'success': True,
            'audio_url': f'/audio/{mp3_path.name}',
            'filename': f"{base_name}.mp3"
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/audio/<filename>')
def serve_audio(filename):
    """Serve generated audio files."""
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        return "File not found", 404
    return send_file(file_path, mimetype='audio/mpeg')


@app.route('/api/songs')
def api_list_songs():
    """Return list of available songs with section details."""
    songs_data = get_songs_data()
    if songs_data is None:
        return jsonify([])

    songs = []
    for song_id, data in songs_data.items():
        songs.append({
            'id': song_id,
            'title': data.get('title', song_id),
            'key': data.get('key', 'C'),
            'type': data.get('type', 'unknown'),
            'sections': data.get('sections', []),
            'lyrics': data.get('lyrics', ''),
            'demo': data.get('demo', []),
            'featured_demo': data.get('featured_demo', [])
        })

    return jsonify(sorted(songs, key=lambda s: s['title']))


@app.route('/generate_song', methods=['POST'])
def generate_song_route():
    """Generate a backing track from a song in the library."""
    try:
        songs_data = get_songs_data()
        if songs_data is None:
            return jsonify({'success': False, 'error': 'Song library not available'})

        song_id = request.form.get('song_id', '').strip()
        tempo = int(request.form.get('tempo', 110))
        repeats = int(request.form.get('repeats', 1))
        target_key = request.form.get('key', '').strip()
        original_key = request.form.get('original_key', '').strip()

        if not song_id:
            return jsonify({'success': False, 'error': 'No song selected'})

        if song_id not in songs_data:
            return jsonify({'success': False, 'error': f'Song not found: {song_id}'})

        if not 60 <= tempo <= 200:
            return jsonify({'success': False, 'error': 'Tempo must be between 60 and 200 BPM'})

        # Get song progression
        song = songs_data[song_id]
        progression = get_song_progression(song)

        if not progression:
            return jsonify({'success': False, 'error': 'No chords found in song'})

        # Transpose if key changed
        from_key = original_key or song.get('key', 'C')
        if target_key and target_key != from_key:
            progression = transpose_progression(progression, from_key, target_key)

        # Apply repeats
        full_progression = progression * repeats

        # Generate unique filename (include key if transposed)
        file_id = uuid.uuid4().hex[:8]
        key_suffix = f"_{target_key}" if target_key and target_key != from_key else ""
        base_name = f"{song_id}{key_suffix}_{tempo}bpm_{file_id}"

        midi_path = OUTPUT_DIR / f"{base_name}.mid"
        mp3_path = OUTPUT_DIR / f"{base_name}.mp3"

        # Generate MIDI
        _, duration = generate_bluegrass_midi(
            full_progression,
            tempo=tempo,
            output_file=str(midi_path)
        )

        # Convert to MP3 with exact duration for seamless looping
        soundfont = find_soundfont()
        if not soundfont:
            return jsonify({'success': False, 'error': 'No SoundFont available'})

        success = convert_midi_to_mp3(
            str(midi_path),
            str(mp3_path),
            soundfont_path=str(soundfont),
            duration=duration
        )

        if not success:
            return jsonify({'success': False, 'error': 'Failed to convert to MP3'})

        # Clean up MIDI file
        midi_path.unlink(missing_ok=True)

        return jsonify({
            'success': True,
            'audio_url': f'/audio/{mp3_path.name}',
            'filename': f"{base_name}.mp3"
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# =============================================================================
# Demo Video Management Routes
# =============================================================================

@app.route('/manage')
def manage():
    """Serve the demo video management page."""
    return render_template('manage.html')


@app.route('/api/search_youtube', methods=['POST'])
def search_youtube():
    """Search YouTube for demo videos related to a song."""
    try:
        query = request.json.get('query', '').strip()
        limit = request.json.get('limit', 10)

        if not query:
            return jsonify({'success': False, 'error': 'No search query provided'})

        # Search YouTube
        search = VideosSearch(query, limit=limit)
        results = search.result().get('result', [])

        videos = []
        for v in results:
            videos.append({
                'id': v.get('id', ''),
                'title': v.get('title', ''),
                'url': f"https://youtu.be/{v.get('id', '')}",
                'channel': v.get('channel', {}).get('name', ''),
                'thumbnail': v.get('thumbnails', [{}])[0].get('url', ''),
                'duration': v.get('duration', '')
            })

        return jsonify({'success': True, 'videos': videos})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/add_demo', methods=['POST'])
def add_demo():
    """Add a demo video URL to a song in songs.json."""
    try:
        song_id = request.json.get('song_id', '').strip()
        video_url = request.json.get('video_url', '').strip()
        is_featured = request.json.get('featured', False)

        if not song_id or not video_url:
            return jsonify({'success': False, 'error': 'Missing song_id or video_url'})

        songs_data = get_songs_data()
        if songs_data is None:
            return jsonify({'success': False, 'error': 'Song library not available'})

        if song_id not in songs_data:
            return jsonify({'success': False, 'error': f'Song not found: {song_id}'})

        song = songs_data[song_id]

        # Add to appropriate list
        if is_featured:
            if 'featured_demo' not in song:
                song['featured_demo'] = []
            if video_url not in song['featured_demo']:
                song['featured_demo'].append(video_url)
        else:
            if 'demo' not in song:
                song['demo'] = []
            if video_url not in song['demo']:
                song['demo'].append(video_url)

        # Save back to file
        save_songs_data(songs_data)

        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/remove_demo', methods=['POST'])
def remove_demo():
    """Remove a demo video from a song."""
    try:
        song_id = request.json.get('song_id', '').strip()
        video_url = request.json.get('video_url', '').strip()

        if not song_id or not video_url:
            return jsonify({'success': False, 'error': 'Missing song_id or video_url'})

        songs_data = get_songs_data()
        if songs_data is None:
            return jsonify({'success': False, 'error': 'Song library not available'})

        if song_id not in songs_data:
            return jsonify({'success': False, 'error': f'Song not found: {song_id}'})

        song = songs_data[song_id]

        # Remove from both lists if present
        if 'demo' in song and video_url in song['demo']:
            song['demo'].remove(video_url)
        if 'featured_demo' in song and video_url in song['featured_demo']:
            song['featured_demo'].remove(video_url)

        # Save back to file
        save_songs_data(songs_data)

        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == '__main__':
    print("Starting Grass - Bluegrass Backing Track Generator...")
    print("Open http://localhost:5000 in your browser")
    app.run(debug=True, port=5000)
