# Trofeo LCD protocol notes for Linux work

Source: live USBPcap analysis from `trofeo_sniffer.py --live --filter 1`.

## Device identity

- Product seen by Windows: `USBDISPLAY`
- Identified by sniffer as: `Thermalright Trofeo LCD`
- USB VID/PID: `0416:5408`
- Windows driver class: `WinUSB`
- Capture device address: `2`
- Relevant endpoints observed:
  - Bulk OUT: endpoint `0x09`
  - Bulk IN: endpoint `0x81` / logical EP1
  - Control transfers: present but rare, only `20` in the 201.5 s capture

## Session shape

The Windows application sends an init packet first, then streams frame data.

Observed init:

```text
OUT INIT: 2048 bytes
Header:   02 ff 00 00 00 00 00 00 01 00 00 00 00 00 00 00
```

Observed init ACK:

```text
IN ACK status: OK
Display reported: 1920 x 599
Firmware-ish value: 1c ac 2c 86
Quality value: 50
Non-zero ACK bytes:
  [0]=03 [1]=ff [8]=01
  [16]=1c [17]=ac [18]=2c [19]=86
  [20]=02 [22]=04
  [24]=80 [25]=07
  [28]=57 [29]=02
  [32]=32
  [40]=02
  [44]=89
```

Likely ACK field guesses:

- Bytes `24..25` are little-endian `0x0780` = `1920`.
- Bytes `28..29` are little-endian `0x0257` = `599`.
- Byte `32` is decimal `50`, matching reported quality.
- Bytes `16..19` are probably firmware/build or device serial-derived protocol value.

## Frame stream

The display reports `1920 x 599`, but frames in the capture are consistently
reported as `1920 x 462`. Treat `1920 x 462` as the active image area until a
separate capture proves otherwise.

Capture summary:

- Duration: `201.5 s`
- Total packets: `355321`
- Bulk OUT packets on EP9: `166984`
- Bulk IN packets on EP1: `2439`
- Frames detected: `2443`
- Total frame data: `647.7 MB`
- Average frame size: `271 KB`
- Frame size range: `4 KB` to `450 KB`
- Average FPS: `13.7`
- Average interval: `73 ms`

Most frame rows look like:

```text
FRAME #n 1920x462 OUT_BYTES/JPEG_BYTES CHUNKS buf=0 b9=0x?? time_ms fps
```

Important observation: chunk counts line up with a maximum payload chunk of
`4080` bytes.

Examples:

- `85ch` -> `346800 B` = `85 * 4080`
- `83ch` -> `338640 B` = `83 * 4080`
- `58ch` -> `236640 B` = `58 * 4080`
- `15ch` -> `61200 B` = `15 * 4080`
- `4ch` -> `16320 B` = `4 * 4080`

Some frames have a partial final chunk, for example:

- `91ch` with `369232 B` = `90 * 4080 + 2032`
- `92ch` with `375360 B` = `92 * 4080`

Working inference: frame payload is sent over EP9 as a sequence of chunks up to
`4080` bytes each. The last chunk may be shorter.

## JPEG and mystery byte b9

The analyzer calls the image payload JPEG. The `b9` byte correlates very strongly
with JPEG size, especially in dense ranges:

- `0x83..0xa9` roughly covers `318 KB..337 KB`
- `0xcb..0xd1` roughly covers `227 KB..230 KB`
- `0xdf..0xe0` roughly covers `364 KB..365 KB`

This suggests `b9` is probably not a frame counter. More likely it is one of:

- a length/check byte derived from JPEG size,
- a chunk/table selector derived from compressed length,
- a protocol-side quality/size bucket,
- or part of a header/checksum field that includes image size.

Useful correlation to test:

```text
b9 ~= f(jpeg_size)
```

Do not hardcode `b9` as constant. The Linux sender should compute or preserve it
from a known-good frame header once the exact frame header bytes are decoded.

## Buffer field

The analyzer reports:

```text
TRIPLE BUFFER pattern (first 12): [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
```

Frame lines often show:

```text
buf=0(!=1)
buf=0(!=2)
```

Working inference: either the Windows app always sends buffer id `0`, or the
current analyzer expected triple-buffer rotation but the observed protocol does
not use it in this mode. Linux should start with `buf=0` only.

## Timing

The device accepts a wide range of timing:

- Normal animation often lands around `16 FPS`.
- Many full frames take `30..40 ms` to transmit.
- Small frames can take `1..7 ms`.
- Long gaps are tolerated between content changes.

Initial Linux target should be conservative:

- send init,
- wait for ACK,
- send one static frame,
- wait `40..70 ms` between frames during animation.

## Linux implementation plan

Use `libusb` or `pyusb` first. Since Windows uses WinUSB and the endpoints are
bulk endpoints, Linux does not need to emulate HID.

Minimal send sequence:

1. Open `0416:5408`.
2. Set configuration `1`.
3. Claim interface `0` unless descriptors show otherwise.
4. Send the 2048-byte init packet to EP9.
5. Read ACK from EP1 and validate:
   - ACK starts with `03 ff`
   - width is `1920`
   - height is `599`
   - quality byte is `50`
6. Encode/prepare one `1920 x 462` JPEG frame.
7. Build the real frame header once decoded.
8. Split frame payload into max `4080` byte chunks.
9. Write chunks to EP9.
10. Optionally read EP1 after each complete frame or when a timeout-safe ACK is
    expected.

## Open questions

These need a short, focused capture with raw frame headers saved:

- Exact frame header structure.
- Where width/height are stored in frame packets.
- Where JPEG byte length is stored.
- How byte `b9` is computed.
- Whether each chunk has its own header or only the first chunk is framed.
- Whether EP1 sends one ACK per frame, per chunk group, or only during init.
- Whether the active `462 px` height is fixed or selected by mode/theme.

## Next capture request

For protocol decoding, capture a very small session:

1. Start app.
2. Let init complete.
3. Send one static black image.
4. Send one static white image.
5. Stop.

For each frame, save the first `64` bytes of the first chunk and the last `64`
bytes of the final chunk. That should be enough to decode headers without
handling a 600 MB capture.

