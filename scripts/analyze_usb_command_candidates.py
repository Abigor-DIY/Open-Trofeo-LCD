#!/usr/bin/env python3
"""Find non-frame USBPcap payloads that may contain device commands."""

from __future__ import annotations

import argparse
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from replay_from_pcap import EP_IN, EP_OUT, iter_epb_packets, iter_pcap_packets


def _iter_packets(path: Path):
    data = path.read_bytes()
    if data.startswith(b"\x0a\x0d\x0d\x0a"):
        yield from iter_epb_packets(data)
        return
    for _, _, _, pkt in iter_pcap_packets(data):
        yield pkt


def _payload(pkt: bytes) -> tuple[int, int, bytes] | None:
    if len(pkt) < 27:
        return None
    hdr_len = struct.unpack_from("<H", pkt, 0)[0]
    if hdr_len < 27 or hdr_len > len(pkt):
        return None
    endpoint = pkt[21]
    transfer = pkt[22]
    data_len = struct.unpack_from("<I", pkt, 23)[0]
    if data_len < 0:
        return None
    end = min(len(pkt), hdr_len + data_len)
    return endpoint, transfer, pkt[hdr_len:end]


def _classify(endpoint: int, transfer: int, payload: bytes) -> str:
    if transfer == 3 and endpoint == EP_OUT and payload[:2] == b"\x01\xff":
        return "bulk-frame-out"
    if transfer == 3 and endpoint == EP_OUT and payload[:2] == b"\x02\xff":
        return "bulk-init-out"
    if transfer == 3 and endpoint == EP_IN and payload[:2] == b"\x03\xff":
        return "bulk-ack-in"
    if not payload:
        return "empty"
    if transfer != 3:
        return "non-bulk"
    if endpoint == EP_OUT:
        return "bulk-other-out"
    if endpoint == EP_IN:
        return "bulk-other-in"
    return "other"


def analyze(path: Path, sample_limit: int = 16) -> None:
    counts: Counter[str] = Counter()
    samples: dict[str, list[tuple[int, int, int, str]]] = defaultdict(list)
    total = 0
    for idx, pkt in enumerate(_iter_packets(path)):
        parsed = _payload(pkt)
        if parsed is None:
            continue
        endpoint, transfer, payload = parsed
        kind = _classify(endpoint, transfer, payload)
        counts[kind] += 1
        total += 1
        interesting = kind in {"non-bulk", "bulk-other-out", "bulk-other-in"} or (
            kind == "bulk-init-out" and len(samples[kind]) < 4
        )
        if interesting and len(samples[kind]) < sample_limit:
            samples[kind].append((idx, endpoint, transfer, payload[:64].hex(" ")))

    print(f"\n{path}")
    print(f"  usbpcap records: {total}")
    for kind, count in counts.most_common():
        print(f"  {kind}: {count}")
    if not samples:
        print("  command candidates: none")
        return
    print("  samples:")
    for kind in sorted(samples):
        for idx, endpoint, transfer, hex_preview in samples[kind]:
            print(f"    {kind}: packet={idx} ep=0x{endpoint:02x} transfer={transfer} data={hex_preview}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pcaps", nargs="+", type=Path)
    parser.add_argument("--sample-limit", type=int, default=16)
    args = parser.parse_args()
    for path in args.pcaps:
        analyze(path, sample_limit=max(1, int(args.sample_limit)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
