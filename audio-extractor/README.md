# Audio Extractor

A single-file, dependency-free web app that pulls the audio track out of a
video and saves it as a WAV. Open `index.html` in any modern browser — no
server, no build step, no upload; the file is processed entirely on the
user's machine.

## How it works

1. The chosen file is read into memory and handed to the Web Audio API's
   `decodeAudioData`, which demuxes and decodes the audio track of any
   container/codec the browser itself can play (MP4/H.264+AAC, WebM, MOV,
   OGG, …).
2. The decoded PCM is re-encoded as a 16-bit little-endian WAV (RIFF header
   written by hand — ~30 lines) at the source's own sample rate and channel
   count, previewed as a waveform, and offered for download.
3. If `decodeAudioData` rejects the container, the app falls back to playing
   the file through a silent `MediaElementSource → MediaStreamDestination`
   graph and recording it with `MediaRecorder` — real-time, saved as
   WebM/Opus instead of WAV.

## Verified

Tested end-to-end in headless Chromium (Playwright): a synthesized 2 s WebM
carrying a 440 Hz tone at gain 0.5 extracts to a valid stereo 44.1 kHz WAV —
measured 1.98 s, peak 0.508, dominant frequency 442.9 Hz by zero-crossing
count.
