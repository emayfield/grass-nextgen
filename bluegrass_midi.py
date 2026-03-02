"""
Bluegrass MIDI Backing Track Generator

Generates MIDI files with the classic "boom-chuck" rhythm:
- Bass: root on beat 1, 5th on beat 3
- Mandolin: chord chop on beats 2 and 4
- Guitar: boom-chuck (bass notes on 1/3, strums on 2/4)
"""

from mido import MidiFile, MidiTrack, Message, MetaMessage

# MIDI note numbers for C0 = 12, C1 = 24, etc.
# We'll use C4 = 60 as middle C reference
NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
NOTE_TO_SEMITONE = {name: i for i, name in enumerate(NOTE_NAMES)}
# Add flats as aliases
NOTE_TO_SEMITONE.update({'Db': 1, 'Eb': 3, 'Fb': 4, 'Gb': 6, 'Ab': 8, 'Bb': 10, 'Cb': 11})

# General MIDI program numbers (0-indexed)
GM_ACOUSTIC_BASS = 32
GM_ACOUSTIC_GUITAR = 25
GM_MANDOLIN = 25  # No mandolin in GM, use steel guitar or acoustic guitar

# Chord intervals (semitones from root)
CHORD_INTERVALS = {
    'major': [0, 4, 7],        # root, major 3rd, 5th
    'minor': [0, 3, 7],        # root, minor 3rd, 5th
    '7': [0, 4, 7, 10],        # dominant 7th
    'maj7': [0, 4, 7, 11],     # major 7th
    'm7': [0, 3, 7, 10],       # minor 7th
}


def parse_chord(chord_name):
    """
    Parse a chord name into root note and chord type.

    Examples:
        'G' -> ('G', 'major')
        'Am' -> ('A', 'minor')
        'D7' -> ('D', '7')
        'F#m' -> ('F#', 'minor')
    """
    chord_name = chord_name.strip()

    # Extract root note (1 or 2 characters)
    if len(chord_name) > 1 and chord_name[1] in '#b':
        root = chord_name[:2]
        suffix = chord_name[2:]
    else:
        root = chord_name[0]
        suffix = chord_name[1:]

    # Determine chord type from suffix
    if suffix == '' or suffix.lower() == 'maj':
        chord_type = 'major'
    elif suffix.lower() == 'm' or suffix.lower() == 'min':
        chord_type = 'minor'
    elif suffix == '7':
        chord_type = '7'
    elif suffix.lower() == 'maj7':
        chord_type = 'maj7'
    elif suffix.lower() == 'm7' or suffix.lower() == 'min7':
        chord_type = 'm7'
    else:
        chord_type = 'major'  # default

    return root, chord_type


# All possible keys for transposition (using sharps for simplicity)
ALL_KEYS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
# Common keys used in bluegrass (for UI display)
COMMON_KEYS = ['C', 'D', 'E', 'F', 'G', 'A', 'B', 'Am', 'Dm', 'Em']


def normalize_key(key):
    """
    Normalize a key name to use sharps and extract if it's minor.

    Returns (root, is_minor) tuple.
    """
    key = key.strip()

    # Check for minor
    is_minor = False
    if key.endswith('m') and not key.endswith('#m') and len(key) > 1:
        is_minor = True
        key = key[:-1]
    elif key.lower().endswith('min'):
        is_minor = True
        key = key[:-3]

    # Normalize flats to sharps
    flat_to_sharp = {
        'Db': 'C#', 'Eb': 'D#', 'Fb': 'E', 'Gb': 'F#',
        'Ab': 'G#', 'Bb': 'A#', 'Cb': 'B'
    }
    key = flat_to_sharp.get(key, key)

    return key, is_minor


def get_key_semitone(key):
    """Get the semitone value (0-11) for a key."""
    root, _ = normalize_key(key)
    return NOTE_TO_SEMITONE.get(root, 0)


