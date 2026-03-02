"""
MIDI to MP3 Converter

Converts MIDI files to MP3 using FluidSynth and a SoundFont.

Requirements:
    - FluidSynth: brew install fluid-synth
    - ffmpeg: brew install ffmpeg
    - A SoundFont file (.sf2) - script can download one if needed

Usage:
    python midi_to_mp3.py input.mid output.mp3
    python midi_to_mp3.py input.mid output.mp3 --soundfont /path/to/soundfont.sf2
"""

import argparse
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

# Default SoundFont location - prefer MuseScore_General for better instrument quality
DEFAULT_SOUNDFONT_DIR = Path(__file__).parent / "soundfonts"
DEFAULT_SOUNDFONT = DEFAULT_SOUNDFONT_DIR / "MuseScore_General.sf2"
FALLBACK_SOUNDFONT = DEFAULT_SOUNDFONT_DIR / "GeneralUser_GS.sf2"

# URL for a free General MIDI SoundFont (MuseScore General - high quality)
SOUNDFONT_URL = "https://ftp.osuosl.org/pub/musescore/soundfont/MuseScore_General/MuseScore_General.sf2"
SOUNDFONT_SIZE_MB = 206  # Approximate size for progress indication


def check_dependencies():
    """Check that required external tools are installed."""
    missing = []

    # Check FluidSynth
    try:
        result = subprocess.run(
            ["fluidsynth", "--version"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            missing.append("fluidsynth")
    except FileNotFoundError:
        missing.append("fluidsynth")

    # Check ffmpeg
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            missing.append("ffmpeg")
    except FileNotFoundError:
        missing.append("ffmpeg")

    if missing:
        print("Missing dependencies:")
        for dep in missing:
            print(f"  - {dep}")
        print("\nInstall with:")
        print("  brew install fluid-synth ffmpeg")
        return False

    return True


def download_soundfont(destination):
    """Download a free General MIDI SoundFont."""
    print(f"Downloading SoundFont (~{SOUNDFONT_SIZE_MB}MB)...")
    print(f"Source: {SOUNDFONT_URL}")

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    def progress_hook(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            percent = min(100, downloaded * 100 // total_size)
            mb_downloaded = downloaded / (1024 * 1024)
            mb_total = total_size / (1024 * 1024)
            print(f"\r  Progress: {percent}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)", end="")

    try:
        urllib.request.urlretrieve(SOUNDFONT_URL, destination, progress_hook)
        print("\n  Download complete!")
        return True
    except Exception as e:
        print(f"\n  Download failed: {e}")
        print("\nYou can manually download a SoundFont from:")
        print("  - https://musical-artifacts.com/artifacts?tags=soundfont")
        print("  - https://github.com/FluidSynth/fluidsynth/wiki/SoundFont")
        return False


def find_soundfont(specified_path=None):
    """Find a usable SoundFont file."""
    # Use specified path if provided
    if specified_path:
        path = Path(specified_path)
        if path.exists():
            return path
        else:
            print(f"Specified SoundFont not found: {specified_path}")
            return None

    # Check default location (MuseScore_General preferred)
    if DEFAULT_SOUNDFONT.exists():
        return DEFAULT_SOUNDFONT

    # Check fallback location (GeneralUser_GS)
    if FALLBACK_SOUNDFONT.exists():
        return FALLBACK_SOUNDFONT

    # Check common system locations
    common_locations = [
        "/usr/share/sounds/sf2/FluidR3_GM.sf2",
        "/usr/share/soundfonts/FluidR3_GM.sf2",
        "/usr/local/share/fluidsynth/FluidR3_GM.sf2",
        Path.home() / ".fluidsynth" / "FluidR3_GM.sf2",
        # Homebrew FluidSynth bundled soundfont
        "/opt/homebrew/Cellar/fluid-synth/2.5.3/share/fluid-synth/sf2/VintageDreamsWaves-v2.sf2",
        "/opt/homebrew/share/fluid-synth/sf2/VintageDreamsWaves-v2.sf2",
    ]

    # Also search for any sf2 file in homebrew fluidsynth
    homebrew_sf2 = Path("/opt/homebrew/Cellar/fluid-synth")
    if homebrew_sf2.exists():
        for sf2 in homebrew_sf2.rglob("*.sf2"):
            if "vintage" in sf2.name.lower() or "dreams" in sf2.name.lower():
                common_locations.insert(0, sf2)

    for loc in common_locations:
        path = Path(loc)
        if path.exists():
            return path

    # Offer to download
    print("No SoundFont found.")
    response = input(f"Download GeneralUser_GS.sf2 (~{SOUNDFONT_SIZE_MB}MB)? [y/N] ").strip().lower()
    if response == 'y':
        if download_soundfont(DEFAULT_SOUNDFONT):
            return DEFAULT_SOUNDFONT

    return None


def midi_to_wav(midi_path, wav_path, soundfont_path, sample_rate=44100):
    """Convert MIDI to WAV using FluidSynth."""
    cmd = [
        "fluidsynth",
        "-ni",                      # No interactive mode
        "-g", "1.0",                # Gain
        "-R", "1",                  # Reverb on
        "-C", "1",                  # Chorus on
        "-r", str(sample_rate),     # Sample rate
        "-F", str(wav_path),        # Output file
        str(soundfont_path),        # SoundFont
        str(midi_path)              # Input MIDI
    ]

    print(f"Rendering MIDI to WAV...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"FluidSynth error: {result.stderr}")
        return False

    return True


def wav_to_mp3(wav_path, mp3_path, bitrate="192k", trim_to_duration=None):
    """
    Convert WAV to MP3 using ffmpeg.

    Args:
        wav_path: Input WAV file path
        mp3_path: Output MP3 file path
        bitrate: MP3 bitrate (default "192k")
        trim_to_duration: If set, trim audio to this exact duration in seconds
                          for seamless looping
    """
    cmd = [
        "ffmpeg",
        "-y",                       # Overwrite output
        "-i", str(wav_path),        # Input file
    ]

    # Add duration trim if specified (for seamless looping)
    if trim_to_duration:
        cmd.extend(["-t", str(trim_to_duration)])

    cmd.extend([
        "-codec:a", "libmp3lame",   # MP3 encoder
        "-b:a", bitrate,            # Bitrate
        "-q:a", "2",                # Quality
        str(mp3_path)               # Output file
    ])

    print(f"Converting to MP3...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"ffmpeg error: {result.stderr}")
        return False

    return True


def convert_midi_to_mp3(midi_path, mp3_path, soundfont_path=None,
                         sample_rate=44100, bitrate="192k", keep_wav=False,
                         duration=None):
    """
    Convert a MIDI file to MP3.

    Args:
        midi_path: Path to input MIDI file
        mp3_path: Path for output MP3 file
        soundfont_path: Optional path to SoundFont file
        sample_rate: Audio sample rate (default 44100)
        bitrate: MP3 bitrate (default "192k")
        keep_wav: Keep intermediate WAV file (default False)
        duration: If set, trim audio to this exact duration for seamless looping

    Returns:
        True if successful, False otherwise
    """
    midi_path = Path(midi_path)
    mp3_path = Path(mp3_path)

    if not midi_path.exists():
        print(f"MIDI file not found: {midi_path}")
        return False

    # Find SoundFont
    soundfont = find_soundfont(soundfont_path)
    if not soundfont:
        print("Cannot proceed without a SoundFont.")
        return False

    print(f"Using SoundFont: {soundfont}")

    # Create temp WAV file or use specified location
    if keep_wav:
        wav_path = mp3_path.with_suffix('.wav')
    else:
        wav_fd, wav_path = tempfile.mkstemp(suffix='.wav')
        os.close(wav_fd)
        wav_path = Path(wav_path)

    try:
        # MIDI -> WAV
        if not midi_to_wav(midi_path, wav_path, soundfont, sample_rate):
            return False

        # WAV -> MP3
        if not wav_to_mp3(wav_path, mp3_path, bitrate, trim_to_duration=duration):
            return False

        print(f"Created: {mp3_path}")
        return True

    finally:
        # Clean up temp WAV
        if not keep_wav and wav_path.exists():
            wav_path.unlink()


def main():
    parser = argparse.ArgumentParser(
        description="Convert MIDI files to MP3 using FluidSynth"
    )
    parser.add_argument("input", help="Input MIDI file")
    parser.add_argument("output", help="Output MP3 file")
    parser.add_argument(
        "--soundfont", "-sf",
        help="Path to SoundFont file (.sf2)"
    )
    parser.add_argument(
        "--sample-rate", "-r",
        type=int,
        default=44100,
        help="Sample rate (default: 44100)"
    )
    parser.add_argument(
        "--bitrate", "-b",
        default="192k",
        help="MP3 bitrate (default: 192k)"
    )
    parser.add_argument(
        "--keep-wav",
        action="store_true",
        help="Keep intermediate WAV file"
    )
    parser.add_argument(
        "--download-soundfont",
        action="store_true",
        help="Download the default SoundFont and exit"
    )

    args = parser.parse_args()

    # Handle soundfont download request
    if args.download_soundfont:
        if download_soundfont(DEFAULT_SOUNDFONT):
            print(f"SoundFont saved to: {DEFAULT_SOUNDFONT}")
            sys.exit(0)
        else:
            sys.exit(1)

    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Convert
    success = convert_midi_to_mp3(
        args.input,
        args.output,
        soundfont_path=args.soundfont,
        sample_rate=args.sample_rate,
        bitrate=args.bitrate,
        keep_wav=args.keep_wav
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
