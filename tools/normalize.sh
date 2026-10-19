#!/usr/bin/env bash
#
# normalize.sh - turn a folder of audio clips into a matched set of short,
# office-friendly notification sounds.
#
# For every clip it:
#   1. strips leading silence
#   2. caps the length (default 1.5 s) with a short fade-out, plus a 5 ms fade-in
#   3. measures loudness (EBU R128 / LUFS) and applies gain to hit one target
#   4. limits peaks to about -1 dBFS so nothing clips
#   5. writes a 44.1 kHz 16-bit WAV (plays everywhere: afplay, paplay, aplay, ffplay)
#
# Needs only ffmpeg + ffprobe. Works with the bash 3.2 that ships on macOS.
#
# Usage:
#   ./normalize.sh [-t TARGET_LUFS] [-m MAX_SECONDS] [-o OFFSETS_FILE] INPUT_DIR OUTPUT_DIR
#
#   -t  loudness target in LUFS (default -20; -24 is quieter, -16 is louder)
#   -m  maximum clip length in seconds (default 1.5)
#   -o  per-clip offsets file (default: INPUT_DIR/offsets.txt if it exists)
#
# Offsets file format - one clip per line, name without extension, then dB:
#   done      -3     # fires constantly: sit it a bit quieter
#   error     +1
#
# Example:
#   ./normalize.sh ~/Downloads/raw-clips ~/.claude/cc-droid/sounds

set -euo pipefail

TARGET=-20
MAX_LEN=1.5
OFFSETS=""

usage() { sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while getopts ":t:m:o:h" opt; do
  case "$opt" in
    t) TARGET="$OPTARG" ;;
    m) MAX_LEN="$OPTARG" ;;
    o) OFFSETS="$OPTARG" ;;
    h) usage 0 ;;
    *) usage 1 ;;
  esac
done
shift $((OPTIND - 1))
[ $# -eq 2 ] || usage 1

IN_DIR="$1"
OUT_DIR="$2"

for bin in ffmpeg ffprobe; do
  command -v "$bin" >/dev/null 2>&1 || {
    echo "error: $bin not found. Install it (macOS: brew install ffmpeg | Debian/Ubuntu: sudo apt install ffmpeg)" >&2
    exit 1
  }
done
[ -d "$IN_DIR" ] || { echo "error: input folder not found: $IN_DIR" >&2; exit 1; }
mkdir -p "$OUT_DIR"

if [ -z "$OFFSETS" ] && [ -f "$IN_DIR/offsets.txt" ]; then
  OFFSETS="$IN_DIR/offsets.txt"
fi

# Older ffmpeg builds (< 4.4) lack alimiter's `level` switch; newer ones default it
# to on, which would re-boost the output. Detect and disable it when present.
LIMITER="alimiter=limit=0.89:attack=5:release=50"
if ffmpeg -hide_banner -h filter=alimiter 2>/dev/null | grep -q '^ *level '; then
  LIMITER="$LIMITER:level=false"
fi

offset_for() {
  # Prints the dB offset for clip name $1 (0 when none is listed).
  [ -n "$OFFSETS" ] && [ -f "$OFFSETS" ] || { echo 0; return; }
  awk -v n="$1" '{ sub(/#.*/, "") } NF >= 2 && $1 == n { v = $2 } END { print (v == "" ? 0 : v + 0) }' "$OFFSETS"
}

measure() {
  # Prints "<integrated LUFS> <true peak dBFS>" for audio produced by filter chain $2.
  # Short clips are padded with digital silence, which R128 gating ignores, so the
  # 400 ms measurement blocks have something to work with.
  ffmpeg -hide_banner -nostats -i "$1" -af "$2,apad=pad_dur=3,ebur128=peak=true:framelog=quiet" -f null - 2>&1 |
    awk '/^ *I:/ { i = $2 } /^ *Peak:/ { p = $2 } END { print i, p }'
}

PRE="silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.01"

TMPD=$(mktemp -d 2>/dev/null || mktemp -d -t normalize)
trap 'rm -rf "$TMPD"' EXIT

printf "%-24s %8s %8s %7s %9s %8s\n" "clip" "len(s)" "in LUFS" "gain" "out LUFS" "peak"
count=0

for f in "$IN_DIR"/*; do
  [ -f "$f" ] || continue
  case "$(basename "$f")" in offsets.txt|*.txt|*.md|.*) continue ;; esac

  # Skip anything ffprobe can't read as audio.
  dur=$(ffprobe -v error -select_streams a:0 -show_entries format=duration -of csv=p=0 "$f" 2>/dev/null || true)
  [ -n "$dur" ] && [ "$dur" != "N/A" ] || { echo "skip (not audio): $(basename "$f")" >&2; continue; }

  name=$(basename "$f"); name="${name%.*}"; name="${name%.raw}"
  out="$OUT_DIR/$name.wav"

  channels=$(ffprobe -v error -select_streams a:0 -show_entries stream=channels -of csv=p=0 "$f")
  ac_opt=""; [ "${channels:-1}" -gt 2 ] && ac_opt="-ac 2"

  # Strip leading silence into a temp file first, so the length cap and fade-out
  # are computed on what will actually play.
  pre="$TMPD/$name.pre.wav"
  # shellcheck disable=SC2086
  ffmpeg -hide_banner -loglevel error -y -i "$f" -af "$PRE" $ac_opt -c:a pcm_s16le "$pre"
  trimmed=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$pre" 2>/dev/null || true)
  if ! awk -v d="$trimmed" 'BEGIN { exit !(d + 0 > 0.02) }'; then
    # The whole clip sits under the silence threshold (a very quiet recording):
    # keep it untrimmed and let the gain stage bring it up.
    # shellcheck disable=SC2086
    ffmpeg -hide_banner -loglevel error -y -i "$f" $ac_opt -c:a pcm_s16le "$pre"
    trimmed=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$pre")
  fi
  len=$(awk -v d="$trimmed" -v m="$MAX_LEN" 'BEGIN { printf "%.3f", (d < m ? d : m) }')
  fade_out=$(awk -v l="$len" 'BEGIN { f = (l > 1 ? 0.12 : l * 0.12); printf "%.3f", (f < 0.01 ? 0.01 : f) }')
  fade_start=$(awk -v l="$len" -v f="$fade_out" 'BEGIN { printf "%.3f", l - f }')

  SHAPE="atrim=end=$len,afade=t=in:d=0.005,afade=t=out:st=$fade_start:d=$fade_out"

  read -r in_lufs _ <<<"$(measure "$pre" "$SHAPE")"
  if [ -z "$in_lufs" ] || awk -v v="$in_lufs" 'BEGIN { exit !(v == "-inf" || v + 0 <= -69) }'; then
    echo "skip (silent): $(basename "$f")" >&2
    continue
  fi

  off=$(offset_for "$name")
  gain=$(awk -v t="$TARGET" -v o="$off" -v i="$in_lufs" 'BEGIN { printf "%.2f", t + o - i }')

  ffmpeg -hide_banner -loglevel error -y -i "$pre" \
    -af "$SHAPE,volume=${gain}dB,$LIMITER,aresample=44100" \
    -c:a pcm_s16le "$out"

  read -r out_lufs out_peak <<<"$(measure "$out" "anull")"
  printf "%-24s %8.2f %8s %+6.1f %9s %8s\n" "$name" "$len" "$in_lufs" "$gain" "$out_lufs" "$out_peak"
  count=$((count + 1))
done

echo "done: $count clip(s) -> $OUT_DIR (target ${TARGET} LUFS${OFFSETS:+, offsets from $OFFSETS})"