def transpose_chord(chord_name, semitones):
    """
    Transpose a single chord by the given number of semitones.

    Args:
        chord_name: Chord name like 'G', 'Am', 'F#7'
        semitones: Number of semitones to transpose (can be negative)

    Returns:
        Transposed chord name
    """
    if chord_name == 'rest':
        return 'rest'

    root, chord_type = parse_chord(chord_name)

    # Get current semitone
    root_normalized, _ = normalize_key(root)
    current_semitone = NOTE_TO_SEMITONE.get(root_normalized, 0)

    # Calculate new semitone
    new_semitone = (current_semitone + semitones) % 12

    # Get new root name
    new_root = NOTE_NAMES[new_semitone]

    # Reconstruct chord name with suffix
    if chord_type == 'major':
        return new_root
    elif chord_type == 'minor':
        return f"{new_root}m"
    elif chord_type == '7':
        return f"{new_root}7"
    elif chord_type == 'maj7':
        return f"{new_root}maj7"
    elif chord_type == 'm7':
        return f"{new_root}m7"
    else:
        return new_root


def transpose_progression(progression, from_key, to_key):
    """
    Transpose an entire progression from one key to another.

    Args:
        progression: List of chords (can include lists for split/half bars)
        from_key: Original key (e.g., 'G', 'Am')
        to_key: Target key (e.g., 'A', 'Em')

    Returns:
        Transposed progression
    """
    from_semitone = get_key_semitone(from_key)
    to_semitone = get_key_semitone(to_key)
    semitones = to_semitone - from_semitone

    if semitones == 0:
        return progression  # No transposition needed

    def transpose_item(item):
        if isinstance(item, list):
            return [transpose_chord(chord, semitones) for chord in item]
        else:
            return transpose_chord(item, semitones)

    return [transpose_item(item) for item in progression]


def note_to_midi(note_name, octave):
    """Convert note name and octave to MIDI note number."""
    semitone = NOTE_TO_SEMITONE.get(note_name, 0)
    return 12 + (octave * 12) + semitone


def get_chord_notes(chord_name, octave=4):
    """
    Get MIDI note numbers for a chord.

    Returns dict with:
        - root: root note MIDI number
        - fifth: 5th note MIDI number
        - chord_tones: list of MIDI numbers for full chord
    """
    root_name, chord_type = parse_chord(chord_name)
    root_midi = note_to_midi(root_name, octave)

    intervals = CHORD_INTERVALS.get(chord_type, CHORD_INTERVALS['major'])
    chord_tones = [root_midi + interval for interval in intervals]

    # Fifth is always 7 semitones above root
    fifth_midi = root_midi + 7

    return {
        'root': root_midi,
        'root_name': root_name,
        'fifth': fifth_midi,
        'chord_tones': chord_tones,
        'chord_type': chord_type,
    }


