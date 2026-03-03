/**
 * Grass - Bluegrass Backing Track Generator
 * Main Application JavaScript
 */

/* ==========================================================================
   State Management
   ========================================================================== */

let songs = [];
let selectedSong = null;
let customCachedAudio = null;
let cachedAudioUrl = null;

// Chord highlighting state
let highlightAnimationId = null;
let currentHighlightedBar = -1;
let chordTimingMap = [];

/* ==========================================================================
   Music Theory - Key/Chord Transposition
   ========================================================================== */

const majorKeys = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
const minorKeys = ['Cm', 'C#m', 'Dm', 'D#m', 'Em', 'Fm', 'F#m', 'Gm', 'G#m', 'Am', 'A#m', 'Bm'];
const noteNames = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
const noteToSemitone = {
    'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4, 'F': 5,
    'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8, 'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11
};

function isMinorKey(key) {
    if (!key) return false;
    const k = Array.isArray(key) ? key[0] : key;
    return k && k.endsWith('m') && !k.endsWith('#m') || k.toLowerCase().includes('min');
}

function getPrimaryKey(key) {
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

/* ==========================================================================
   Tempo Controls
   ========================================================================== */

function updateTempoDisplay(prefix) {
    const slider = document.getElementById(prefix + 'Tempo');
    const display = document.getElementById(prefix + 'TempoValue');
    display.textContent = slider.value;
}

function adjustTempo(prefix, delta) {
    const slider = document.getElementById(prefix + 'Tempo');
    const newVal = Math.max(60, Math.min(160, parseInt(slider.value) + delta));
    slider.value = newVal;
    updateTempoDisplay(prefix);
    if (prefix === 'song') {
        clearCachedAudio();
    } else {
        clearCustomCache();
    }
}

/* ==========================================================================
   Audio Playback & Chord Highlighting
   ========================================================================== */

function setPlayButtonState(btn, isPlaying) {
    const playIcon = btn.querySelector('.icon-play');
    const stopIcon = btn.querySelector('.icon-stop');
    if (isPlaying) {
        playIcon.style.display = 'none';
        stopIcon.style.display = 'block';
        btn.title = 'Stop';
    } else {
        playIcon.style.display = 'block';
        stopIcon.style.display = 'none';
        btn.title = 'Play';
    }
}

function getBarDuration() {
    // Bar duration in seconds
    // For 4/4 cut-time: internal tempo is doubled, so each bar = 120 / user_tempo
    // For 3/4 waltz: 3 beats per bar, so each bar = 90 / user_tempo
    const tempo = parseInt(document.getElementById('songTempo').value) || 110;
    const isWaltz = selectedSong && selectedSong.signature === 'waltz';
    return isWaltz ? (90 / tempo) : (120 / tempo);
}

function highlightChordAtTime(currentTime) {
    const barDuration = getBarDuration();
    let elapsed = 0;
    let targetBar = -1;

    // Find which bar we're in based on cumulative time
    for (let i = 0; i < chordTimingMap.length; i++) {
        const chordDuration = chordTimingMap[i].duration * barDuration;
        if (currentTime >= elapsed && currentTime < elapsed + chordDuration) {
            targetBar = chordTimingMap[i].barIndex;
            break;
        }
        elapsed += chordDuration;
    }

    // Only update DOM if bar changed
    if (targetBar !== currentHighlightedBar) {
        // Remove previous highlight
        document.querySelectorAll('.preview-chords .chord.playing').forEach(el => {
            el.classList.remove('playing');
        });
        // Add new highlight
        if (targetBar >= 0) {
            const chordEl = document.querySelector(`.preview-chords .chord[data-bar="${targetBar}"]`);
            if (chordEl) chordEl.classList.add('playing');
        }
        currentHighlightedBar = targetBar;
    }
}

function startChordHighlighting(audioPlayer) {
    function animate() {
        if (audioPlayer.paused) return;
        highlightChordAtTime(audioPlayer.currentTime);
        highlightAnimationId = requestAnimationFrame(animate);
    }
    animate();
}

function stopChordHighlighting() {
    if (highlightAnimationId) {
        cancelAnimationFrame(highlightAnimationId);
        highlightAnimationId = null;
    }
    currentHighlightedBar = -1;
    document.querySelectorAll('.preview-chords .chord.playing').forEach(el => {
        el.classList.remove('playing');
    });
}

function clearCachedAudio() {
    cachedAudioUrl = null;
    const audioPlayer = document.getElementById('songAudioPlayer');
    audioPlayer.oncanplay = null;
    audioPlayer.pause();
    audioPlayer.src = '';
    setPlayButtonState(document.getElementById('playBtn'), false);
    stopChordHighlighting();
}

function clearCustomCache() {
    customCachedAudio = null;
    const customAudio = document.getElementById('customAudioPlayer');
    customAudio.oncanplay = null;
    customAudio.pause();
    customAudio.src = '';
    setPlayButtonState(document.getElementById('customPlayBtn'), false);
}

async function playOrGenerate() {
    if (!selectedSong) return;

    const btn = document.getElementById('playBtn');
    const audioPlayer = document.getElementById('songAudioPlayer');

    // If playing, stop it
    if (!audioPlayer.paused) {
        audioPlayer.oncanplay = null;
        audioPlayer.pause();
        audioPlayer.currentTime = 0;
        setPlayButtonState(btn, false);
        stopChordHighlighting();
        return;
    }

    // If we have cached audio, just play it
    if (cachedAudioUrl) {
        audioPlayer.play();
        setPlayButtonState(btn, true);
        startChordHighlighting(audioPlayer);
        return;
    }

    // Generate new audio
    btn.disabled = true;
    btn.classList.add('loading');

    try {
        const formData = new FormData();
        formData.append('song_id', selectedSong.id);
        formData.append('tempo', document.getElementById('songTempo').value);
        formData.append('repeats', '1');
        formData.append('key', document.getElementById('songKey').value);
        formData.append('original_key', getPrimaryKey(selectedSong.key));

        const response = await fetch('/generate_song', { method: 'POST', body: formData });
        const data = await response.json();

        if (data.success) {
            cachedAudioUrl = data.audio_url;
            audioPlayer.src = data.audio_url;

            // Auto-play when loaded
            audioPlayer.oncanplay = () => {
                audioPlayer.play();
                setPlayButtonState(btn, true);
                startChordHighlighting(audioPlayer);
            };
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

async function playCustom() {
    const btn = document.getElementById('customPlayBtn');
    const audioPlayer = document.getElementById('customAudioPlayer');

    // If playing, stop it
    if (!audioPlayer.paused) {
        audioPlayer.oncanplay = null;
        audioPlayer.pause();
        audioPlayer.currentTime = 0;
        setPlayButtonState(btn, false);
        return;
    }

    // If cached, just play
    if (customCachedAudio) {
        audioPlayer.play();
        setPlayButtonState(btn, true);
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
        formData.append('repeats', '1');

        const response = await fetch('/generate', { method: 'POST', body: formData });
        const data = await response.json();

        if (data.success) {
            customCachedAudio = data.audio_url;
            audioPlayer.src = data.audio_url;
            audioPlayer.oncanplay = () => {
                audioPlayer.play();
                setPlayButtonState(btn, true);
            };
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

/* ==========================================================================
   Custom Song Editor
   ========================================================================== */

function createCustomSong() {
    // Deselect any selected song
    document.querySelectorAll('.song-item').forEach(el => el.classList.remove('selected'));
    selectedSong = null;

    // Clear saved song
    localStorage.removeItem('selectedSongId');

    // Hide other views, show custom editor
    document.getElementById('noSongSelected').style.display = 'none';
    document.getElementById('songControls').style.display = 'none';
    document.getElementById('customSongEditor').style.display = 'block';

    // Reset audio
    const customAudio = document.getElementById('customAudioPlayer');
    customAudio.pause();
    customAudio.src = '';
    customCachedAudio = null;
    setPlayButtonState(document.getElementById('customPlayBtn'), false);
}

/* ==========================================================================
   Song List & Search
   ========================================================================== */

async function loadSongs() {
    try {
        const response = await fetch('/api/songs');
        songs = await response.json();
        renderSongs(songs, []);

        // Restore previously selected song
        const savedSongId = localStorage.getItem('selectedSongId');
        if (savedSongId && songs.find(s => s.id === savedSongId)) {
            selectSong(savedSongId);
        }
    } catch (err) {
        document.getElementById('songList').innerHTML =
            '<div class="no-songs">Could not load songs</div>';
    }
}

function renderSongItem(song, lyricSnippet = null) {
    const keyDisplay = Array.isArray(song.key) ? song.key.join('/') : (song.key || '?');
    const isVocal = song.type === 'vocal';
    if (lyricSnippet) {
        return `
            <div class="song-item has-snippet" onclick="selectSong('${song.id}')" id="song-${song.id}">
                <span class="song-title">${song.title}</span>
                ${isVocal ? '<span class="song-vocal">vocal</span>' : ''}
                <span class="song-key">${keyDisplay}</span>
                <div class="lyric-match-snippet">${lyricSnippet}</div>
            </div>
        `;
    }
    return `
        <div class="song-item" onclick="selectSong('${song.id}')" id="song-${song.id}">
            <span class="song-title">${song.title}</span>
            ${isVocal ? '<span class="song-vocal">vocal</span>' : ''}
            <span class="song-key">${keyDisplay}</span>
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
                .replace(/\n/g, ' ')
                .replace(/<[^>]+>/g, '');
            if (start > 0) snippet = '...' + snippet;
            if (end < song.lyrics.length) snippet = snippet + '...';
            // Highlight the match
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

/* ==========================================================================
   Song Display & Preview
   ========================================================================== */

function formatChord(chord, barIndex) {
    const dataAttr = `data-bar="${barIndex}"`;
    if (chord === 'rest') {
        return `<span class="chord rest" ${dataAttr}>rest</span>`;
    } else if (Array.isArray(chord)) {
        if (chord.length === 1) {
            // Half bar - shorter width, no brackets
            return `<span class="chord half-bar" ${dataAttr}>${chord[0]}</span>`;
        } else {
            // Split bar - two chords spaced apart
            return `<span class="chord split-bar" ${dataAttr}><span>${chord[0]}</span><span>${chord[1]}</span></span>`;
        }
    } else {
        return `<span class="chord" ${dataAttr}>${chord}</span>`;
    }
}

function extractYouTubeId(url) {
    if (!url) return null;
    // Handle youtu.be/VIDEO_ID format
    let match = url.match(/youtu\.be\/([a-zA-Z0-9_-]+)/);
    if (match) return match[1];
    // Handle youtube.com/watch?v=VIDEO_ID format
    match = url.match(/youtube\.com\/watch\?v=([a-zA-Z0-9_-]+)/);
    if (match) return match[1];
    // Handle youtube.com/embed/VIDEO_ID format
    match = url.match(/youtube\.com\/embed\/([a-zA-Z0-9_-]+)/);
    if (match) return match[1];
    return null;
}

function formatLyrics(lyrics) {
    if (!lyrics) return '';
    // Parse <chorus>...</chorus> tags and wrap in styled spans
    let html = lyrics
        .replace(/<chorus>([\s\S]*?)<\/chorus>/g, '<span class="chorus">$1</span>')
        .replace(/\n\n/g, '</span><span class="verse">')
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
        ? `(from ${originalKey})`
        : '';
    document.getElementById('previewMeta').textContent = transposedLabel;

    // Build timing map and render sections
    chordTimingMap = [];
    let barIndex = 0;

    const sectionsHtml = selectedSong.sections.map(section => {
        const repeats = section.repeats || 1;

        // Render chords once (display)
        const chordHtml = section.chords.map((chord, chordIdx) => {
            const transposed = transposeChordItem(chord, semitones);
            return formatChord(transposed, barIndex + chordIdx);
        }).join(' ');

        // Build timing map for all repeats (playback)
        for (let r = 0; r < repeats; r++) {
            section.chords.forEach((chord, chordIdx) => {
                const duration = (Array.isArray(chord) && chord.length === 1) ? 0.5 : 1;
                // Map back to the displayed bar index (same chords repeat)
                chordTimingMap.push({ barIndex: barIndex + chordIdx, duration });
            });
        }
        barIndex += section.chords.length;

        const repeatLabel = repeats > 1 ? ` (x${repeats})` : '';
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

    // Set default tempo based on song type (waltzes are slower)
    const defaultTempo = selectedSong.signature === 'waltz' ? 70 : 110;
    document.getElementById('songTempo').value = defaultTempo;
    updateTempoDisplay('song');

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

    // Render demo videos
    const demoVideos = document.getElementById('demoVideos');
    const demosCol = document.getElementById('demosCol');
    const mobileTabs = document.getElementById('mobileTabs');
    const chordsCol = document.getElementById('chordsLyricsCol');
    const allDemos = [...(selectedSong.featured_demo || []), ...(selectedSong.demo || [])];

    const hasDemos = allDemos.length > 0;

    if (hasDemos) {
        demoVideos.innerHTML = allDemos.map(url => {
            const videoId = extractYouTubeId(url);
            if (!videoId) return '';
            return `<div class="demo-video">
                <iframe src="https://www.youtube.com/embed/${videoId}"
                        allowfullscreen loading="lazy"></iframe>
            </div>`;
        }).join('');
    }

    // Show/hide demos column and tabs based on whether demos exist
    demosCol.style.display = hasDemos ? '' : 'none';
    mobileTabs.style.display = hasDemos && window.innerWidth <= 900 ? 'flex' : '';

    // Reset mobile tabs to show chords first
    chordsCol.classList.remove('hidden');
    if (window.innerWidth <= 900) {
        demosCol.classList.add('hidden');
    } else {
        demosCol.classList.remove('hidden');
    }
    document.querySelectorAll('.mobile-tab').forEach((t, i) => {
        t.classList.toggle('active', i === 0);
    });

    // Reset audio when song changes
    clearCachedAudio();

    // Remember selected song for page refresh
    localStorage.setItem('selectedSongId', songId);
}

/* ==========================================================================
   Mobile Tab Switching
   ========================================================================== */

function showMobileTab(tab) {
    const chordsCol = document.getElementById('chordsLyricsCol');
    const demosCol = document.getElementById('demosCol');
    const tabs = document.querySelectorAll('.mobile-tab');

    tabs.forEach(t => t.classList.remove('active'));

    if (tab === 'chords') {
        chordsCol.classList.remove('hidden');
        demosCol.classList.add('hidden');
        tabs[0].classList.add('active');
    } else {
        chordsCol.classList.add('hidden');
        demosCol.classList.remove('hidden');
        tabs[1].classList.add('active');
    }
}

/* ==========================================================================
   Legacy/Utility Functions
   ========================================================================== */

function setProgression(prog) {
    document.getElementById('progression').value = prog;
}

/* ==========================================================================
   Initialization
   ========================================================================== */

// Set up event listeners when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Clear cache when settings change
    document.getElementById('songKey').addEventListener('change', clearCachedAudio);
    document.getElementById('songTempo').addEventListener('input', clearCachedAudio);

    // Load songs on startup
    loadSongs();
});
