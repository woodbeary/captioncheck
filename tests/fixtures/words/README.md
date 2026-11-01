# Recorded word timings

Recorded 2026-11-01 with `scripts/record_fixtures.py` from the clips that
`scripts/fetch_clips.py` fetches: faster-whisper 1.2.1, CTranslate2 4.8.4,
`small.en` at repository revision `d1d751a5f8271d482d14ca55d9e2deeebbae577f`,
int8 on CPU, beam 5, temperature 0. Two runs on the same machine produced
identical files. Each file names the SHA-256 of the analysis audio it was made
from, and captioncheck refuses to use it with any other audio.

They are a machine transcript of dialogue from *Tears of Steel*,
(CC) Blender Foundation | mango.blender.org, licensed CC BY 3.0. The
transcript is the model's hearing, mistakes included ("Tom" for "Thom",
"Me and Cecilia!" for "Vivacissimo!"); that is the point of keeping it.