def generate_bluegrass_midi(
    progression,
    tempo=120,
    time_sig=(4, 4),
    output_file='bluegrass_backing.mid',
    bass_octave=2,
    mandolin_octave=4,
    guitar_octave=3,
):
    """
    Generate a bluegrass backing track MIDI file.

    Args:
        progression: List of chord names, one per bar. e.g. ['G', 'G', 'C', 'D']
        tempo: Bluegrass tempo (half-note pulse). e.g. 110 = typical medium tempo.
               Internally doubled since bluegrass is in cut time.
        time_sig: Tuple of (beats_per_bar, beat_unit). Default (4, 4)
        output_file: Output MIDI filename
        bass_octave: Octave for bass notes (default 2, which is E1-ish range)
        mandolin_octave: Octave for mandolin chops (default 4)
        guitar_octave: Octave for guitar bass notes (default 3)

    Returns:
        Tuple of (path to generated MIDI file, duration in seconds)
    """
    # Bluegrass is in cut time - double the tempo for the actual quarter note pulse
    actual_tempo = tempo * 2

    mid = MidiFile(type=1)  # Type 1 = multiple tracks, synchronous
    ticks_per_beat = mid.ticks_per_beat  # Default 480

    beats_per_bar = time_sig[0]
    ticks_per_bar = ticks_per_beat * beats_per_bar

    # Note durations in ticks
    quarter_note = ticks_per_beat
    eighth_note = ticks_per_beat // 2

    # Chop duration (short, percussive)
    chop_duration = ticks_per_beat // 4  # 16th note

    # Bass note duration
    bass_duration = ticks_per_beat // 2  # 8th note, leaves space

    # Create tracks
    # Track 0: Tempo and time signature
    tempo_track = MidiTrack()
    mid.tracks.append(tempo_track)
    tempo_track.append(MetaMessage('set_tempo', tempo=int(60_000_000 / actual_tempo), time=0))
    tempo_track.append(MetaMessage('time_signature',
                                    numerator=time_sig[0],
                                    denominator=time_sig[1],
                                    time=0))
    tempo_track.append(MetaMessage('track_name', name='Tempo Track', time=0))

    # Track 1: Bass
    bass_track = MidiTrack()
    mid.tracks.append(bass_track)
    bass_track.append(MetaMessage('track_name', name='Bass', time=0))
    bass_track.append(Message('program_change', channel=0, program=GM_ACOUSTIC_BASS, time=0))

    # Track 2: Mandolin
    mando_track = MidiTrack()
    mid.tracks.append(mando_track)
    mando_track.append(MetaMessage('track_name', name='Mandolin', time=0))
    mando_track.append(Message('program_change', channel=1, program=GM_MANDOLIN, time=0))

    # Track 3: Guitar
    guitar_track = MidiTrack()
    mid.tracks.append(guitar_track)
    guitar_track.append(MetaMessage('track_name', name='Guitar', time=0))
    guitar_track.append(Message('program_change', channel=2, program=GM_ACOUSTIC_GUITAR, time=0))

    # Generate notes for each bar
    bass_events = []
    mando_events = []
    guitar_events = []

    def add_half_bar(chord_name, bar_start, half, bass_events, mando_events, guitar_events):
        """
        Add notes for half a bar (beats 1-2 or beats 3-4).

        Args:
            chord_name: The chord to play
            bar_start: Tick position of bar start
            half: 0 for first half (beats 1-2), 1 for second half (beats 3-4)
            *_events: Event lists to append to
        """
        chord = get_chord_notes(chord_name)
        bass_root = note_to_midi(chord['root_name'], bass_octave)
        bass_fifth = bass_root + 7

        # Calculate beat positions for this half
        if half == 0:
            bass_beat = bar_start  # Beat 1
            chop_beat = bar_start + quarter_note  # Beat 2
        else:
            bass_beat = bar_start + (2 * quarter_note)  # Beat 3
            chop_beat = bar_start + (3 * quarter_note)  # Beat 4

        # Bass: always root on the downbeat of this half
        bass_events.append(('on', bass_beat, bass_root, 100 if half == 0 else 95))
        bass_events.append(('off', bass_beat + bass_duration, bass_root, 0))

        # Mandolin: chop on the backbeat
        mando_chord = [note_to_midi(chord['root_name'], mandolin_octave) + i
                       for i in CHORD_INTERVALS[chord['chord_type']]]
        for note in mando_chord:
            mando_events.append(('on', chop_beat, note, 110))
            mando_events.append(('off', chop_beat + chop_duration, note, 0))

        # Guitar: bass note on downbeat, chord strum on backbeat
        guitar_bass_root = note_to_midi(chord['root_name'], guitar_octave)
        guitar_chord = [note_to_midi(chord['root_name'], guitar_octave + 1) + i
                        for i in CHORD_INTERVALS[chord['chord_type']]]

        guitar_events.append(('on', bass_beat, guitar_bass_root, 85 if half == 0 else 80))
        guitar_events.append(('off', bass_beat + eighth_note, guitar_bass_root, 0))

        for note in guitar_chord:
            guitar_events.append(('on', chop_beat, note, 75 if half == 0 else 70))
            guitar_events.append(('off', chop_beat + eighth_note, note, 0))

    def add_full_bar(chord_name, bar_start, bass_events, mando_events, guitar_events):
        """Add notes for a full bar with root on 1, 5th on 3."""
        chord = get_chord_notes(chord_name)
        bass_root = note_to_midi(chord['root_name'], bass_octave)
        bass_fifth = bass_root + 7

        beat_2_start = bar_start + quarter_note
        beat_3_start = bar_start + (2 * quarter_note)
        beat_4_start = bar_start + (3 * quarter_note)

        # Bass: root on 1, 5th on 3
        bass_events.append(('on', bar_start, bass_root, 100))
        bass_events.append(('off', bar_start + bass_duration, bass_root, 0))
        bass_events.append(('on', beat_3_start, bass_fifth, 95))
        bass_events.append(('off', beat_3_start + bass_duration, bass_fifth, 0))

        # Mandolin: chop on 2 and 4
        mando_chord = [note_to_midi(chord['root_name'], mandolin_octave) + i
                       for i in CHORD_INTERVALS[chord['chord_type']]]
        for beat_start in [beat_2_start, beat_4_start]:
            for note in mando_chord:
                mando_events.append(('on', beat_start, note, 110))
                mando_events.append(('off', beat_start + chop_duration, note, 0))

        # Guitar: boom-chuck
        guitar_bass_root = note_to_midi(chord['root_name'], guitar_octave)
        guitar_bass_fifth = guitar_bass_root + 7
        guitar_chord = [note_to_midi(chord['root_name'], guitar_octave + 1) + i
                        for i in CHORD_INTERVALS[chord['chord_type']]]

        # Beat 1: bass root
        guitar_events.append(('on', bar_start, guitar_bass_root, 85))
        guitar_events.append(('off', bar_start + eighth_note, guitar_bass_root, 0))
        # Beat 2: chord strum
        for note in guitar_chord:
            guitar_events.append(('on', beat_2_start, note, 75))
            guitar_events.append(('off', beat_2_start + eighth_note, note, 0))
        # Beat 3: bass fifth
        guitar_events.append(('on', beat_3_start, guitar_bass_fifth, 80))
        guitar_events.append(('off', beat_3_start + eighth_note, guitar_bass_fifth, 0))
        # Beat 4: chord strum
        for note in guitar_chord:
            guitar_events.append(('on', beat_4_start, note, 70))
            guitar_events.append(('off', beat_4_start + eighth_note, note, 0))

    # Track position with a running tick counter (for half-measures)
    current_tick = 0
    half_bar_ticks = ticks_per_bar // 2

    for bar_entry in progression:
        if bar_entry == 'rest':
            # Full bar of rest - just advance time
            current_tick += ticks_per_bar

        elif isinstance(bar_entry, list):
            if len(bar_entry) == 1:
                # Half measure: ["G"] - only 2 beats
                chord = bar_entry[0]
                if chord != 'rest':
                    add_half_bar(chord, current_tick, 0, bass_events, mando_events, guitar_events)
                current_tick += half_bar_ticks

            elif len(bar_entry) == 2:
                # Split bar: ["C", "G"] or ["C", "rest"]
                first_chord, second_chord = bar_entry

                if first_chord != 'rest':
                    add_half_bar(first_chord, current_tick, 0, bass_events, mando_events, guitar_events)

                if second_chord != 'rest':
                    add_half_bar(second_chord, current_tick, 1, bass_events, mando_events, guitar_events)

                current_tick += ticks_per_bar
            else:
                # Unexpected list length, treat as full bar with first chord
                add_full_bar(bar_entry[0], current_tick, bass_events, mando_events, guitar_events)
                current_tick += ticks_per_bar

        else:
            # Full bar: single chord string with root-5th pattern
            add_full_bar(bar_entry, current_tick, bass_events, mando_events, guitar_events)
            current_tick += ticks_per_bar

    # Convert events to MIDI messages with delta times
    def events_to_messages(events, channel):
        """Convert absolute-time events to delta-time MIDI messages."""
        events.sort(key=lambda e: (e[1], e[0] == 'on'))  # Sort by time, note-offs first
        messages = []
        last_time = 0
        for event in events:
            event_type, abs_time, note, velocity = event
            delta = abs_time - last_time
            if event_type == 'on':
                messages.append(Message('note_on', channel=channel, note=note,
                                        velocity=velocity, time=delta))
            else:
                messages.append(Message('note_off', channel=channel, note=note,
                                        velocity=0, time=delta))
            last_time = abs_time
        return messages

    # Add messages to tracks
    for msg in events_to_messages(bass_events, 0):
        bass_track.append(msg)

    for msg in events_to_messages(mando_events, 1):
        mando_track.append(msg)

    for msg in events_to_messages(guitar_events, 2):
        guitar_track.append(msg)

    # End of track messages
    for track in [tempo_track, bass_track, mando_track, guitar_track]:
        track.append(MetaMessage('end_of_track', time=0))

    # Calculate duration in seconds
    # current_tick is the total ticks, ticks_per_beat is 480
    # actual_tempo is in BPM, so duration = ticks / ticks_per_beat / (actual_tempo / 60)
    duration_seconds = current_tick / ticks_per_beat / (actual_tempo / 60)

    # Save
    mid.save(output_file)
    return output_file, duration_seconds


