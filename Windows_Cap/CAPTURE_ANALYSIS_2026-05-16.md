# Trofeo LCD — Live Capture Analysis (2026-05-16)
## Capture: trofeo_live_45188.pcap (445.6 MB, 153s, 2042 frames)

Captured using `trofeo_sniffer.py --live --filter 1` on Windows.
TRCC was already running — INIT was NOT captured in this session.

---

## Key Findings

### 1. Byte [9] wraps around (uint8 modulo 256)
- Confirmed: byte[9] transitions through 0xFF → 0x00 → 0x01 etc.
- Example sequence from frames #571–#584:
  - b9=0x01 → declared_size=254,012
  - b9=0x06 → declared_size=256,536
  - b9=0xff → declared_size=252,969
  - b9=0x00 → declared_size=253,878
- This is uint8 arithmetic with wrap-around, NOT a simple offset
- The exact formula mapping declared_size → b9 is still unknown
- b9 correlates with declared_size but the relationship is not linear division

### 2. TRCC sends PARTIAL frames (delta optimization)
- Many frames have actual_size << declared_size
- Examples:
  - Frame #445: 510B actual / 330,905B declared (just 122KB sent!)
  - Frame #515: 61,200B actual / 365,160B declared (15 chunks only)
  - Frame #278: 65,280B actual / 299,396B declared (16 chunks)
  - Frame #1081: 18,352B actual / 196,237B declared (5 chunks!)
- Minimum observed: 4KB actual for a 64KB frame
- Pattern: 65,280B = exactly 16 chunks × 4,080B data per chunk
- Hypothesis: TRCC only sends changed regions of the JPEG
- Our driver sends FULL frames every time — this mismatch may explain
  why the LCD doesn't display our data properly

### 3. Triple buffer byte [12] is always 0
- In this capture: buf=0 for ALL 2042 frames
- Previous captures (dzis.pcapng) showed cycling pattern 2,0,1
- Possible explanations:
  - Triple buffering is optional / mode-dependent
  - The cycling depends on INIT parameters
  - Different TRCC versions / settings use different modes
- Our driver should probably keep buf=0 as default

### 4. Variable FPS (5–58 FPS, avg 13.3)
- TRCC dynamically adjusts frame rate
- Static images: ~6 FPS (idle redraw)
- Animations: up to 58 FPS peak
- Theme transitions cause FPS spikes
- Average interval: 75ms

### 5. Content change detection works
- Sniffer correctly identifies theme switches via JPEG size transitions
- Large jumps visible at:
  - t=13.1s: 293KB → 351KB (theme change)
  - t=39.3s: 329KB → 227KB (animation transition)
  - t=41.8s: 135KB → 353KB (new theme loaded)
  - t=46.8s: 343KB → 243KB (scene change)
  - t=118.2s: 64KB → 139KB (small content)
- Partial frames (64KB bursts) appear during fast animations

### 6. No INIT captured
- Capture started with TRCC already running
- Device descriptor not in capture → "Trofeo LCD not found"
- To capture INIT: start sniffer FIRST, then plug in LCD or restart TRCC

---

## Statistics

| Metric              | Value          |
|---------------------|----------------|
| Duration            | 153.4s         |
| Total packets       | 248,778        |
| Bulk OUT (EP9)      | 111,671        |
| Bulk IN (EP1)       | 2,061          |
| Control transfers   | 0              |
| Total frames        | 2,042          |
| Avg frame size      | 217 KB         |
| Frame size range    | 4–510 KB       |
| Total data          | 432.5 MB       |
| Avg FPS             | 13.3           |
| Avg interval        | 75 ms          |

---

## Byte [9] Distribution (selected values)

| b9   | declared_size range     | count | notes                          |
|------|-------------------------|-------|--------------------------------|
| 0x24 | 144,605 – 271,459      | 55×   | wide range! partial frames?    |
| 0x25 | 144,852 – 272,303      | 71×   | most common low value          |
| 0xaa | 210,858 – 337,967      | 139×  | most frequent overall          |
| 0xab | 211,305 – 338,292      | 63×   |                                |
| 0xb7 | 217,417 – 344,555      | 60×   | static theme region            |
| 0xb8 | 217,829 – 218,139      | 99×   | very tight range = static img  |

Note: b9=0xb8 with tight size range (217,829–218,139) = TRCC showing a static
image and redrawing identical frames. The value stays constant when content
doesn't change.

---

## Implications for Driver Development

1. **Partial frame support** — Our driver should consider NOT sending full
   JPEG data every frame. TRCC clearly optimizes by sending only deltas.
   This may be why our full-frame approach doesn't trigger display update.

2. **Buffer index** — Keep byte[12]=0 as default. The 2,0,1 cycling may
   only apply in specific TRCC modes.

3. **Byte [9] computation** — Still unknown. May need to reverse-engineer
   TRCC binary to find the formula. For now, try:
   - Fixed value matching TRCC output for same JPEG
   - (declared_size / N) mod 256 for various N
   - CRC/checksum of JPEG header bytes

4. **INIT capture needed** — Next session: start sniffer, THEN plug LCD in
   or restart TRCC service to capture the full INIT handshake.

---

## Files

- Capture: `C:\Users\abigo\AppData\Local\Temp\trofeo_live_45188.pcap`
- Sniffer: `trofeo_sniffer.py` (repo: tools/ or root)
- Previous captures with INIT: `dzis.pcapng`
