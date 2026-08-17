# dwimsy
dwimsy - retrocomputing media preservation, demodulation, restoration, and mastering

grandiose version: (currently 0% implemented)
> **D**oing **W**hat **I** **M**ean, **S**alvaging **Y**esteryear
> A modular toolkit for vintage computer tapes, disks, ROMs, and audio captures.

> [!WARNING]
> **Nothing in this repository is implemented yet.** Every row in the [status matrix](#3-component-implementation-status-matrix) below reads `[ ] TODO`. There is no `dwimsy` CLI, no `core.*` library, and no filters here yet — this repo is currently a specification for how several existing, working tools will be unified. If you need to actually convert or restore media today, use the standalone tools linked below instead.

### For now, see:

- **[`f-fix/pc88_tape_tools`](https://github.com/f-fix/pc88_tape_tools)** — working NEC PC-8001/PC-8801 tools: `pc88_tape_tools.py` (`.t88`↔`.cmt` conversion, splitting/joining, and structural `analyze`), `t882wav.py` (streaming `.t88`→`.wav` FSK synthesis with `tape`/`shaped`/`ideal` modes), and `wav2t88.py` (streaming `.wav`→`.t88` demodulation with AGC and baud auto-detection). All three already have self-test suites and stdin/stdout piping. This is the most complete preview of dwimsy's planned pipeline, and its logic is the intended source for `core.fsk`, `cli.filters.t882wav`/`wav2t88`, and part of `cli.dwimsy analyze`/`inspect` (Milestone 1). It doesn't yet implement dwimsy's flavor taxonomy (Section 5) — there's no trimmed/untrimmed pairing or No-Intro-style naming — and there's no shared `core.audio`/`core.pulse` library, since each script is self-contained.
- **[`f-fix/wav2cas`](https://github.com/f-fix/wav2cas)** — working MSX-family tools: `wav2cas.py` (WAV/FLAC→CAS demodulation with AGC, adaptive thresholding, and per-block confidence scoring), `cas2wav.py` (CAS→WAV synthesis), `flac2wav.py` (pure-Python FLAC decode, stdin/stdout capable), `cmt_filter.py` (component-level simulation of the MSX CMT-IN/CMT-OUT analog circuits), and `cassette_model.py` (physical tape-channel modeling: IEC pre-emphasis, magnetic saturation, Wallace gap loss). These map to `core.fsk`, `core.audio` (`flac2wav`), `dsp.filter` (`cmt_filter`), and `dsp.modeler` (`cassette_model`) in Milestone 1. Note `wav2cas.py`/`cas2wav.py` currently take plain file paths only, not `-` for stdin/stdout, unlike the other three tools here; dwimsy's `cli.filters.*` layer is intended to normalize that.
- **[`f-fix/fat8_d88_tool`](https://github.com/f-fix/fat8_d88_tool)** — a working D88/FAT8 extractor, tested against PC-6001/PC-6001mkII/PC-6001mkIISR, PC-8801, PC-98, and even a Pasopia disk image, including PC-88/PC-98 obfuscated-save deobfuscation and JIS-adjacent character mapping. It's the intended source for `disk.d88`, `disk.fat8`, and part of `core.charsets` (Milestone 2) and `core.fs` filename sanitization. The author's own README is candid that the code "started in ChatGPT" and "is uglier than sin" pending cleanup — a good example of a real candidate for dwimsy's promised readable, documented conversion steps. Tokenized-BASIC detokenization and RBYTE encode/decode are still separate, unintegrated pieces.
- **[`f-fix/nontama_to_bload`](https://github.com/f-fix/nontama_to_bload)** — two working unpackers, `nontama_to_bload.py` (PC-6001mkII NONTAMA loader tapes, verified against ~18 released games) and `mload_to_bload.py` (MSX "M"-loader tapes), plus `mkrom.py` for building bootable cartridges from the results. Maps to `platforms.unpack` (Milestone 2). Each unpacker is a standalone script today; dwimsy's plan is to route their output through the shared Layer 3/4 stream and payload handling rather than writing `.bin` directly.
- **[`f-fix/cas2uef`](https://github.com/f-fix/cas2uef)** — a working, narrowly-scoped `cas2uef.py` that converts "compact" (unpadded, non-8-byte-aligned) MSX CAS from DumpListEditor directly into BBC Micro `.uef`. The author's own README flags that the result isn't archival-quality, since CAS carries no timing data and the tool heuristically inserts pauses at detected file-header boundaries. This is the intended basis for `tape.bbc` (Milestone 3), though in dwimsy it's planned to route through the shared logical-stream layer instead of converting directly, so the heuristic pause-insertion can eventually be replaced with real timing where available.
- **[`f-fix/bin2fds`](https://github.com/f-fix/bin2fds)** — a working but self-described "super ugly" **Python 2** script that converts raw `.bin` to Famicom Disk System `.fds`, including multi-side images. Slated for a straight Python 3 port as `disk.fds` (Milestone 2); until then it's the odd one out in this list, since it isn't even Python 3 yet.

---

## Table of Contents
1. [Overview & Approach](#1-overview--approach)
2. [Existing Project Lineage & Asset Repositories](#2-existing-project-lineage--asset-repositories)
3. [Component Implementation Status Matrix](#3-component-implementation-status-matrix)
4. [The 4-Layer Architecture](#4-the-4-layer-architecture)
5. [Systematic Flavor Taxonomy & No-Intro Naming](#5-systematic-flavor-taxonomy--no-intro-naming)
6. [CLI & Interface Conventions](#6-cli--interface-conventions)
7. [Metadata, Checksums & Archival Packaging](#7-metadata-checksums--archival-packaging)
8. [Forensic DSP & Restoration Engines](#8-forensic-dsp--restoration-engines)
9. [Multi-Phase Implementation Roadmap](#9-multi-phase-implementation-roadmap)
10. [Format & Protocol Technical Reference Guide](#10-format--protocol-technical-reference-guide)

---

## 1. Overview & Approach

`dwimsy` is a modular Python toolkit for decoding, restoring, converting, and analyzing vintage computer media (cassette audio, disk images, ROM cartridges, and stream dumps). 

It is designed to grow incrementally, adding support for new computer platforms, physical media types, modulations, filesystems, and recovery scenarios over time.

### Core Design Principles
* **Composable Unix Filters + Shared Core**: Individual tools (`t882wav`, `wav2t88`, `flac2wav`, `cas2wav`, `bin2fds`, etc.) can be piped together in standard shells or called through a central CLI (`dwimsy`). All tools share a common internal library.
* **Zero Required Dependencies**: Built on Python 3.9+ standard library (`math`, `struct`, `array`, `io`, `sys`, `shutil`, `os`). Acceleration libraries (like NumPy) are strictly optional.
* **Standard [No-Intro Naming Conventions](https://wiki.no-intro.org/index.php?title=Naming_Convention)**: Defaults to clean No-Intro naming for all long names. Tool name/version tags are strictly avoided in filenames (except where mandated by container specifications like TSX tool metadata blocks).
* **Systematic Flavor Defaults**: Each layer has an untagged canonical default flavor. Non-default variants (untrimmed raw streams, 8-byte padded CAS) receive standard No-Intro qualifier tags and exist side-by-side to guarantee hash matches across MAME Softlists, No-Intro, and TOSEC.
* **Self-Contained Archival Bundles**: Input capture files are linked/copied directly inside output bundles alongside full hash suites (Size, CRC32, MD5, SHA1, SHA256) at every abstraction layer.
* **Layered Architecture & Cross-Copy Consensus**: Multi-copy differential recovery and consensus voting operate at signal, flux, container, and logical sector/record layers for both disks and tapes.
* **Fault-Tolerant Automation (`fsck` Model)**: Non-interactive conversions process valid data and isolate corrupted sections with diagnostic logs rather than crashing. An offline interactive recovery mode assists with manual bit/pulse repairs.

---

## 2. Existing Project Lineage & Asset Repositories

`dwimsy` integrates and unifies code, tables, and DSP algorithms from several existing repositories:

* [`f-fix/pc88_tape_tools`](https://github.com/f-fix/pc88_tape_tools): NEC PC-8001 / PC-8801 `.t88` container state machines, `.cmt` stream extraction, and `t882wav` / `wav2t88` streaming FSK audio converters.
* [`f-fix/wav2cas`](https://github.com/f-fix/wav2cas): MSX FSK demodulation (`wav2cas`), audio synthesis (`cas2wav`), streaming FLAC decoding (`flac2wav`), analog signal conditioning (`cmt_filter`), and physical cassette channel simulation (`cassette_modeler`).
* [`f-fix/fat8_d88_tool`](https://github.com/f-fix/fat8_d88_tool): NEC PC-8801 / PC-8001 D88 floppy disk container parsing, FAT8 filesystem extraction/injection, JIS X 0201 / NEC semigraphics character tables, and deterministic OS filename sanitization.
* [`f-fix/nontama_to_bload`](https://github.com/f-fix/nontama_to_bload): PC-6001mkII NONTAMA loader and MSX "M"-loader unpackers, MSX Japanese character mappings, and `mkrom` cartridge builder.
* [`f-fix/cas2uef`](https://github.com/f-fix/cas2uef): MSX `.cas` to BBC Micro Model B `.uef` timing container converter.
* [`f-fix/bin2fds`](https://github.com/f-fix/bin2fds): Raw binary to Nintendo Famicom Disk System / Mitsumi Quick Disk `.fds` image generator.

---

## 3. Component Implementation Status Matrix

| Subsystem / Module | Description | Status | Target Milestone |
| :--- | :--- | :---: | :---: |
| **`core.pulse`** | Edge timing, zero-crossing, time-base correction (TBC), AGC | `[ ] TODO` | Milestone 1 |
| **`core.audio`** | Streaming WAV/FLAC I/O, lossless PCM frame slicing (`flac2wav`) | `[ ] TODO` | Milestone 1 |
| **`core.fsk`** | FSK pulse classifier & UART framing | `[ ] TODO` | Milestone 1 |
| **`dsp.filter`** | Analog filter/wave-shaper & differentiator (`cmt_filter`) | `[ ] TODO` | Milestone 1 |
| **`dsp.modeler`** | Magnetic tape channel simulator (`cassette_modeler`) | `[ ] TODO` | Milestone 1 |
| **`cli.dwimsy`** | Central CLI (`convert`, `restore`, `split`, `join`, `inspect`) | `[ ] TODO` | Milestone 1 |
| **`cli.filters.*`** | Netpbm-style filter entry points (`t882wav`, `wav2t88`, etc.) | `[ ] TODO` | Milestone 1 |
| **`core.charsets`** | Unicode ↔ JIS X 0201 / NEC / MSX / KOI-7 | `[ ] TODO` | Milestone 2 |
| **`core.fs`** | Filename sanitizer & `link_or_copy` hardlinker/copier | `[ ] TODO` | Milestone 2 |
| **`disk.d88`** | D88 sector container reader & writer | `[ ] TODO` | Milestone 2 |
| **`disk.fat8`** | FAT8 filesystem parser & injector | `[ ] TODO` | Milestone 2 |
| **`disk.fds`** | FDS / QuickDisk container engine (`bin2fds` Python 3 port) | `[ ] TODO` | Milestone 2 |
| **`platforms.unpack`** | NONTAMA & MSX M-Loader binary unpackers (`mkrom`) | `[ ] TODO` | Milestone 2 |
| **`metadata.archive`** | Archival bundle exporter & `README.md` generator | `[ ] TODO` | Milestone 2 |
| **`tape.variants`** | Multi-flavor generator (Trimmed/Untrimmed, CAS Pad8, P6/P6T pairs) | `[ ] TODO` | Milestone 2 |
| **`tape.tsx`** | TSX / TZX 1.20 container (MSX FSK & Turbo blocks, CDT/TZX) | `[ ] TODO` | Milestone 3 |
| **`tape.p6t`** | PC-6001 `.p6t` container (footer sync) & `.p6` stream trimmer | `[ ] TODO` | Milestone 3 |
| **`tape.bbc`** | BBC Micro Model B `.uef` reader/writer (`cas2uef`) | `[ ] TODO` | Milestone 3 |
| **`tape.sord_sega`** | Sord M5 & Sega SC-3000 `.cas` adapters | `[ ] TODO` | Milestone 3 |
| **`tape.multiplex`** | Multi-platform compilation splitter (*Tape Login*) | `[ ] TODO` | Milestone 3 |
| **`cue.engine`** | Companion `<basename>.cue` generator & reader | `[ ] TODO` | Milestone 3 |
| **`dsp.classifier`** | FSK carrier vs. broadband speech/music classifier | `[ ] TODO` | Milestone 4 |
| **`platforms.sega_ai`** | Sega AI Computer concurrent stereo engine | `[ ] TODO` | Milestone 4 |
| **`platforms.atari8`** | Atari 8-bit POKEY/Audio concurrent stereo engine | `[ ] TODO` | Milestone 4 |
| **`media.audio_disc`** | Audio-carrier formats (Flexidiscs, CD-DA modulated tracks) | `[ ] TODO` | Milestone 4 |
| **`dsp.harmonize`** | Non-linear time harmonization & reverse print-through recovery | `[ ] TODO` | Milestone 4 |
| **`core.pulse_slicer`**| PWM / Turbo pulse slicer (MSX Turbo, Amstrad Speedlock) | `[ ] TODO` | Milestone 5 |
| **`platforms.studybox`**| Famicom StudyBox dual-track voice + MFM stream decoder | `[ ] TODO` | Milestone 5 |
| **`platforms.adam_ddp`**| Coleco Adam DDP (80 ips high-speed tape) decoder | `[ ] TODO` | Milestone 5 |
| **`platforms.ibm5150`** | IBM PC 5150 cassette demodulator | `[ ] TODO` | Milestone 5 |
| **`platforms.bk0010`** | Soviet Elektronika BK-0010 PDP-11 demodulator | `[ ] TODO` | Milestone 5 |
| **`disk.flux`** | Floppy disk raw flux timing decoders (Applesauce, Greaseweazle)| `[ ] TODO` | Milestone 5 |
| **`packaging`** | `pyproject.toml`, pip packaging, API docs | `[ ] TODO` | Milestone 5 |

---

## 4. The 4-Layer Architecture

```text
┌────────────────────────────────────────────────────────┐
│ Layer 4: Semantic File & Payload Layer        [ ] TODO │
│   • Executable Binaries (BLOAD, Load/Exec RAM images)  │
│   • Detokenized Plaintext Source (N-BASIC, MSX, FOCAL) │
│   • Unicode Charsets (JIS X 0201, NEC, MSX, KOI-7)     │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ Layer 3: Filesystem & Protocol Layer          [ ] TODO │
│   • Sector FS: FAT8, FAT12, CP/M, Coleco DDP           │
│   • Unified Headers: Sharp MZ 128-byte (Tape/QD/Disk)  │
│   • Stream Protocols: PC-88 (D3/24/9C), MSX (1F A6)    │
│   • Custom Loaders: NONTAMA, Speedlock, PWM Turbo      │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ Layer 2: Physical Timing & Sector Containers  [ ] TODO │
│   • Tape Containers: .t88, .tsx, .p6t, .uef, .cdt, .tzx│
│   • Floppy Images  : .d88, .dsk (MSX sectors == CMT)   │
│   • Spiral Disks   : .fds, .qd, .qdf                   │
│   • ROM Cartridges : .rom, .crt (MSX AB, C64 mappers)  │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ Layer 1: Physical Carrier & Raw Signal Layer  [ ] TODO │
│   • Audio Signals  : WAV, FLAC, Flexidiscs, CD Tracks  │
│   • Raw Pulse Flux : Applesauce (.a2r), Greaseweazle   │
│   • Physical DSP   : Time-Base Correction, AGC, Slicer │
└────────────────────────────────────────────────────────┘
```

## 5. Systematic Flavor Taxonomy & No-Intro Naming

To prevent tool-name pollution and keep filenames concise while maintaining 100%
hash correlation against No-Intro, TOSEC, and MAME Software Lists, dwimsy
defines a canonical default flavor (no extra tag) for each layer, alongside
explicitly tagged variant siblings.
```text
Layer            Default Flavor (Untagged)     Tagged Variant Sibling
──────────────────────────────────────────────────────────────────────────
Layer 1 (Audio)  capture.flac                  capture [re-synthesized].wav
Layer 2 (Cont.)  game (Japan).t88 / .tsx       game (Japan) [canonical-timing].tsx
Layer 3 (Stream) game (Japan).p6 / .cas / .cmt game (Japan) [untrimmed].p6 / [pad8].cas
Layer 4 (Payload) game (Japan).bin / .rom      game (Japan) [alt-load].bin
```
### Pairing Rules

1.  PC-6001 (.p6 and .p6t Aligned Pairs):
      - game (Japan).p6 ↔ game (Japan).p6t: Clean stream trimmed
        at verified BASIC 0x0000 EOF / MON :00 terminator for standard emulator
        compatibility.
      - game (Japan) [untrimmed].p6 ↔ game (Japan)
        [untrimmed].p6t: Raw stream retaining physical trailing flush padding.
2.  MSX (.cas Unaligned vs. 8-Byte Aligned Pairs):
      - game (Japan).cas: Clean unpadded byte stream (No-Intro / OpenMSX
        standard).
      - game (Japan) [pad8].cas: Chunks padded to 8-byte boundaries (legacy
        TOSEC / fMSX match).
      - game (Japan).tsx: Physical timing container with KCS Block 0x4B and
        Turbo Block 0x11.
3.  PC-88 / PC-80 (.t88 and .cmt Pairs):
      - game (Japan).cmt ↔ game (Japan).t88: Canonical
        DumpListEditor / c2t mastering timing.
      - game (Japan) [untrimmed].cmt ↔ game (Japan)
        [untrimmed].t88: Raw physical stream retaining trailing carrier
        overshoot.

## 6. CLI & Interface Conventions

### Main CLI Verbs `[ ] TODO`
```bash
# Convert between any pair of formats (inferred from extensions)
dwimsy convert input.flac output.t88
dwimsy convert game.d88 game.wav --target-tape-type t88

# Export complete multi-flavor archival bundle (masters, tracks, trimmed pairs, manifests)
dwimsy archive capture.flac -o ./Archive_Bundle/

# Restore audio or clean up container timing (w2w / t2t)
dwimsy restore degraded.flac clean.wav --canonical

# Slice into tracks (lossless PCM audio or container splits)
dwimsy split tape.flac -o ./extracted_tracks/

# Join tracks or folders into a single image (reads cue if present)
dwimsy join ./extracted_tracks/ -o master.wav

# Inspect structure, metadata, baud rates, and timing
dwimsy inspect input.t88
```
### Positional Per-Input Options (SoX / FFmpeg Model) `[ ] TODO`

Options placed immediately before an input file act as scoped overrides:
```bash
dwimsy join \
    --channel left  deck_a.flac \
    --channel right deck_b.flac \
    --baud 600      loader.cmt \
    -o master.wav --wave tape --volume 0.85
```
### File Linking & Paired Naming `[ ] TODO`

  - dwimsy emits both a compact CLI name (crazy_a.p6) and an extended No-Intro
    long name (Crazy Newton (Japan) (PC-6001 32K Mode 2 Pages 2)
    [CLOAD-RUN] 32k.p6) in a flat directory.
  - Links are created with os.link, falling back automatically to shutil.copy2
    on FAT32/exFAT, cross-device mounts, or unsupported environments.
  - Input capture files are linked/copied directly inside output bundles under
    standard names.

## 7. Metadata, Checksums & Archival Packaging

### Multi-Level Hash Registry `[ ] TODO`

Every file entry across manifests, README.md, and inspection reports provides
the complete hash suite (Size in bytes, CRC32, MD5, SHA1, SHA256) to enable
cross-referencing against MAME Software Lists, TOSEC, and No-Intro:
```text
hashes:
  # Layer 1: Raw Analog Capture (Matches MAME Softlist / CHD hashing)
  layer1_analog_audio:
    filename: "crazy_orig.flac"
    size_bytes: 24741464
    crc32: "89ABCDEF"
    md5: "c4ca4238a0b923820dcc509a6f75849b"
    sha1: "356a192b7913b04c54574d18c28d46e6395428ab"
    sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

  # Layer 2: Physical Timing Container
  layer2_container:
    filename: "Crazy Newton (Japan).p6t"
    size_bytes: 27200
    crc32: "12345678"
    md5: "5d41402abc4b2a76b9719d911017c592"
    sha1: "da39a3ee5e6b4b0d3255bfef95601890afd80709"
    sha256: "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

  # Layer 3: Logical Stream (Trimmed & Untrimmed Flavors)
  layer3_logical_stream:
    trimmed_clean:
      filename: "Crazy Newton (Japan).p6"
      size_bytes: 26830
      crc32: "EEFF0011"
      md5: "098f6bcd4621d373cade4e832627b4f6"
      sha1: "2ef7bde608ce5404e97d5f042f95f89f1c232871"
      sha256: "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"
      no_intro_match: "Crazy Newton (Japan) (PC-6001)"
    untrimmed_raw:
      filename: "Crazy Newton (Japan) [untrimmed].p6"
      size_bytes: 26856
      crc32: "AABBCCDD"
      md5: "ad0234829205b9033196ba818f7a872b"
      sha1: "7c211433f02071597741e6ff5a8ea34789abbf43"
      sha256: "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a"
```
### Trailing Byte Trimming & Motor Coasting Ledger `[ ] TODO`

When BIOS routines (PC-6001, MSX CSAVE, PC-88) write padding bytes that CLOAD
ignores during motor coast:

  - RLE Pattern Representation: Documented in manifest.yaml as pattern: "00*26"
    or pattern: "FF*18".
  - Byte Offset & Reason: Stored in manifest metadata to allow reversible
    reconstruction.

## 8. Forensic DSP & Restoration Engines

  - Time-Base Correction (TBC): `[ ] TODO` Tracks carrier frequency to normalize
    playback speed drift into standard 4,800 ticks/sec container time.
  - Zero-Gap Demodulation: `[ ] TODO` Snaps post-DATA carrier start ticks to the
    exact end tick of the preceding data block
    (`T_end = T_start + N_bytes × ticks_per_byte`).
  - Multi-Copy & Multi-Revolution Consensus (Disks & Tapes): `[ ] TODO` Merges
    multiple physical copies or multi-revolution dumps (floppy SCP/A2R/D88 or
    tape takes) using CRC-verified block/sector consensus.
  - Non-Linear Time Harmonization & Print-Through Recovery: `[ ] TODO` Dynamic
    Time Warping on pulse transitions (Δt) to align time-reversed ghost
    signals from opposite tape sides and repair dropouts.
  - Context-Aware Semantic Recovery (ZX81): `[ ] TODO` Uses BASIC line link
    pointers, token tables, and disassembly branches to solve ambiguous pulse
    dropouts.
  - Dual-Track Concurrent Stereo: `[ ] TODO` Independent channel classification
    and crosstalk bleed rejection (Sega AI Computer, Atari 8-bit, Famicom
    StudyBox).
  - Virtual Sanyo PHC-DRIII Shaper & 2x Doubler: `[ ] TODO` Software
    differentiator (d/dt), phase equalizer, and adaptive Schmitt slicer
    (cmt_filter), with octave-doubled fast audio synthesis
    (2400/4800 Hz).

## 9. Multi-Phase Implementation Roadmap

### Phase 1: Core Foundation & Unix Filters `[ ] TODO`

Tasks:

1.  [ ] TODO Implement dwimsy.core.pulse (zero-crossing timer, TBC, AGC,
    DC-blocker).
2.  [ ] TODO Implement dwimsy.core.audio (streaming WAV + FLAC reader/writer
    with lossless PCM slicing).
3.  [ ] TODO Implement dwimsy.dsp (cmt_filter wave shaper and cassette_modeler).
4.  [ ] TODO Implement Netpbm filters: t882wav, wav2t88, cas2wav, wav2cas,
    flac2wav, t88clean (t2t), wavclean (w2w).
5.  [ ] TODO Implement dwimsy CLI with convert, restore, split, join, inspect.
    Verification: `[ ] TODO` Bit-exact roundtrip on input01.t88 and casan.flac.

### Phase 2: Semantics, Disk Subsystems, QuickDisk / FDS & Flavor Matrix `[ ] TODO`

Tasks:

1.  [ ] TODO Integrate dwimsy.core.charsets (JIS X 0201, NEC semigraphics, MSX
    Katakana, ASCII).
2.  [ ] TODO Integrate dwimsy.disk.d88 and dwimsy.disk.fat8 (d882fat8, fat82d88,
    d882t88).
3.  [ ] TODO Port bin2fds.py to Python 3 in dwimsy.disk.fds (bin2fds filter).
4.  [ ] TODO Implement NONTAMA and MSX M-loader unpackers to standard BLOAD
    binaries (mkrom).
5.  [ ] TODO Implement dwimsy.tape.variants: Side-by-side flavor generator
    (Trimmed/Untrimmed, MSX Pad8, .p6/.p6t aligned pairs) with complete
    hash/size registry.
6.  [ ] TODO Implement dwimsy archive bundle generator with manifest.yaml and
    README.md.

### Phase 3: Extended Tape Containers (TSX, P6T, UEF, Sord, Sega) `[ ] TODO`

Tasks:

1.  [ ] TODO Implement dwimsy.tape.tsx (TZX 1.20 + Block #4B KCS FSK)
    → enables Amstrad CPC .cdt and ZX Spectrum .tzx.
2.  [ ] TODO Implement dwimsy.tape.p6t and dwimsy.tape.p6 with BIOS CSAVE
    padding trimmer.
3.  [ ] TODO Integrate dwimsy.tape.bbc (BBC Micro Model B .uef via cas2uef).
4.  [ ] TODO Implement Sord M5 and Sega SC-3000 .cas adapters.
5.  [ ] TODO Add auto-sniffing for .cas flavor disambiguation and multi-platform
    compilation splitting (Tape Login multiplexer).

### Phase 4: Mixed-Mode Media, Dual-Track Stereo & Audio Discs `[ ] TODO`

Tasks:

1.  [ ] TODO Build narrow-band FSK vs. broadband voice/music spectral
    classifier.
2.  [ ] TODO Implement dual-track concurrent stereo profiles (Sega AI Computer,
    Atari 8-bit, Famicom StudyBox).
3.  [ ] TODO Add non-magnetic modulated audio disc support (PiO magazine
    flexidiscs, Starpath Supercharger / MSX CD-DA audio tracks).
4.  [ ] TODO Implement companion `<basename>.cue` generator and cue-driven join.

### Phase 5: Advanced Modulations, Vintage 16-Bit Systems & Packaging `[ ] TODO`

Tasks:

1.  [ ] TODO Implement dwimsy.core.pulse_slicer for PWM Turbo loaders (European
    MSX, Amstrad Speedlock).
2.  [ ] TODO Implement Famicom StudyBox MFM stream decoder.
3.  [ ] TODO Implement Coleco Adam DDP (80 ips high-speed tape) and Sinclair ZX
    Microdrive decoders.
4.  [ ] TODO Implement vintage 16-bit demodulators: IBM PC 5150 cassette
    (.cas/.bin) and Elektronika BK-0010 PDP-11 demodulator with KOI-7 Cyrillic
    decoding.
5.  [ ] TODO Implement raw floppy flux decoders and multi-revolution consensus
    (Applesauce .a2r/.woz, Greaseweazle .scp/.raw).
6.  [ ] TODO Finalize pyproject.toml, docstrings, and test suite for pip
    packaging.

## 10. Format & Protocol Technical Reference Guide

### Physical Modulation Reference Table

| Platform / System          | Modulation Type  | Mark / 1 Frequency                           | Space / 0 Frequency                           | Baud / Data Rate                  | Bit Framing                           |
| :------------------------- | :--------------- | :------------------------------------------- | :-------------------------------------------- | :-------------------------------- | :------------------------------------ |
| **NEC PC-8001 / PC-8801**  | FSK              | 2400 Hz (2 cyc)                              | 1200 Hz (1 cyc)                               | 1200 / 600 baud                   | 1 Start (0), 8 Data (LSB), 2 Stop (1) |
| **NEC PC-6001 / PC-6601**  | FSK              | 2400 Hz (2 cyc)                              | 1200 Hz (1 cyc)                               | 1200 / 600 baud                   | 1 Start (0), 8 Data (LSB), 2 Stop (1) |
| **MSX / MSX2 (Standard)**  | FSK              | 2400 Hz (2 cyc)                              | 1200 Hz (1 cyc)                               | 1200 / 2400 baud                  | 1 Start (0), 8 Data (LSB), 2 Stop (1) |
| **MSX (Sanyo 2x Fast)**    | Octave FSK       | 4800 Hz (2 cyc)                              | 2400 Hz (1 cyc)                               | 2400 baud                         | 1 Start (0), 8 Data (LSB), 2 Stop (1) |
| **MSX (European Turbo)**   | PWM / Pulse      | Short edge pair                              | Long edge pair                                | 2000–4000+ baud                   | Raw bitstream, zero stop bits         |
| **BBC Micro Model B**      | FSK (KCS)        | 2400 Hz (2 cyc)                              | 1200 Hz (1 cyc)                               | 1200 / 300 baud                   | 1 Start (0), 8 Data (LSB), 1 Stop (1) |
| **Amstrad CPC (Standard)** | 2-Tone PWM       | ≈667 Hz (750 μs)                             | ≈1333 Hz (375 μs)                             | ≈1000 / 2000 baud                 | 2KB data blocks + 16-bit CRC          |
| **Sord M5 / Sega SC-3000** | FSK              | 2400 Hz (2 cyc)                              | 1200 Hz (1 cyc)                               | 1200 baud                         | 1 Start (0), 8 Data (LSB), 2 Stop (1) |
| **Sega AI Computer**       | Dual FSK/Audio   | Right: 2400/1200 FSK                         | Left: Speech audio                            | 1200 baud                         | Synchronized concurrent stereo        |
| **Atari 8-bit (POKEY)**    | Dual FSK/Audio   | Right: ≈4 kHz                                | Left: Voice audio                             | 600 baud                          | 1 Start, 8 Data, 1 Stop, 128B blocks  |
| **IBM PC 5150**            | Tone Pulse       | 2000 Hz (500 μs)                             | 1000 Hz (1000 μs)                             | ≈1500 baud                        | 256B blocks + CRC16                   |
| **Elektronika BK-0010**    | Pulse Interval   | 2 pulses (500 μs)                            | 1 pulse (1000 μs)                             | ≈1200 baud                        | 16B header + PDP-11 memory image      |
| **Famicom StudyBox**       | Dual MFM/Audio   | Right: MFM Stream                            | Left: Speech audio                            | High-density MFM                  | 1T / 1.5T / 2T cell transitions       |
| **Coleco Adam DDP**        | High-Speed Pulse | 80 ips continuous                            | Bi-directional                                | High-speed DDP                    | 512B blocks + CRC                     |
| **Starpath Supercharger**  | High-Speed FSK   | ≈8.4 kHz carrier                             | Phase transitions                             | 8400 baud                         | 2KB multi-load banks                  |

### Container Signatures Reference
```text
Format      Extension   Header Signature / Magic Bytes
─────────────────────────────────────────────────────────────────────────────
PC-88 T88   .t88        50 43 2D 38 38 30 31 20 54 61 70 65 20 49 6D 61 67 65 28 54 38 38 29 00
MSX TSX     .tsx / .tzx 5A 58 54 61 70 65 21 1A ("ZXTape!\x1a") + ver 0x01 0x20/0x21
MSX CAS     .cas        1F A6 DE BA CC 13 7D 74 (8-byte BIOS sync header)
BBC UEF     .uef        1F 8B (Gzip header) -> 55 45 46 20 46 69 6C 65 21 ("UEF File!")
Amstrad CDT .cdt        5A 58 54 61 70 65 21 1A ("ZXTape!\x1a")
PC-6001 P6T .p6t        PC6001V format with trailing timing/mode descriptors
Sega CAS    .cas        53 45 47 41 20 43 41 53 53 45 54 54 45 ("SEGA CASSETTE")
Sord M5 CAS .cas        55 55 55 55 55 55 55 55 (Sync run) + 'HEADER'
NEC D88     .d88 / .d77 17-byte disk title + 0x00 + 0x00 0x00 0x00 0x00
FDS Image   .fds        46 44 53 1A ("FDS\x1a") or Block 1 '\x01*NINTENDO-HVC*'
Applesauce  .woz / .a2r 57 4F 5A 31 / 57 4F 5A 32 | 41 32 52 32 ("A2R2")
Greaseweazle.scp        53 43 50 ("SCP")
C64 CRT     .crt        43 36 34 20 43 41 52 54 52 49 44 47 45 20 20 20 ("C64 CARTRIDGE   ")
```

---

# Note on the code and the tools used to write it

Parts of this code were written (including some initial ones that began in other, separate projects) with assistance from LLM-integrated coding tools. If you don't like it, feel free to use other software or rewrite parts you dislike. PRs are welcome!

## How did I end up using those? Don't I dislike slop?

Yes, I hate slop. This project began because I wanted tape image conversion tools where the conversion steps were all clearly documented and readable code, but which also performed well enough in terms of accuracy to actually be the tool I use. I started out writing the tools myself, but my manual attempts hadn't yielded comparable accuracy to existing closed-source tools for some steps, so I started using the tools to help find the bugs and suggest improvements, and IMO the result is now good enough to actually be useful in some scenarios. In terms of slop, the tool-generated code doesn't closely resemble any existing solutions I have found. Rather it's a fairly passable translation of my requests into Python.