# Convenience function for single chord
def generate_bar(chord, bars=1, **kwargs):
    """Generate one or more bars of a single chord."""
    progression = [chord] * bars
    return generate_bluegrass_midi(progression, **kwargs)


def load_songs(json_path='songs.json'):
    """Load songs from JSON file."""
    import json
    from pathlib import Path

    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"Songs file not found: {json_path}")

    with open(path) as f:
        return json.load(f)


def get_song_progression(song_data, sections=None):
    """
    Extract the full chord progression from a song.

    Args:
        song_data: Dict with song metadata and sections
        sections: Optional list of section names to include (e.g., ['A', 'B'])
                  If None, includes all sections with their repeats

    Returns:
        List of chords (strings or lists for split/half bars)
    """
    progression = []

    for section in song_data.get('sections', []):
        # Filter by section name if specified
        if sections and section.get('name') not in sections:
            continue

        chords = section.get('chords', [])
        repeats = section.get('repeats', 1)

        # Add section chords with repeats
        for _ in range(repeats):
            progression.extend(chords)

    return progression


def generate_song(song_id, songs_data=None, json_path='songs.json',
                  sections=None, tempo=110, output_file=None, **kwargs):
    """
    Generate a backing track for a song from the library.

    Args:
        song_id: The song identifier (e.g., 'clinch_mountain_backstep')
        songs_data: Optional pre-loaded songs dict (avoids reloading JSON)
        json_path: Path to songs.json if songs_data not provided
        sections: Optional list of section names to include
        tempo: Tempo in BPM (bluegrass feel, will be doubled internally)
        output_file: Output filename (auto-generated if None)
        **kwargs: Additional args passed to generate_bluegrass_midi

    Returns:
        Tuple of (path to generated MIDI file, duration in seconds)
    """
    # Load songs if not provided
    if songs_data is None:
        songs_data = load_songs(json_path)

    if song_id not in songs_data:
        raise ValueError(f"Song not found: {song_id}")

    song = songs_data[song_id]
    progression = get_song_progression(song, sections)

    if not progression:
        raise ValueError(f"No chords found for song: {song_id}")

    # Generate output filename
    if output_file is None:
        output_file = f"{song_id}_{tempo}bpm.mid"

    return generate_bluegrass_midi(
        progression,
        tempo=tempo,
        output_file=output_file,
        **kwargs
    )


def list_songs(songs_data=None, json_path='songs.json'):
    """List all available songs with their titles and keys."""
    if songs_data is None:
        songs_data = load_songs(json_path)

    songs = []
    for song_id, data in songs_data.items():
        songs.append({
            'id': song_id,
            'title': data.get('title', song_id),
            'key': data.get('key', '?'),
            'type': data.get('type', 'unknown'),
            'sections': [s.get('name') for s in data.get('sections', [])]
        })

    return sorted(songs, key=lambda s: s['title'])


if __name__ == '__main__':
    # Example: Generate a simple G-C-D progression
    progression = ['G', 'G', 'C', 'D'] * 4  # 16 bars
    output, duration = generate_bluegrass_midi(
        progression,
        tempo=110,
        output_file='bluegrass_example.mid'
    )
    print(f"Generated: {output} ({duration:.2f}s)")

    # Example: Single bar of G
    output2, duration2 = generate_bar('G', bars=1, output_file='g_one_bar.mid')
    print(f"Generated: {output2} ({duration2:.2f}s)")
