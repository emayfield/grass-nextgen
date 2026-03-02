"""
Bluegrass Backing Track Generator - Web Interface

A Flask web app that generates bluegrass backing tracks from chord progressions.
"""

import os
import tempfile
import uuid
from pathlib import Path

from flask import Flask, render_template_string, request, send_file, jsonify

from bluegrass_midi import (
    generate_bluegrass_midi, load_songs, list_songs,
    get_song_progression, generate_song, transpose_progression,
    COMMON_KEYS
)
from midi_to_mp3 import convert_midi_to_mp3, find_soundfont

# Songs library with mtime-based caching
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

app = Flask(__name__)

# Directory for generated files
OUTPUT_DIR = Path(__file__).parent / "generated"
OUTPUT_DIR.mkdir(exist_ok=True)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Grass</title>
    <style>
        * { box-sizing: border-box; }
        html, body {
            margin: 0;
            padding: 0;
            height: 100%;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            color: #333;
            background: #f5f5f5;
        }
        /* Top header bar */
        .top-header {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 48px;
            background: #2c5530;
            display: flex;
            align-items: center;
            padding: 0 20px;
            z-index: 100;
        }
        .top-header h1 {
            margin: 0;
            font-size: 18px;
            font-weight: 600;
            color: white;
            letter-spacing: 0.5px;
        }
        .layout {
            display: flex;
            height: 100vh;
            padding-top: 48px;
        }
        /* Sidebar */
        .sidebar {
            width: 320px;
            min-width: 320px;
            background: white;
            border-right: 1px solid #ddd;
            display: flex;
            flex-direction: column;
            height: calc(100vh - 48px);
        }
        .sidebar-header {
            padding: 12px;
            border-bottom: 1px solid #eee;
        }
        .sidebar-header input {
            width: 100%;
            padding: 10px 14px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
        }
        .song-search input:focus {
            outline: none;
            border-color: #2c5530;
        }
        .song-list {
            flex: 1;
            overflow-y: auto;
            min-height: 0;
        }
        .song-item {
            padding: 12px 20px;
            border-bottom: 1px solid #eee;
            cursor: pointer;
            transition: background 0.15s;
        }
        .song-item:hover { background: #f5f5f5; }
        .song-item.selected { background: #e8f5e9; }
        .song-title { font-weight: 600; color: #333; font-size: 14px; }
        .song-meta { font-size: 12px; color: #888; margin-top: 4px; }
        .song-key {
            display: inline-block;
            background: #2c5530;
            color: white;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            margin-right: 6px;
        }
        .song-type {
            display: inline-block;
            background: #eee;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
        }
        .no-songs { padding: 20px; text-align: center; color: #888; }

        /* Custom progression button */
        .sidebar-footer {
            padding: 12px;
            border-top: 1px solid #ddd;
        }
        .create-custom-btn {
            width: 100%;
            padding: 10px;
            background: #f8f9fa;
            border: 2px dashed #ccc;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            color: #666;
            cursor: pointer;
            transition: all 0.2s;
        }
        .create-custom-btn:hover {
            background: #e8f5e9;
            border-color: #2c5530;
            color: #2c5530;
        }

        /* Editable custom song */
        .custom-song-editor input[type="text"],
        .custom-song-editor textarea {
            width: 100%;
            padding: 10px 12px;
            border: 2px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            margin-bottom: 12px;
            font-family: inherit;
        }
        .custom-song-editor input:focus,
        .custom-song-editor textarea:focus {
            outline: none;
            border-color: #2c5530;
        }
        .custom-song-editor .title-input {
            font-size: 18px;
            font-weight: 600;
        }
        .custom-song-editor .chords-input {
            font-family: 'SF Mono', Monaco, 'Courier New', monospace;
        }
        .custom-song-editor .lyrics-input {
            min-height: 150px;
            resize: vertical;
        }
        .custom-song-editor label {
            display: block;
            font-size: 12px;
            font-weight: 600;
            color: #666;
            margin-bottom: 4px;
        }
        .custom-song-editor .help {
            font-size: 11px;
            color: #888;
            margin: -8px 0 12px;
        }
        .song-list-section {
            padding: 8px 16px 4px;
            font-size: 11px;
            font-weight: 600;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            background: #f5f5f5;
            border-bottom: 1px solid #eee;
            position: sticky;
            top: 0;
        }
        .lyric-match-snippet {
            font-size: 11px;
            color: #666;
            font-style: italic;
            margin-top: 4px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .lyric-match-snippet mark {
            background: #fff3cd;
            padding: 0 2px;
            border-radius: 2px;
        }

        /* Main content */
        .main {
            flex: 1;
            overflow-y: auto;
            padding: 40px;
        }
        .main-inner {
            max-width: 700px;
        }
        .card {
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        label {
            display: block;
            font-weight: 600;
            margin-bottom: 8px;
            color: #444;
        }
        input[type="text"], input[type="number"], select {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
            margin-bottom: 20px;
            transition: border-color 0.2s;
        }
        input:focus, select:focus {
            outline: none;
            border-color: #2c5530;
        }
        .row { display: flex; gap: 20px; }
        .row > div { flex: 1; }
        button[type="submit"], .generate-btn {
            background: #2c5530;
            color: white;
            border: none;
            padding: 14px 28px;
            font-size: 16px;
            font-weight: 600;
            border-radius: 8px;
            cursor: pointer;
            width: 100%;
            transition: background 0.2s;
        }
        button[type="submit"]:hover, .generate-btn:hover { background: #1e3d22; }
        button:disabled { background: #999; cursor: not-allowed; }
        .download-link {
            display: inline-block;
            color: #2c5530;
            text-decoration: none;
            font-weight: 600;
        }
        .download-link:hover { text-decoration: underline; }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* Song preview styles */
        .song-preview {
            background: #f8f9fa;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 20px;
        }
        .preview-header {
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid #ddd;
        }
        .preview-header strong { font-size: 16px; }
        .preview-header span { color: #666; margin-left: 10px; font-size: 14px; }
        .preview-section { margin-bottom: 10px; }
        .preview-section-name {
            font-weight: 600;
            color: #2c5530;
            font-size: 13px;
            margin-bottom: 4px;
        }
        .preview-chords {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
            font-family: 'SF Mono', Monaco, 'Courier New', monospace;
            font-size: 13px;
            color: #444;
        }
        .preview-chords .chord {
            width: calc(25% - 3px);
            box-sizing: border-box;
            background: #fff;
            border: 1px solid #ddd;
            padding: 6px 4px;
            border-radius: 4px;
            text-align: center;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .preview-chords .split-bar {
            display: flex;
            justify-content: space-around;
        }
        .preview-chords .half-bar {
            width: calc(12.5% - 3px);
        }
        .preview-chords .rest { background: #eee; color: #999; font-style: italic; }

        /* Lyrics styles */
        .lyrics-section {
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
        }
        .lyrics-section h3 {
            font-size: 14px;
            color: #2c5530;
            margin: 0 0 12px 0;
        }
        .lyrics-content {
            font-size: 14px;
            line-height: 1.8;
            color: #444;
            white-space: pre-wrap;
        }
        .lyrics-content .chorus {
            background: #fff8e1;
            border-left: 3px solid #f9a825;
            padding: 12px 16px;
            margin: 12px 0;
            display: block;
        }
        .lyrics-content .verse {
            padding: 8px 0;
            display: block;
        }

        .select-prompt {
            text-align: center;
            padding: 40px 20px;
            color: #888;
        }
        .select-prompt h3 { color: #666; margin-bottom: 8px; }

        /* Play button */
        .play-btn {
            background: #2c5530;
            color: white;
            border: none;
            width: 48px;
            height: 48px;
            border-radius: 50%;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background 0.2s;
            margin-top: 24px;
            flex-shrink: 0;
        }
        .play-btn:hover { background: #1e3d22; }
        .play-btn:disabled { background: #999; cursor: not-allowed; }
        .play-btn svg { width: 20px; height: 20px; fill: white; }
        .play-btn.loading svg { display: none; }
        .play-btn.loading::after {
            content: '';
            width: 20px;
            height: 20px;
            border: 2px solid white;
            border-top-color: transparent;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        /* Audio player row */
        .audio-row {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 20px;
            padding: 12px 16px;
            background: #f8f9fa;
            border-radius: 8px;
        }
        .audio-row audio {
            flex: 1;
        }
        .audio-row .download-link {
            margin: 0;
            white-space: nowrap;
        }
    </style>
</head>
<body>
    <div class="top-header">
        <h1>Grass</h1>
    </div>
    <div class="layout">
        <!-- Sidebar with song list -->
        <div class="sidebar">
            <div class="sidebar-header">
                <input type="text" id="songSearch" placeholder="Search songs..."
                       oninput="filterSongs(this.value)">
            </div>
            <div class="song-list" id="songList">
                <div class="no-songs">Loading songs...</div>
            </div>
            <div class="sidebar-footer">
                <button class="create-custom-btn" onclick="createCustomSong()">
                    + Custom Song
                </button>
            </div>
        </div>

        <!-- Main content area -->
        <div class="main">
            <div class="main-inner">
                <div class="card">
                    <div id="noSongSelected" class="select-prompt">
                        <h3>No song selected</h3>
                        <p>Select a song from the sidebar to get started</p>
                    </div>

                    <!-- Custom song editor -->
                    <div id="customSongEditor" class="custom-song-editor" style="display: none;">
                        <input type="text" id="customTitle" class="title-input"
                               placeholder="Song Title" value="Custom Song">

                        <div class="row">
                            <div>
                                <label for="customKey">Key</label>
                                <select id="customKey" onchange="clearCustomCache()">
                                    <option value="C">C</option>
                                    <option value="D">D</option>
                                    <option value="E">E</option>
                                    <option value="F">F</option>
                                    <option value="G" selected>G</option>
                                    <option value="A">A</option>
                                    <option value="B">B</option>
                                    <option value="Am">Am</option>
                                    <option value="Dm">Dm</option>
                                    <option value="Em">Em</option>
                                </select>
                            </div>
                            <div>
                                <label for="customTempo">Tempo (BPM)</label>
                                <input type="number" id="customTempo" value="110" min="60" max="200"
                                       onchange="clearCustomCache()">
                            </div>
                            <div>
                                <label for="customRepeats">Repeats</label>
                                <input type="number" id="customRepeats" value="2" min="1" max="8"
                                       onchange="clearCustomCache()">
                            </div>
                            <button type="button" class="play-btn" id="customPlayBtn" onclick="playCustom()" title="Play">
                                <svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                            </button>
                        </div>

                        <div id="customAudioRow" class="audio-row" style="display: none;">
                            <audio id="customAudioPlayer" controls loop></audio>
                            <a id="customDownloadLink" class="download-link" download>Download</a>
                        </div>

                        <label for="customChords">Chord Progression</label>
                        <input type="text" id="customChords" class="chords-input"
                               placeholder="G G C D" value="G G C D" onchange="clearCustomCache()">
                        <p class="help">One chord per bar. Use [C, G] for split bars, [G] for half bars.</p>

                        <label for="customLyrics">Lyrics (optional)</label>
                        <textarea id="customLyrics" class="lyrics-input"
                                  placeholder="Enter lyrics here...&#10;&#10;Use blank lines between verses.&#10;Wrap chorus in <chorus>...</chorus> tags."></textarea>
                    </div>

                    <div id="songControls" style="display: none;">
                        <div class="row">
                            <div>
                                <label for="songKey">Key</label>
                                <select id="songKey" onchange="updateChordPreview()">
                                    <option value="">Select a song first</option>
                                </select>
                            </div>
                            <div>
                                <label for="songTempo">Tempo (BPM)</label>
                                <input type="number" id="songTempo" value="110" min="60" max="200">
                            </div>
                            <div>
                                <label for="songRepeats">Repeats</label>
                                <input type="number" id="songRepeats" value="1" min="1" max="8">
                            </div>
                            <button type="button" class="play-btn" id="playBtn" onclick="playOrGenerate()" title="Play">
                                <svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                            </button>
                        </div>

                        <div id="audioRow" class="audio-row" style="display: none;">
                            <audio id="songAudioPlayer" controls loop></audio>
                            <a id="songDownloadLink" class="download-link" download>Download</a>
                        </div>

                        <div id="songPreview" class="song-preview">
                            <div class="preview-header">
                                <strong id="previewTitle"></strong>
                                <span id="previewMeta"></span>
                            </div>
                            <div id="previewSections"></div>
                            <div id="lyricsSection" class="lyrics-section" style="display: none;">
                                <h3>Lyrics</h3>
                                <div id="lyricsContent" class="lyrics-content"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let songs = [];
        let selectedSong = null;

        // Create custom song
        function createCustomSong() {
            // Deselect any selected song
            document.querySelectorAll('.song-item').forEach(el => el.classList.remove('selected'));
            selectedSong = null;

            // Hide other views, show custom editor
            document.getElementById('noSongSelected').style.display = 'none';
            document.getElementById('songControls').style.display = 'none';
            document.getElementById('customSongEditor').style.display = 'block';

            // Reset audio
            document.getElementById('customAudioRow').style.display = 'none';
            customCachedAudio = null;
        }

        let customCachedAudio = null;

        // Clear custom cache when inputs change
        function clearCustomCache() {
            customCachedAudio = null;
            document.getElementById('customAudioRow').style.display = 'none';
        }

        async function playCustom() {
            const btn = document.getElementById('customPlayBtn');
            const audioPlayer = document.getElementById('customAudioPlayer');
            const audioRow = document.getElementById('customAudioRow');

            // If cached, just play
            if (customCachedAudio) {
                audioPlayer.play();
                return;
            }

            const chords = document.getElementById('customChords').value.trim();
            if (!chords) {
                alert('Please enter a chord progression');
                return;
            }

            btn.disabled = true;
            btn.classList.add('loading');

            try {
                const formData = new FormData();
                formData.append('progression', chords);
                formData.append('tempo', document.getElementById('customTempo').value);
                formData.append('repeats', document.getElementById('customRepeats').value);

                const response = await fetch('/generate', { method: 'POST', body: formData });
                const data = await response.json();

                if (data.success) {
                    customCachedAudio = data.audio_url;
                    audioPlayer.src = data.audio_url;
                    document.getElementById('customDownloadLink').href = data.audio_url;
                    audioRow.style.display = 'flex';
                    audioPlayer.oncanplay = () => audioPlayer.play();
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (err) {
                alert('Error: ' + err.message);
            } finally {
                btn.disabled = false;
                btn.classList.remove('loading');
            }
        }

        // Load songs on page load
        async function loadSongs() {
            try {
                const response = await fetch('/api/songs');
                songs = await response.json();
                renderSongs(songs, []);
            } catch (err) {
                document.getElementById('songList').innerHTML =
                    '<div class="no-songs">Could not load songs</div>';
            }
        }

        function renderSongItem(song, lyricSnippet = null) {
            const keyDisplay = Array.isArray(song.key) ? song.key.join('/') : (song.key || '?');
            return `
                <div class="song-item" onclick="selectSong('${song.id}')" id="song-${song.id}">
                    <div class="song-title">${song.title}</div>
                    <div class="song-meta">
                        <span class="song-key">${keyDisplay}</span>
                        <span class="song-type">${song.type || ''}</span>
                    </div>
                    ${lyricSnippet ? `<div class="lyric-match-snippet">${lyricSnippet}</div>` : ''}
                </div>
            `;
        }

        function renderSongs(songList, lyricMatches = []) {
            const container = document.getElementById('songList');
            if (songList.length === 0 && lyricMatches.length === 0) {
                container.innerHTML = '<div class="no-songs">No songs found</div>';
                return;
            }

            let html = '';

            // Title/key matches
            if (songList.length > 0) {
                html += songList.map(song => renderSongItem(song)).join('');
            }

            // Lyric matches (separate section)
            if (lyricMatches.length > 0) {
                html += '<div class="song-list-section">Lyric Matches</div>';
                html += lyricMatches.map(match => renderSongItem(match.song, match.snippet)).join('');
            }

            container.innerHTML = html;
        }

        function filterSongs(query) {
            const q = query.toLowerCase().trim();

            if (!q) {
                // No query - show all songs
                renderSongs(songs, []);
                return;
            }

            // Title matches (also check key)
            const titleMatches = songs.filter(s => {
                if (s.title && s.title.toLowerCase().includes(q)) return true;
                if (!s.key) return false;
                // Handle key as string or array
                const keys = Array.isArray(s.key) ? s.key : [s.key];
                return keys.some(k => k.toLowerCase().includes(q));
            });

            // Get IDs of title matches to exclude from lyric search
            const titleMatchIds = new Set(titleMatches.map(s => s.id));

            // Lyric matches (only vocal songs not already in title matches)
            const lyricMatches = [];
            for (const song of songs) {
                if (titleMatchIds.has(song.id)) continue;
                if (song.type !== 'vocal' || !song.lyrics) continue;

                if (typeof song.lyrics !== 'string') continue;
                const lyricsLower = song.lyrics.toLowerCase();
                const idx = lyricsLower.indexOf(q);
                if (idx !== -1) {
                    // Extract snippet around the match
                    const start = Math.max(0, idx - 20);
                    const end = Math.min(song.lyrics.length, idx + q.length + 30);
                    let snippet = song.lyrics.substring(start, end)
                        .replace(/\\n/g, ' ')
                        .replace(/<[^>]+>/g, '');
                    if (start > 0) snippet = '...' + snippet;
                    if (end < song.lyrics.length) snippet = snippet + '...';
                    // Highlight the match using simple string replacement
                    const lowerSnippet = snippet.toLowerCase();
                    const matchIdx = lowerSnippet.indexOf(q);
                    if (matchIdx !== -1) {
                        const before = snippet.substring(0, matchIdx);
                        const match = snippet.substring(matchIdx, matchIdx + q.length);
                        const after = snippet.substring(matchIdx + q.length);
                        snippet = before + '<mark>' + match + '</mark>' + after;
                    }
                    lyricMatches.push({ song, snippet });
                }
            }

            renderSongs(titleMatches, lyricMatches);
        }

        const majorKeys = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
        const minorKeys = ['Cm', 'C#m', 'Dm', 'D#m', 'Em', 'Fm', 'F#m', 'Gm', 'G#m', 'Am', 'A#m', 'Bm'];
        const noteNames = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
        const noteToSemitone = {'C':0, 'C#':1, 'Db':1, 'D':2, 'D#':3, 'Eb':3, 'E':4, 'F':5,
                                'F#':6, 'Gb':6, 'G':7, 'G#':8, 'Ab':8, 'A':9, 'A#':10, 'Bb':10, 'B':11};

        function isMinorKey(key) {
            if (!key) return false;
            const k = Array.isArray(key) ? key[0] : key;
            return k && k.endsWith('m') && !k.endsWith('#m') || k.toLowerCase().includes('min');
        }

        function getPrimaryKey(key) {
            // Get the first key if it's an array, otherwise return the key
            return Array.isArray(key) ? key[0] : (key || 'C');
        }

        function parseChord(chordName) {
            if (!chordName || chordName === 'rest') return { root: null, suffix: '' };
            let root, suffix;
            if (chordName.length > 1 && (chordName[1] === '#' || chordName[1] === 'b')) {
                root = chordName.substring(0, 2);
                suffix = chordName.substring(2);
            } else {
                root = chordName[0];
                suffix = chordName.substring(1);
            }
            return { root, suffix };
        }

        function getKeySemitone(key) {
            const root = key.replace(/m$/, '').replace(/min$/i, '');
            return noteToSemitone[root] || 0;
        }

        function transposeChord(chord, semitones) {
            if (chord === 'rest') return 'rest';
            const { root, suffix } = parseChord(chord);
            if (!root) return chord;
            const currentSemitone = noteToSemitone[root] || 0;
            const newSemitone = (currentSemitone + semitones + 12) % 12;
            return noteNames[newSemitone] + suffix;
        }

        function transposeChordItem(item, semitones) {
            if (Array.isArray(item)) {
                return item.map(c => transposeChord(c, semitones));
            }
            return transposeChord(item, semitones);
        }

        function formatChord(chord) {
            if (chord === 'rest') {
                return '<span class="chord rest">rest</span>';
            } else if (Array.isArray(chord)) {
                if (chord.length === 1) {
                    // Half bar - shorter width, no brackets
                    return `<span class="chord half-bar">${chord[0]}</span>`;
                } else {
                    // Split bar - two chords spaced apart
                    return `<span class="chord split-bar"><span>${chord[0]}</span><span>${chord[1]}</span></span>`;
                }
            } else {
                return `<span class="chord">${chord}</span>`;
            }
        }

        function formatLyrics(lyrics) {
            if (!lyrics) return '';
            // Parse <chorus>...</chorus> tags and wrap in styled spans
            let html = lyrics
                .replace(/<chorus>([\\s\\S]*?)<\\/chorus>/g, '<span class="chorus">$1</span>')
                .replace(/\\n\\n/g, '</span><span class="verse">')
                .trim();
            return '<span class="verse">' + html + '</span>';
        }

        function updateChordPreview() {
            if (!selectedSong) return;

            const targetKey = document.getElementById('songKey').value;
            const originalKey = getPrimaryKey(selectedSong.key);
            const semitones = getKeySemitone(targetKey) - getKeySemitone(originalKey);

            // Update meta to show transposition
            const transposedLabel = targetKey !== originalKey
                ? `Original: ${originalKey} → ${targetKey}`
                : `Key: ${originalKey}`;
            document.getElementById('previewMeta').textContent = transposedLabel;

            // Render sections with transposed chords
            const sectionsHtml = selectedSong.sections.map(section => {
                const chordHtml = section.chords.map(chord => {
                    const transposed = transposeChordItem(chord, semitones);
                    return formatChord(transposed);
                }).join(' ');
                const repeatLabel = section.repeats > 1 ? ` (x${section.repeats})` : '';
                return `
                    <div class="preview-section">
                        <div class="preview-section-name">${section.name}${repeatLabel}</div>
                        <div class="preview-chords">${chordHtml}</div>
                    </div>
                `;
            }).join('');
            document.getElementById('previewSections').innerHTML = sectionsHtml;
        }

        function selectSong(songId) {
            document.querySelectorAll('.song-item').forEach(el => el.classList.remove('selected'));
            document.getElementById(`song-${songId}`).classList.add('selected');
            selectedSong = songs.find(s => s.id === songId);

            // Show controls, hide prompt and custom editor
            document.getElementById('noSongSelected').style.display = 'none';
            document.getElementById('customSongEditor').style.display = 'none';
            document.getElementById('songControls').style.display = 'block';

            // Populate key selector - only show keys matching major/minor
            const keySelect = document.getElementById('songKey');
            const primaryKey = getPrimaryKey(selectedSong.key);
            const isMinor = isMinorKey(primaryKey);
            const keys = isMinor ? minorKeys : majorKeys;
            keySelect.innerHTML = keys.map(key =>
                `<option value="${key}" ${key === primaryKey ? 'selected' : ''}>${key}</option>`
            ).join('');

            // Update title
            document.getElementById('previewTitle').textContent = selectedSong.title;

            // Render chords (will use original key since dropdown is set to original)
            updateChordPreview();

            // Render lyrics for vocal songs
            const lyricsSection = document.getElementById('lyricsSection');
            const lyricsContent = document.getElementById('lyricsContent');
            if (selectedSong.type === 'vocal' && selectedSong.lyrics) {
                lyricsContent.innerHTML = formatLyrics(selectedSong.lyrics);
                lyricsSection.style.display = 'block';
            } else {
                lyricsSection.style.display = 'none';
            }

            // Reset audio when song changes
            clearCachedAudio();
        }

        let cachedAudioUrl = null;

        function clearCachedAudio() {
            cachedAudioUrl = null;
            document.getElementById('audioRow').style.display = 'none';
            document.getElementById('songAudioPlayer').src = '';
        }

        // Clear cache when settings change
        document.getElementById('songKey').addEventListener('change', clearCachedAudio);
        document.getElementById('songTempo').addEventListener('change', clearCachedAudio);
        document.getElementById('songRepeats').addEventListener('change', clearCachedAudio);

        async function playOrGenerate() {
            if (!selectedSong) return;

            const btn = document.getElementById('playBtn');
            const audioPlayer = document.getElementById('songAudioPlayer');
            const audioRow = document.getElementById('audioRow');

            // If we have cached audio, just play it
            if (cachedAudioUrl) {
                audioPlayer.play();
                return;
            }

            // Generate new audio
            btn.disabled = true;
            btn.classList.add('loading');

            try {
                const formData = new FormData();
                formData.append('song_id', selectedSong.id);
                formData.append('tempo', document.getElementById('songTempo').value);
                formData.append('repeats', document.getElementById('songRepeats').value);
                formData.append('key', document.getElementById('songKey').value);
                formData.append('original_key', getPrimaryKey(selectedSong.key));

                const response = await fetch('/generate_song', { method: 'POST', body: formData });
                const data = await response.json();

                if (data.success) {
                    cachedAudioUrl = data.audio_url;
                    audioPlayer.src = data.audio_url;
                    document.getElementById('songDownloadLink').href = data.audio_url;
                    document.getElementById('songDownloadLink').textContent = 'Download';
                    audioRow.style.display = 'flex';

                    // Auto-play when loaded
                    audioPlayer.oncanplay = () => audioPlayer.play();
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (err) {
                alert('Error: ' + err.message);
            } finally {
                btn.disabled = false;
                btn.classList.remove('loading');
            }
        }

        function setProgression(prog) {
            document.getElementById('progression').value = prog;
        }


        // Load songs on startup
        loadSongs();
    </script>
</body>
</html>
"""


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
    import re

    progression_str = progression_str.strip()
    result = []

    # Pattern to match either [chord, chord] or single chord
    # Handles optional spaces around commas
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


@app.route('/')
def index():
    """Serve the main page."""
    return render_template_string(HTML_TEMPLATE)


@app.route('/generate', methods=['POST'])
def generate():
    """Generate a backing track from the form input."""
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
            'lyrics': data.get('lyrics', '')  # Include lyrics for vocal songs
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


if __name__ == '__main__':
    print("Starting Bluegrass Backing Track Generator...")
    print("Open http://localhost:5000 in your browser")
    app.run(debug=True, port=5000)
