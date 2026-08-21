# dwimsy
dwimsy - retrocomputing media preservation, demodulation, restoration, and mastering

grandiose version: (currently 0% implemented)
> **D**oing **W**hat **I** **M**ean, **S**alvaging **Y**esteryear — Format-Aware Media Transducer & Preservation Gateway
> 
> A modular toolkit for vintage computer tapes, disks, ROMs, and audio captures.

> [!IMPORTANT]
> **DEVELOPMENT STATUS: SPECIFICATION & ADAPTER PHASE.**
> This repository is a specification for a unified media transducer. Implementation is being bootstrapped by **adapting and wrapping** the existing standalone tools listed below into the `dwimsy` orchestration layer.

### For now, see:

- **[`f-fix/pc88_tape_tools`](https://github.com/f-fix/pc88_tape_tools)** — working NEC PC-8001/PC-8801 tools: `pc88_tape_tools.py` (`.t88`↔`.cmt` conversion, splitting/joining, and structural `analyze`), `t882wav.py` (streaming `.t88`→`.wav` FSK synthesis with `tape`/`shaped`/`ideal` modes), and `wav2t88.py` (streaming `.wav`→`.t88` demodulation with AGC and baud auto-detection). All three already have self-test suites and stdin/stdout piping. This is the most complete preview of dwimsy's planned pipeline, and its logic is the intended source for `core.fsk`, `cli.filters.t882wav`/`wav2t88`, and part of `cli.dwimsy analyze`/`inspect` (Milestone 1). It doesn't yet implement dwimsy's flavor taxonomy (Section 6) — there's no trimmed/untrimmed pairing or No-Intro-style naming — and there's no shared `core.audio`/`core.pulse` library, since each script is self-contained.
  * *Refactoring Status:* Currently being integrated via adapters to prove the Bridge/LCD UI logic.
- **[`f-fix/wav2cas`](https://github.com/f-fix/wav2cas)** — working MSX-family tools: `wav2cas.py` (WAV/FLAC→CAS demodulation with AGC, adaptive thresholding, and per-block confidence scoring), `cas2wav.py` (CAS→WAV synthesis), `flac2wav.py` (pure-Python FLAC decode, stdin/stdout capable), `cmt_filter.py` (component-level simulation of the MSX CMT-IN/CMT-OUT analog circuits), and `cassette_model.py` (physical tape-channel modeling: IEC pre-emphasis, magnetic saturation, Wallace gap loss). These map to `core.fsk`, `core.audio` (`flac2wav`), `dsp.filter`, and `dsp.modeler` (`cassette_model`) in Milestone 1. Note `wav2cas.py`/`cas2wav.py` currently take plain file paths only, not `-` for stdin/stdout, unlike the other three tools here; dwimsy's `cli.filters.*` layer is intended to normalize that so all tape tools operate as continuous Unix streaming filters.
  * *Refactoring Status:* Target for `dwimsy.dsp` and MSX physical layer generalization.
- **[`f-fix/fat8_d88_tool`](https://github.com/f-fix/fat8_d88_tool)** — a working D88/FAT8 extractor, tested against PC-6001/PC-6001mkII/PC-6001mkIISR, PC-8801, PC-98, and even a Pasopia disk image, including PC-88/PC-98 obfuscated-save deobfuscation (N88-BASIC bit rotation and PC-88 143-byte combined XOR key recovery) and JIS-adjacent / PC-6001 semigraphics character mapping. It includes dedicated streaming line-by-line character set conversion modes (`--pc98-8bit-to-utf8`, `--pc6001-8bit-to-utf8`, `--utf8-to-pc98-8bit`, `--utf8-to-pc6001-8bit`) which will form a dedicated `dwimsy charset` verb and filter applet (`dwimsy-conv`). It's the intended source for `disk.d88`, `disk.fat8`, `core.charsets` (Milestone 2), and `core.fs` filename sanitization. The author's own README is candid that the code "started in ChatGPT" and "is uglier than sin" pending cleanup — a good example of a real candidate for dwimsy's promised readable, documented conversion steps. Tokenized-BASIC detokenization and RBYTE encode/decode (`rbyte.py`, `rbyte88.py`, `rbyte_enc.py`, `rbyte88_enc.py`) are still separate, unintegrated pieces.
  * *Refactoring Status:* Will be used as a backend for `dwimsy extract` disk workflows.
- **[`f-fix/nontama_to_bload`](https://github.com/f-fix/nontama_to_bload)** — two working unpackers, `nontama_to_bload.py` (PC-6001mkII NONTAMA rolling-XOR loader tapes, verified against ~18 released games) and `mload_to_bload.py` (MSX "M"-loader rolling-XOR tapes with bitsum verification), plus `mkrom.py` for building bootable cartridges from the results (handling PC-6001mkII port 0xF0 bank switching and Beluga port 0x7F). Maps to `platforms.unpack` and `platforms.cart_hooks` (Milestone 2). Each unpacker is a standalone script today; dwimsy's plan is to route their output through the shared Layer 3/4 stream and payload handling rather than writing `.bin` directly.
- **[`f-fix/cas2uef`](https://github.com/f-fix/cas2uef)** — a working, narrowly-scoped `cas2uef.py` that converts "compact" (unpadded, non-8-byte-aligned) MSX CAS from DumpListEditor directly into BBC Micro `.uef`. The author's own README flags that the result isn't archival-quality, since CAS carries no timing data and the tool heuristically inserts pauses at detected file-header boundaries. This is the intended basis for `tape.bbc` (Milestone 3), though in dwimsy it's planned to route through the shared logical-stream layer instead of converting directly, so the heuristic pause-insertion can eventually be replaced with real timing where available.
- **[`f-fix/bin2fds`](https://github.com/f-fix/bin2fds)** — a working but self-described "super ugly" **Python 2** script that converts raw `.bin` (such as FDSStick dumps) to Famicom Disk System `.fds`, including multi-side images. Slated for a straight Python 3 port as `disk.fds` (Milestone 2); until then it's the odd one out in this list, since it isn't even Python 3 yet.

---

## Table of Contents
1. [Overview & Approach](#1-overview--approach)
2. [Development Strategy](#2-development-strategy)
3. [Existing Project Lineage & Asset Repositories](#3-existing-project-lineage--asset-repositories)
4. [Component Implementation Status Matrix](#4-component-implementation-status-matrix)
5. [Representation Layers, Real-Time Planes & Hardware Gateway](#5-representation-layers-real-time-planes--hardware-gateway)
   - [Representation Layers and Orthogonal Planes](#representation-layers-and-orthogonal-planes)
   - [Real-Time Streaming Contract](#real-time-streaming-contract)
   - [Timebase as a First-Class Representation](#timebase-as-a-first-class-representation)
   - [Hardware Transducer & Tri-Directional Control Gateway ("DWIMSY Box")](#hardware-transducer--tri-directional-control-gateway-dwimsy-box)
   - [On-Demand Disk / Track Streaming](#on-demand-disk--track-streaming)
   - [Transport Automation Spectrum: From Manual Relays to Fully Logic-Controlled Decks](#transport-automation-spectrum-from-manual-relays-to-fully-logic-controlled-decks)
   - [Runtime Media Management, Adaptive Modes & Content-Aware Transport](#runtime-media-management-adaptive-modes--content-aware-transport)
   - [Fresh Blank Media Creation, Auto-Naming & Out-of-Band Storage](#fresh-blank-media-creation-auto-naming--out-of-band-storage)
   - [ROM Cartridges as Tape Containers & BIOS Hook Injections](#rom-cartridges-as-tape-containers--bios-hook-injections)
   - [Physical Cassette Shell Profiling & Nominal Whole-Tape Geometry](#physical-cassette-shell-profiling--nominal-whole-tape-geometry)
   - [Preservation Dimensions, Epistemic Tags & Non-Destructive Write Overlays](#preservation-dimensions-epistemic-tags--non-destructive-write-overlays)
6. [Evidence, Models, and Preservation Status](#6-evidence-models-and-preservation-status)
   - [Status of Technical Claims](#status-of-technical-claims)
   - [Preservation Hierarchy](#preservation-hierarchy)
   - [Mixed-Mode Media](#mixed-mode-media)
   - [Physical-Equivalent Cassette Modeling](#physical-equivalent-cassette-modeling)
7. [Systematic Flavor Taxonomy & No-Intro Naming](#7-systematic-flavor-taxonomy--no-intro-naming)
8. [CLI & Interface Conventions](#8-cli--interface-conventions)
9. [Metadata, Checksums & Archival Packaging](#9-metadata-checksums--archival-packaging)
10. [Forensic DSP & Restoration Engines](#10-forensic-dsp--restoration-engines)
11. [Multi-Phase Implementation Roadmap](#11-multi-phase-implementation-roadmap)
12. [Format & Protocol Technical Reference Guide](#12-format--protocol-technical-reference-guide)
13. [Note on the code and the tools used to write it](#13-note-on-the-code-and-the-tools-used-to-write-it)

---

## 1. Overview & Approach

`dwimsy` is a modular Python toolkit and real-time media transducer for decoding, restoring, converting, and analyzing vintage computer media (cassette audio, disk images, ROM cartridges, and stream dumps). 

It is designed to grow incrementally, adding support for new computer platforms, physical media types, modulations, filesystems, and recovery scenarios over time.

### Core Design Principles
* **Composable Unix Filters + Shared Core**: Individual tools (`t882wav`, `wav2t88`, `flac2wav`, `cas2wav`, `bin2fds`, `dwimsy-conv`, etc.) can be piped together in standard shells (`stdin`/`stdout` streaming with `-`) or called through a central CLI (`dwimsy`). All tools share a common internal library. Streamability is not by itself a claim of real-time suitability: live-capable stages must declare bounded lookahead, maximum buffering, processing latency, startup latency, and resynchronization latency.
* **Zero Required Dependencies & Standalone Operation**: Built on Python 3.9+ standard library (`math`, `struct`, `array`, `io`, `sys`, `shutil`, `os`, `argparse`). Pure-Python biquad/IIR direct form filter engines provide full DSP functionality out-of-the-box. Acceleration libraries (like NumPy/SciPy) are strictly optional and auto-detected for high-throughput batch processing.
* **Offline Operation (No Network & No Embedded DBs)**: `dwimsy` contains no embedded software lists and performs no network lookups. Extended No-Intro metadata is applied when explicitly provided by the user (via CLI options or input filenames); otherwise, standard clean filenames based on the input basename or tape header preambles are used directly without friction.
* **Empty Tape Deck Mode**: Can be launched with zero initial media inputs, operating as an unpopulated virtual cassette transport ready to record software from scratch over `CMT-OUT` or mount images via the 2-line LCD browser.
* **Always-Available User Channel & Ephemeral Imports**: The supervisor import/export channel is always active. Images imported into a session are held ephemerally in the Virtual Image Root without touching host directories unless explicitly exported.
* **Ephemeral In-Memory / Crash-Safe Mode (`--ephemeral`)**: When activated, ensures that no write overlays, generated save tapes, or session modifications are persisted to disk or persistent cache across runs, remaining clean even after sudden termination or power loss. Temporary storage uses auto-cleaned scratch directories or RAM.
* **Preservation Before Interpretation**: A preservation workflow should capture and retain the highest-fidelity available source signal before conditioning, decoding, timebase correction, canonicalization, or synthesis. Derived artifacts are never substitutes for the source capture.
* **Evidence and Claims Are Separate**: A decoded file, segmentation boundary, timing model, or semantic interpretation may be useful without being certain. Wherever practical, dwimsy records the evidence, transformation, confidence, and epistemic status that support a derived result. Canonicalization is purpose-specific and lossy by definition; it never replaces the preservation master.
* **Automated Physical Side/Tape Slicing (`--multi-side`)**: Automatically detects non-magnetic clear leader tape and magnetic tape hiss dropouts (15–25 dB step-change), splitting continuous deck digitizations into verified `Tape X Side A/B` boundaries.
* **Standard [No-Intro Naming Conventions](https://wiki.no-intro.org/index.php?title=Naming_Convention)**: Defaults to clean naming for all output files. Tool name/version tags are strictly avoided in filenames (except where mandated by container specifications like TSX tool metadata blocks).
* **Systematic Flavor Defaults**: Each layer has an untagged canonical default flavor (e.g. standard 8-byte padded `.cas` for MSX, trimmed `.cmt` for PC-88). Non-default variants (untrimmed raw streams, compact unpadded CAS) receive standard qualifier tags and exist side-by-side to guarantee hash matches across MAME Softlists, No-Intro, and TOSEC.
* **Canonical Default Collapsing**: `dwimsy` automatically emits both explicit long names and collapsed canonical default slugs (e.g., `door_door_a.t88` and `door_door.t88` linked to Side A; `salad1_1a.cas` linked to primary part) via non-destructive hardlinking (`os.link`).
* **Contrasting Audio Representation**: Long names treat the raw capture as default (`.flac`) and tag synthesized audio as `[REGENERATED].wav`; short CLI slugs treat usable synthesized audio as default (`.wav`) and qualify raw captures with `_orig.flac`.
* **Self-Contained Archival Bundles**: Input capture files are linked/copied directly inside output bundles alongside full hash suites (Size, CRC32, MD5, SHA1, SHA256) at every abstraction layer.
* **Layered Architecture & Cross-Copy Consensus**: Multi-copy differential recovery and consensus voting operate at signal, flux, container, and logical sector/record layers for both disks and tapes.
* **Fault-Tolerant Automation (`fsck` Model)**: Non-interactive conversions process valid data and isolate corrupted sections with diagnostic logs rather than crashing. An offline interactive recovery mode assists with manual bit/pulse repairs.
* **The Archival Rule (No Premature Inference)**: Never infer structure when the container or physical capture explicitly provides structure (e.g. D88 track offset tables). Preserve the observed source representation before applying interpretation, correction, canonicalization, or synthesis.
* **Information Conservation**: A transformation cannot recover information that its input representation does not contain (e.g., CAS → UEF necessarily invents timing, which must be explicitly marked as `synthetic` / `heuristic`). Canonicalization is purpose-specific and lossy by definition; it never replaces the preservation master.
* **Unified KCS Physical Layer**: For FSK-based systems (PC-88, MSX, BBC Micro, etc.), `dwimsy` utilizes a unified KCS-block (Kansas City Standard) internal representation, allowing high-fidelity export to hardware-compatible containers like TZX, TSX, and CDT.
* **Non-Destructive Write Overlays & Hash-Indexed Media Creation**: Saving to virtual or physical media never overwrites pristine captures. Overlays are stored out-of-band in `~/.cache/dwimsy/overlays/<SHA1>/`, while newly created save media is placed in `~/.local/share/dwimsy/created/<SHA1>/` (associated with the initial tape hash, or `da39a3ee5e6b4b0d3255bfef95601890afd80709` for empty sessions).

---

## 2. Development Strategy

`dwimsy` employs an **Adapter-first bootstrapping strategy**. Rather than deferring the high-level Transducer/Bridge features until a perfect refactor is complete, we wrap the existing "slop" tools into the `dwimsy` orchestration layer:

*   **Phase 0.5 Adapters**: Define the `PulseStream` and `ByteStream` interfaces. Wrap classes like `BaudAgnosticPulseRecognizer` from `wav2t88` to provide an immediate data source for the Bridge and LCD UI.
*   **UI-First Orchestration**: Build the ANSI Virtual LCD marquee, phone dashboard, and IPC telemetry logic early by polling status and confidence scores from adapted legacy loops.
*   **Parallel Verification**: As legacy logic is migrated into the clean `core.fsk` and `core.pulse` modules, we run the new implementation side-by-side with the original "slop" code to ensure accuracy parity and zero regression.
*   **Feature Injection**: Standalone tools are updated to support `stderr` standard logging and metadata dict injection prior to formal migration, allowing No-Intro naming and live telemetry to function even in the adapter phase.

---

## 3. Existing Project Lineage & Asset Repositories

`dwimsy` integrates and unifies code, tables, and DSP algorithms from several existing repositories:

* [`f-fix/pc88_tape_tools`](https://github.com/f-fix/pc88_tape_tools): NEC PC-8001 / PC-8801 `.t88` container state machines, `.cmt` stream extraction, and `t882wav` / `wav2t88` streaming FSK audio converters.
* [`f-fix/wav2cas`](https://github.com/f-fix/wav2cas): MSX FSK demodulation (`wav2cas`), audio synthesis (`cas2wav`), streaming FLAC decoding (`flac2wav`), analog signal conditioning (`cmt_filter`), and physical cassette channel simulation (`cassette_modeler`).
* [`f-fix/fat8_d88_tool`](https://github.com/f-fix/fat8_d88_tool): NEC PC-8801 / PC-8001 / PC-98 / PC-6001 / Pasopia D88 floppy disk container parsing, FAT8 filesystem extraction/injection, JIS X 0201 / NEC / PC-6001 semigraphics character transcoding filters, N88-BASIC / PC-88 obfuscation engines, and deterministic OS filename sanitization.
* [`f-fix/nontama_to_bload`](https://github.com/f-fix/nontama_to_bload): PC-6001mkII NONTAMA loader and MSX "M"-loader unpackers, PC-6001 and MSX Japanese character mappings, and `mkrom` cartridge builder.
* [`f-fix/cas2uef`](https://github.com/f-fix/cas2uef): MSX `.cas` to BBC Micro Model B `.uef` timing container converter.
* [`f-fix/bin2fds`](https://github.com/f-fix/bin2fds): Raw binary to Nintendo Famicom Disk System / Mitsumi Quick Disk `.fds` image generator.

---

## 4. Component Implementation Status Matrix

| Subsystem / Module | Description | Status | Target Milestone |
| :--- | :--- | :---: | :---: |
| **`core.pulse`** | Edge timing, zero-crossing, time-base correction (TBC), AGC — tuned first against PC-88/PC-8801's 2400/1200 Hz FSK | `[ ] TODO` | Milestone 1 |
| **`core.audio`** | Streaming WAV I/O only (no FLAC yet — that ships with MSX support in Milestone 2) | `[ ] TODO` | Milestone 1 |
| **`core.fsk`** | FSK pulse classifier & UART framing, extracted from `wav2t88`/`t882wav` | `[ ] TODO` | Milestone 1 |
| **`cli.filters.*`** | `t882wav` and `wav2t88` only, ported directly from `pc88_tape_tools` | `[ ] TODO` | Milestone 1 |
| **`cli.dwimsy`** | Minimal CLI exposing only `convert`, wired to `t882wav`/`wav2t88` — remaining verbs land in Milestone 2 | `[ ] TODO` | Milestone 1 |
| **`core.realtime`** | Live-stage contracts, bounded buffering/latency accounting, clocks, backpressure and resynchronization | `[ ] TODO` | Milestone 2 |
| **`dsp.filter`** | Analog filter/wave-shaper & differentiator (`cmt_filter`, ported with MSX support) | `[ ] TODO` | Milestone 2 |
| **`dsp.modeler`** | Magnetic tape channel simulator (`cassette_modeler`, ported with MSX support) | `[ ] TODO` | Milestone 2 |
| **`cli.sidechannel`** | `stderr` virtual LCD, TTY keystrokes & POSIX/Win32 signal dispatcher | `[ ] TODO` | Milestone 2 |
| **`core.charsets`** | Unicode ↔ JIS X 0201 / NEC / MSX / KOI-7 streaming transcoder | `[ ] TODO` | Milestone 2 |
| **`core.fs`** | Filename sanitizer & `link_or_copy` hardlinker/copier | `[ ] TODO` | Milestone 2 |
| **`core.transport`** | Transport automation engine: Tier 1 manual, Tier 2 relay, Tier 3 solenoid logic | `[ ] TODO` | Milestone 2 |
| **`transport.changer`**| Media changer, auto-naming, blank media generator & jukebox policies | `[ ] TODO` | Milestone 2 |
| **`transport.browser`**| LCD 2-line virtual image root browser with type-to-navigate & context tracking | `[ ] TODO` | Milestone 2 |
| **`transport.seeker`** | Content-aware smart seek (file/block/marker navigation & cueing) | `[ ] TODO` | Milestone 2 |
| **`dsp.router`**       | Dynamic mode & modulation router (pilot sniff, auto-turbo switch) | `[ ] TODO` | Milestone 2 |
| **`platforms.cart_hooks`**| ROM cartridge tape containers, BIOS hook extractors & `cas2rom` packagers | `[ ] TODO` | Milestone 2 |
| **`ui.remote`** | IPC control daemon (Unix socket / Named Pipe / WebSocket) for web/phone UI | `[ ] TODO` | Milestone 2 |
| **`disk.d88`** | D88 sector container reader & writer | `[ ] TODO` | Milestone 2 |
| **`disk.fat8`** | FAT8 filesystem parser & injector | `[ ] TODO` | Milestone 2 |
| **`disk.fds`** | FDS / QuickDisk container engine (`bin2fds` Python 3 port) | `[ ] TODO` | Milestone 2 |
| **`platforms.unpack`** | NONTAMA & MSX M-Loader binary unpackers (`mkrom`) | `[ ] TODO` | Milestone 2 |
| **`metadata.archive`** | Archival bundle exporter & `README.md` generator | `[ ] TODO` | Milestone 2 |
| **`tape.variants`** | Multi-flavor generator (Trimmed/Untrimmed, CAS unpadded, P6/P6T pairs) | `[ ] TODO` | Milestone 2 |
| **`tape.geometry`** | Physical cassette shell profiling (C-10..C-90, custom lengths, hub math) | `[ ] TODO` | Milestone 2 |
| **`tape.tzx_family`** | Unified TZX/CDT/TSX container (Spectrum, CPC, MSX FSK/Turbo) | `[ ] TODO` | Milestone 3 |
| **`tape.sharp_mz`** | Sharp MZ-80K / MZ-700 / MZ-800 PWM & 128-byte MZF/MZT | `[ ] TODO` | Milestone 3 |
| **`tape.sharp_x1`** | Sharp X1 2700-baud PWM, `.tap` container, 80C49 deck logic | `[ ] TODO` | Milestone 3 |
| **`tape.fujitsu`** | Fujitsu FM-7 / FM-8 / FM-77 `.t77` pulse container & FSK | `[ ] TODO` | Milestone 3 |
| **`tape.sega`** | Sega SC-3000 / SG-1000 `.cas` adapter | `[ ] TODO` | Milestone 3 |
| **`tape.sord`** | Sord M5 `.cas` adapter (`0x55` sync bursts) | `[ ] TODO` | Milestone 3 |
| **`tape.casio`** | Casio PV-2000 & Casio FP-1100 FSK/PWM tape codec | `[ ] TODO` | Milestone 3 |
| **`tape.p6t`** | PC-6001 `.p6t` container (footer sync, autoboot, `mk2mon`) | `[ ] TODO` | Milestone 3 |
| **`tape.bbc`** | BBC Micro Model B `.uef` reader/writer (`cas2uef`) | `[ ] TODO` | Milestone 3 |
| **`tape.multiplex`** | Multi-platform compilation splitter (*Tape Login*, *Tank Battle*) | `[ ] TODO` | Milestone 3 |
| **`platforms.family_basic`**| Famicom Family BASIC V2/V3 detokenizer & HVC-008 level maps | `[ ] TODO` | Milestone 3 |
| **`cue.engine`** | Companion `<basename>.cue` generator & reader | `[ ] TODO` | Milestone 3 |
| **`dsp.classifier`** | FSK carrier vs. broadband speech/music classifier & leader detector | `[ ] TODO` | Milestone 4 |
| **`platforms.sega_ai`** | Sega AI Computer concurrent stereo engine | `[ ] TODO` | Milestone 4 |
| **`platforms.atari8`** | Atari 8-bit POKEY/Audio concurrent stereo engine | `[ ] TODO` | Milestone 4 |
| **`media.audio_disc`** | Audio-carrier formats (Flexidiscs, CD-DA modulated tracks, GCX CD) | `[ ] TODO` | Milestone 4 |
| **`dsp.harmonize`** | Non-linear time harmonization & reverse print-through recovery | `[ ] TODO` | Milestone 4 |
| **`core.pulse_slicer`**| PWM / Turbo pulse slicer (MSX Turbo, Amstrad Speedlock) | `[ ] TODO` | Milestone 5 |
| **`platforms.studybox`**| Famicom StudyBox dual-track voice + MFM stream decoder & solenoid transport | `[ ] TODO` | Milestone 5 |
| **`platforms.adam_ddp`**| Coleco Adam DDP (80 ips high-speed tape) decoder & servo transport | `[ ] TODO` | Milestone 5 |
| **`platforms.gakken_gcx`**| Gakken Manabu-kun (GCX) MSX-like tape & CD-DA audio disc engine | `[ ] TODO` | Milestone 5 |
| **`platforms.ibm5150`** | IBM PC 5150 cassette demodulator | `[ ] TODO` | Milestone 5 |
| **`platforms.bk0010`** | Soviet Elektronika BK-0010 PDP-11 demodulator | `[ ] TODO` | Milestone 5 |
| **`bus.controller`** | Floppy/Serial/Parallel/IEC bus hardware interfaces (Shugart, Apple, Commodore IEC, SIO) | `[ ] TODO` | Milestone 5 |
| **`disk.flux`** | Floppy disk raw flux decoders (Applesauce .a2r/.woz, Greaseweazle .scp/.raw)| `[ ] TODO` | Milestone 5 |
| **`packaging`** | `pyproject.toml`, pip packaging, API docs | `[ ] TODO` | Milestone 5 |

---

## 5. Representation Layers, Real-Time Planes & Hardware Gateway

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
│   • ROM Cartridges : .rom, .crt (MSX AB, C64, cas2rom) │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ Layer 1: Physical Carrier & Raw Signal Layer  [ ] TODO │
│   • Audio Signals  : WAV, FLAC, Flexidiscs, CD Tracks  │
│   • Raw Pulse Flux : Applesauce (.a2r), Greaseweazle   │
│   • Physical DSP   : Time-Base Correction, AGC, Slicer │
└────────────────────────────────────────────────────────┘
```

### Representation Layers and Orthogonal Planes

The four representation layers describe *what* a transformation represents, but are complemented by orthogonal planes crossing representation boundaries:

```text
Representation layers

  Information / Payload       files, BASIC, binaries, filesystem objects
             ▲
  Protocol / Container        CMT, T88, CAS, UEF, D88, sector streams
             ▲
  Timing / Modulation         symbols, pulses, flux timing, regenerated timing
             ▲
  Physical Signal             PCM audio, raw flux, observed transitions

Orthogonal planes

  Transport / Control         motor, relay, solenoid, drive selection, EOT
  Timebase                    capture time ↔ media time ↔ corrected time
  Segmentation / Cueing       mixed-mode regions and semantic annotations
  Provenance / Preservation   raw masters, derivatives, hashes, epistemic tags
  Live I/O                    bounded-latency streaming between endpoints
```

A codec operates on a representation stream and declares its real-time properties independently of whether its endpoint is a file, pipe, emulator, or physical deck.

### Real-Time Streaming Contract

All tape-format converters are intended to be usable as continuous streaming stages, including when connected directly to physical hardware. For a stage to be declared **live-capable**, its implementation must document and test:
* maximum lookahead;
* maximum buffering / memory footprint (constant-bounded for live stages);
* worst-case processing latency;
* startup latency;
* flush/end-of-stream behavior; and
* maximum resynchronization latency after a dropout or ambiguous region.

A Unix filter that accepts stdin/stdout but buffers an entire file is therefore *streamable* but not *live-capable*. The two properties must not be conflated.

For live operation, a stage must also identify its clock domain and whether its output timestamps refer to capture time, media time, corrected time, or regenerated time. A bounded-latency implementation must not silently introduce unbounded queues while waiting for a future synchronization point. If a format intrinsically requires unbounded lookahead, it is not a live-capable stage even if it can process finite files successfully.

### Timebase as a First-Class Representation

Physical capture time, modeled tape position, corrected media time, protocol timing, and regenerated timing are distinct quantities. Transformations preserve an explicit mapping rather than silently resampling into a single clock domain. On mixed-mode tapes, known CMT timing constrains the tape-speed model used to correct adjacent analog speech/music tracks while leaving original audio waveforms untouched.

### Hardware Transducer & Tri-Directional Control Gateway ("DWIMSY Box")

`dwimsy` operates as a real-time hardware appliance and bridge between retrocomputing systems, physical media transports, modern sound cards, emulators, and human operators:

```text
                  ┌───────────────────────────────────────────────┐
                  │          TRI-DIRECTIONAL CONTROL PLANE        │
                  │                                               │
 [1] UPSTREAM     │ • Host Motor Handshake & Relay Sense (REMOTE) │ [2] DOWNSTREAM
 (Host / Emu) ◄───┼─► Parallel / Serial / IEC / Solenoid Engine   ◄───┼─► (Deck/Drive)
                  │ • Writable Media Non-Destructive Overlays     │   (Relays, Tacho,
                  │                       │                       │    Greaseweazle)
                  │               Synchronized Event              │
                  │                    Timeline                   │
                  │                       ▼                       │
                  │ [3] OPERATOR / SUPERVISOR TELEMETRY PLANE     │
                  │ • Inbound: Keystrokes, Buttons, IPC Commands  │
                  │ • Outbound: Live VU, Motor RPM, Track, Events │
                  │ • Interfaces: stderr ANSI LCD, Sockets        │
                  │                       │                       │
                  │ DATA PLANE (FULL-DUPLEX AUDIO & FLUX)         │
 Host CMT OUT ───►│ • Independent Raw Capture Tee (FLAC / Flux)   │──► Deck Line IN
 Host CMT IN  ◄───│ • Demodulation / Decoding / Canonicalization  │◄─── Deck Line OUT
 (or Soundcard)   │ • Cassette Emulation (`cassette_model`)       │   (or Greaseweazle)
                  └───────────────────────┬───────────────────────┘
                                          │
                          ┌───────────────┴───────────────┐
                          ▼                               ▼
                  Local CLI / LCD / TTY          Phone / Web Dashboard
                  (Keystrokes, stderr)          (Spectrogram, Swaps)
```

#### Tri-Directional Control Mechanics
1. **Upstream Host Control**: Senses host `REMOTE` motor relays, Shugart `/STEP`/`/MOTOR_ON` lines, Commodore IEC serial bus, Atari SIO, Sharp MZ parallel bus lines, or full software transport ASIC command lines (StudyBox / Gakken GCX / Sharp X1).
2. **Downstream Transport Control**: Drives physical deck relays/solenoids (`PLAY`, `STOP`, `REWIND`, `RECORD`), monitors capstan tachometer / reel rotation for instant tape speed feedback, and senses optical end-of-tape (EOT).
3. **Operator / Supervisor Plane (Bidirectional)**:
   * **Inbound Commands**: Operators swap disks, flip tape sides, arm virtual recording modes, create blank save tapes, trigger motor overrides, inject cue annotations, and cycle canonicalization modes without disturbing the real-time audio/flux streaming loop.
   * **Outbound Live Telemetry**: `dwimsy` continuously pushes real-time status messages (transport speed deviation, active cylinder/track, sector ID, demodulator carrier lock, confidence scores, detected filenames during save operations, record-arm status, and write-protection alerts) back to the supervisor interfaces.
   * **Remote Connectivity**: Exposes an out-of-band IPC interface (Unix domain sockets `/var/run/dwimsy.sock`, Windows Named Pipes `\\.\pipe\dwimsy_ctl`, or local WebSockets at `:8080`) so headless appliances can be monitored and driven from a smartphone, tablet, or web dashboard.

### On-Demand Disk / Track Streaming

For disks, the live endpoint may be random-access even though underlying flux/sector codecs stream. A Greaseweazle-backed drive operates as an on-demand track source/sink: an emulator or higher layer requests a cylinder/head track identity, `dwimsy` acquires or regenerates only the required track, and the resulting flux/sector stream flows through the same transformation pipeline used offline. Raw flux capture remains independently archivable. This is intentionally a hardware-adapter requirement rather than a claim about any particular Greaseweazle command syntax; the adapter must be verified against the actual device/API behavior before implementation.

### Transport Automation Spectrum: From Manual Relays to Fully Logic-Controlled Decks

The degree to which media transport is governed by software vs. the human operator varies widely across vintage systems. `dwimsy` formalizes a **Three-Tier Transport Automation Model**:

| Tier | Control Level | Representative Systems | Host Capabilities | User Responsibilities |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1: Manual / Passive** | None (Audio Only) | ZX Spectrum, BBC Micro (Standard), Early PET | Audio IN/OUT only | User manually presses PLAY, STOP, RECORD, REW, FF on prompts |
| **Tier 2: Relay-Gated Motor** | Electrical Spindle Motor Gating | MSX, NEC PC-88 / PC-6001, TRS-80, C64 Datassette | Senses/switches 5V/12V `REMOTE` relay; starts/stops tape motion | User manually depresses mechanical `PLAY` or `RECORD` keys; computer gates motor |
| **Tier 3: Full Logic / Solenoid Control** | 100% Software-Controlled Transport | **Sharp X1 (CZ-800)**, **Famicom StudyBox**, **Gakken Manabu-kun (GCX)**, **Coleco Adam DDP**, **Sharp MZ-80B / MZ-2000 / MZ-2500** | Software commands `PLAY`, `STOP`, `REC`, `FF`, `REW`, `HIGH_SPEED_SEEK`, `HEAD_LOAD`, `EJECT` via 80C49/ASIC/PIO registers | Zero physical key pressing required; host software autonomously seeks lessons, cue points, and records audio |

#### Transport Gating Modes (Handling Missing Motor Relays on ZX Spectrum, MSX, Sharp MZ)
When computers or decks are connected via 2-wire audio cables without a `REMOTE` relay wire (such as standard Sinclair ZX Spectrum hardware, or audio-only MSX/Sharp MZ setups), `dwimsy` provides four selectable transport gating policies:
* **Hardware Relay (`--motor=relay`)**: Strictly obeys host `REMOTE` relay voltage.
* **Passive Continuous (`--motor=continuous`)**: Unbroken real-time playback (simulates a mechanical deck with `PLAY` permanently depressed).
* **Smart Auto-Pause (`--motor=smart-pause`, Default for audio-only)**: Streams entire **Loading Groups** (consecutive blocks making up a level, screen, or stage) in one continuous pass without stopping, pausing automatically only at true Loading Group boundaries or level transitions. Resumes on `<Space>` keypress.
* **Carrier-Sensed Gating (`--motor=carrier-sense`)**: For recording over `CMT-OUT`: automatically engages recording upon detecting 1200/2400 Hz carrier tones, pausing when the carrier drops.

#### Modeling the Tier 2 Record Interlock
On Tier 2 systems (MSX, PC-88, PC-6001):
1. **Mechanical Record Arming**: The user must mechanically depress `RECORD` + `PLAY` on the deck (engaging head carriage and record bias circuits).
2. **Electrical Motor Gating (`REMOTE`)**: Tape motion does *not* begin immediately; the host computer holds the `REMOTE` relay open until the BIOS save routine is ready → closes relay → tape writes → opens relay → tape stops, remaining mechanically armed in record mode.
* In `dwimsy`, users can virtually arm recording mode (`<R>` key, appliance button, or UI switch). In headless mode (`--record-policy auto-arm`), `dwimsy` auto-arms upon detecting valid modulated carrier tones on `CMT-OUT`.

#### Modeling Tier 3 Smart Transport Engines
For Tier 3 systems (Sharp X1, Famicom StudyBox, Gakken Manabu-kun GCX, Sharp MZ-2000, Coleco Adam):
* `dwimsy` provides complete hardware emulation of the host transport command protocol.
* **Sharp X1 (CZ-800 series)** utilizes a dedicated NEC 80C49 microcontroller for software deck automation, supporting high-speed tape counter reading, filename-based hardware fast-forward seeks, software `EJECT` commands, and 2700-baud Sharp PWM transfers.
* **Gakken Manabu-kun (GCX)** utilizes an MSX-adjacent Z80/VDP architecture with both logic-controlled tape decks and **Audio CD (CD-DA)** models that interleave modulated software programs with high-fidelity listenable voice/music tracks.
* When the StudyBox, X1, or GCX BIOS issues seek, fast-forward, or audio-record commands, `dwimsy` executes content-aware seek routines, aligns audio/data heads, and engages recording channels completely autonomously without requiring manual user intervention.

### Runtime Media Management, Adaptive Modes & Content-Aware Transport

#### 1. Runtime Media Changes, Jukebox Policies & Composite Sets (`transport.changer`)
Media swaps occur both via external triggers (user hotkey, phone UI, physical button) and through automated **inference engines**:
* **Manual / Out-of-Band Triggers**: Hot-swapping virtual disks or flipping tape sides (`[` / `]` keys) without resetting the running audio/flux stream or dropping connection to the retrocomputer.
* **Automated Sequential Advance**:
  - **Auto-Flip**: Detects optical leader / end-of-tape (EOT) silence or post-data motor stop and automatically queues Side B.
  - **Multi-Tape / Multi-Disk Carousel**: Automatically traverses multi-tape sets (`Tape 1 Side A` → `Side B` → `Tape 2 Side A` → `Side B` → `...` → loop back to `Tape 1 Side A`).
  - **Composite Side Carousel Sequence**: For multi-tape sets with publisher composite side designations (e.g. *Tomato Hime*), sequences in exact physical order: `Side 1A` → `Side 1B` → `Side 2A` → `Side 2B`.
* **Hardware Bus Synthesis**: During an automated or manual disk change, `dwimsy` asserts `/DISK_CHANGE` (pin 34) and pulses `/INDEX` / `/READY` to signal the retrocomputer BIOS that media has been swapped.

#### 2. Virtual Image Root & 2-Line Status LCD File Browser (`transport.browser`)
When browsing media via the `<I>` keystroke in TTY mode:
* **Virtual Image Root**: The top level of the browser always presents a unified virtual root containing all initial CLI-supplied input files, dynamically generated blank save media, and imported images.
* **Always-Available Import/Export Channel**: Operators can dynamically import new images or export artifacts from the Virtual Image Root at any time via TTY local commands (`:import`, `:export`) or remote phone/web dashboard endpoints.
* **Session-Ephemeral Imports**: Any image imported via the user channel is held ephemerally in the Virtual Image Root without touching host directories unless explicitly exported.
* **Image Root Directory (`--image-root <DIR>`)**: When an image root directory is declared, a `[Browse Directory...]` item is presented at the top level of the Virtual Image Root, allowing navigation into filesystem subdirectories.
* **Context-Aware Initial Location**:
  - If the active media was chosen from the CLI, generated dynamically, or imported → browsing starts in the Virtual Image Root.
  - If the active media was selected from a subdirectory within `--image-root` → browsing opens directly inside that subdirectory.
* **Type-to-Navigate**: In TTY mode, typing alphanumeric characters performs in-place substring filtering across filenames.
* **Seamless Virtual Insertion**: Pressing `<Enter>` selects an image and hot-inserts it into the active transport loop, simulating appropriate door/index pulses to the host retrocomputer without audio dropouts.

#### 3. Out-of-Band Import/Export Control Channel & Ephemeral Mode
* **Ephemeral In-Memory / Crash-Safe Mode (`--ephemeral`)**: Overlays and newly created save media are held strictly in RAM and never written to disk or persistent cache, remaining clean even after sudden termination or power loss. Temporary storage uses auto-cleaned scratch directories or RAM.
* **TTY UI Local Transfer Commands**: Running logically within the TTY frontend without interrupting the audio streaming engine, operators can issue local commands (`:import <path>`, `:export <file> <dest>`, `:save-overlay`) to transfer files into/out of the Virtual Image Root.
* **Remote UI Upload/Download (IPC)**: Web and phone dashboards expose file upload/download endpoints over WebSocket / HTTP. Imported images immediately enter the Virtual Image Root and can be cycled via `[` / `]`.
* **SHA1-Indexed Persistent Overlays**: In non-ephemeral mode, write overlays are stored out-of-band under `~/.cache/dwimsy/overlays/<SHA1>/`, indexed by the master tape SHA-1 hash. Selecting an image with an existing overlay presents an instant choice: `[1] Use Overlay`, `[2] Clean Master`, `[3] Delete Overlay`. Pressing `<D>` in TTY mode discards the active overlay.
* **Pipeline / Filter Default**: Standalone filter applets and piped stream conversions default to cold, read-only mode. If a matching overlay is found in cache, `dwimsy` displays an informational notice on `stderr` explaining the `--overlay` activation flag.
* **Deterministic Verification (`--no-overlay`)**: Explicitly bypasses overlay reading for reproducible verification and testing.

#### 4. Automated Physical Side/Tape Slicing & Leader Detection (`--multi-side`)
When digitizing continuous captures containing multiple cassette sides or tapes:
* **Spectrographic Leader & Hiss Profiling**: Identifies non-magnetic clear leader tape and transport stops via a 15–25 dB step-change dropping from magnetic bias hiss (E_bias ≈ −50 dBFS) to electronic preamp floor (E_floor ≤ −75 dBFS).
* **Validated Lifecycle Interlock**: Only commits a side split when the audio region satisfies a complete tape lifecycle (Leader In → Valid Program/Audio Payload → Leader Out).
* **Default Carousel Sequencing**: Automatically assigns sequential layout (`Tape 01 Side A` → `Side B` → `Tape 02 Side A` → `Side B`) unless overridden by user metadata.

#### 5. Loading Groups & Multi-Block Chaining (`transport.seeker`)
To prevent tedious manual keystrokes during multi-block loading on systems without motor control (e.g. Sinclair ZX Spectrum games like *R-Type* or *Bubble Bobble*, Speedlock protection schemes, MSX multi-loaders, or PC-6001 NONTAMA stages):
* **Three-Level Structural Hierarchy**:
  1. *Block / Record (Layer 2)*: Atomic physical data frame (TZX block, 19-byte Spectrum header, MSX 16-byte chunk, PC-88 `: [addr]` record).
  2. *Loading Group / Load Group (Layer 3)*: Contiguous sequence of blocks streamed in one continuous, uninterrupted pass by the computer's active loader without stopping the tape.
  3. *Segment (Timeline / Mixed-Mode)*: Chronological macro-region on a composite mixed-mode tape (e.g. *Gundam 2* `Segment 01` [Data] ↔ `Segment 02` [Audio Drama]).
* **Automated Group Boundary Detection**:
  - *TZX / TSX / CDT Metadata*: Evaluates block pause values. Non-zero pauses stream automatically; zero-pause blocks (Block `0x20` Stop the Tape / Block `0x2A` Stop in 48K) or TZX Group markers (`0x21`/`0x22`) seal the Loading Group and engage transport auto-pause.
  - *Audio Cadence*: Inter-block gaps < 2.0s maintain continuous streaming; silence drops ≥ 3.0s–5.0s trigger stage auto-pause.
  - *Loader Protocol Signatures*: Recognizes linked loader patterns (Speedlock, NONTAMA, PC-88 CSAVE → MON chains) and groups them automatically.

#### 6. Runtime Conversion Mode & Modulation Switching (`dsp.router`)
Mode switching operates across two distinct dynamics:
* **User-Driven Real-Time A/B Testing**: The operator toggles output modes on-the-fly (`Raw Passthrough` ↔ `Conditioned Filter` ↔ `Canonical Ideal` ↔ `Cassette Hardware Model`) while listening to the real hardware to diagnose edge-case demodulation issues.
* **Inferred / Sniffed In-Stream Modulation Switching**:
  - **Hybrid Speed Loaders**: Software often begins with a standard ROM BIOS FSK header (1200 baud) and switches mid-stream to high-speed custom PWM or Turbo tones (e.g. 3600+ baud). `dwimsy` continuously monitors pilot frequencies and dynamically hot-switches demodulators mid-stream with zero dropped samples.
  - **Adaptive DSP Fallback**: If signal SNR or carrier eye pattern degrades below a confidence threshold, the router dynamically engages secondary phase equalization or alternate slicer hysteresis.

#### 7. Multi-Platform Compilation Splitting & Multi-File Container Packaging (`tape.multiplex`)
For compilation tapes containing programs for multiple target systems and spoken human narration (such as ASCII's *Tape Login* and *Tank Battle* series, or multi-part releases like *Gundam 2* and *Tomato Hime*):
* **Hard Program Fencing**: Intervening human speech/commentary tracks or extended leader silences (>5s) act as hard program boundaries, preventing unrelated titles from merging.
* **Chained Multi-File Container Integrity**: Multi-part programs (e.g., PC-88 tokenized BASIC loader → machine-language engine → graphics/map data; MSX multi-block loads; PC-6001 BASIC → NONTAMA payload) are preserved together inside a single, unified, bootable emulator container image (`.t88`, `.cas`, `.p6t`, `.t77`, `.mzt`, `.tap`, `.cdt`, `.tzx`). This ensures emulators load all subsequent stages automatically without hanging on missing sub-files.
* **Dissected Payload Extraction**: In addition to the bootable multi-file container, individual sub-files (`.cmt`, `.bin`, detokenized `.bas`) are unpacked into a `subfiles/` directory for developer inspection.

#### 8. Three-Tier Ambiguity Resolution Strategy
Generic extensions like `.cmt` (used by PC-88, PC-6001, MSX, FM-7), `.cas` (used by MSX, Sega SC-3000, Sord M5, Casio, CoCo), `.mzt` (Sharp MZ single/multi-file dumps vs QD BSD images), and `.wav` are resolved through a deterministic hierarchy:
1. **Tier 1: Explicit Namespaced Filter Applets**: Direct invocation of single-purpose Unix filters (`dwimsy-msx-wav2cas`, `dwimsy-sega-wav2cas`, `dwimsy-sord-wav2cas`, `dwimsy-wav2t88`, `dwimsy-t882wav`) establishes unambiguous platform context.
2. **Tier 2: Explicit Profile Switches**: High-level commands accept `--profile=` overrides (`--profile=pc88`, `--profile=msx`, `--profile=sega-sc3000`, `--profile=sord-m5`, `--profile=pc6001`, `--profile=fm7`, `--profile=mz700`, `--profile=mz2000`, `--profile=x1`, `--profile=cpc`, `--profile=spectrum`, `--profile=famicom-basic`).
3. **Tier 3: In-Stream Layer 3 Protocol Sniffing**: If no profile is specified, `dwimsy` parses the demodulated stream through parallel platform recognizers (checking for MSX `1F A6` sync tokens, PC-88 `0xD3`/`0x24`/`0x9C` preambles, PC-6001 mode descriptors, Sharp 128B directory blocks, Sharp X1 `.tap` headers, Family BASIC headers, Sega `"SEGA CASSETTE"`, Sord `0x55`+`HEADER`, or FM-7/FM-8 headers).

#### 9. Content-Aware "Smart Seek" (Intelligent Fast-Forward & Rewind) (`transport.seeker`)
Instead of blind time-based skipping, `dwimsy` provides structure-aware transport navigation:
* **Named File & Header Seeking**: Seek directly to a named file (e.g., `seek --file "STAGE2.BIN"` or `seek --type BASIC`).
* **Loading Group Navigation**: Step forward or backward by entire loading groups (`seek --next-group`, `seek --prev-group`).
* **Block & Record Navigation**: Step forward or backward by logical data blocks (`seek --next-block`, `seek --prev-block`).
* **Semantic Marker Seeking**: Instantly cue to narration cue points, audio drama segments, or user cable swap prompts.
* **Calibrated Tape Counter Seek**: Navigates using physical reel rotation models (`seek --counter "0450"`), translating between tape ticks and elapsed master FLAC time.
* **Transport State Integrity**: While seeking in live bridge mode, `dwimsy` coordinates with the retrocomputer host by holding the virtual motor/pause state, smoothly re-engaging carrier lock at the target boundary without triggering framing errors.

### Fresh Blank Media Creation, Auto-Naming & Out-of-Band Storage

Many retrocomputing productivity tools (such as Japanese word processors on the PC-6001mkIISR, database managers on PC-88, or multi-part RPGs) explicitly prompt the user to **"Insert a formatted blank tape/disk for saving user data"**.

`dwimsy` provides built-in facilities to generate and hot-insert virgin save media on demand:
* **Deterministic Auto-Naming & Numbering**: Automatically derives clean, structured filenames linked to the host session:
  - Tape: `Hydlide (Japan) [User Save Tape 01].p6t` or `PC6001_DataTape_2026-08-17_001.wav`
  - Floppy: `Yukara_WordProcessor (Japan) [User Data Disk 01].d88`
* **Pre-Formatted Geometry Presets**: Instantly synthesizes pre-formatted media templates (e.g., fresh C-15/C-30 blank cassette with clear leader + unrecorded magnetic bias silence, or standard pre-formatted FAT8/2D/2DD floppy sector images).
* **Hash-Indexed Out-of-Band Storage**: Created save media is stored in `~/.local/share/dwimsy/created/<SHA1>/`, indexed by the SHA-1 hash of the first supplied image, or `da39a3ee5e6b4b0d3255bfef95601890afd80709` (empty file hash) if started in empty deck mode.
* **Instant Virtual Insertion**: Hot-swaps the active program media with the newly created save media and simulates appropriate physical bus notifications (door open/close cycle, `/DISK_CHANGE` assertion, or motor release) without restarting the audio daemon.
* **Trigger Methods**:
  - **Single Keystroke**: Pressing `<N>` in interactive TTY mode.
  - **Appliance UI**: Long-pressing Button A or selecting "New Blank Tape" from the 2-button LCD menu.
  - **Remote Web/Phone UI**: Tapping "Create & Insert Save Tape".
  - **CLI IPC**: `dwimsy-ctl media new-tape --preset C-30 --auto-name`.

### ROM Cartridges as Tape Containers & BIOS Hook Injections (`platforms.cart_hooks`)

In vintage ecosystems, commercial distributors frequently re-released cassette-based games as ROM cartridges by wrapping the tape payload in a small stub that patches or intercepts ROM BIOS cassette routines (e.g., Al-Alamiah / Sakhr Arabic MSX `cas2rom` cartridges, Korean Zemmix conversions, and PC-6001mkII `mkrom.py` bank-switch cartridges):

```text
┌──────────────────────────────────────────────────────────┐
│              ROM CARTRIDGE CONTAINER (.rom)              │
│                                                          │
│  ┌─────────────────────────┐  ┌───────────────────────┐  │
│  │ BIOS Hook Injection     │  │ Encapsulated Tape     │  │
│  │ • MSX TAPION / TAPIN    │  │ Logical Stream        │  │
│  │ • P6 Port 0xF0 Vector   ├──► (.cas / .p6 / .cmt)   │  │
│  │ • C64 Kernal LOAD Vector│  │                       │  │
│  └─────────────────────────┘  └───────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

* **De-encapsulation & Extraction**: Identifies the BIOS tape hook signatures and extracts the encapsulated logical cassette stream (`.cas`, `.cmt`, `.p6`) and original payload binary directly from cartridge ROM dumps.
* **Encapsulation & ROM Synthesis**: Compiles standalone logical tape files into bootable cartridge ROM images (e.g. `cas2rom` for MSX or `mkrom` with Port `0xF0` / `0x7F` paging for PC-6001mkII).
* **Provenance Correlation**: Links cartridge ROM releases to their original tape releases in the multi-level hash registry, allowing cross-verification between tape dumps and official cartridge conversions.

### Physical Cassette Shell Profiling & Nominal Whole-Tape Geometry (`tape.geometry`)

In vintage software distribution, software was duplicated onto standard or custom physical cassette shells (e.g., a 3-minute program released on a C-10 or C-15 cassette, with the remainder of Side A and the entirety of Side B left unrecorded). When synthesizing audio from logical streams or timing containers (e.g., `.t88`/`.cas`/`.cmt` → `.wav`), `dwimsy` allows declaring **nominal whole-tape geometry**:

* **Standard & Custom Shell Presets**: Supports standard tape lengths (`C-10`, `C-15`, `C-20`, `C-30`, `C-46`, `C-60`, `C-90`, `C-120`) and custom publisher-cut runtimes (e.g., `--tape-length 8.5m` or `--side-duration 4m15s`).
* **Realistic Lead-in & Trailing Infill**: Positions program data after standard non-magnetic clear leader tape and initial magnetic lead-in silence (e.g. 5–10s), then pads trailing tape with realistic modeled analog tape silence / residual bias noise up to the full nominal side length.
* **Side B Infill & Unrecorded Replication**: Optionally produces a structurally matched, unrecorded or blank Side B waveform to mirror the complete physical retail artifact.
* **Reel Hub Physics & Counter Calibration**: Uses tape thickness models (e.g., standard 18 µm for C-60 vs. 12 µm for C-90) and hub diameter (r₀ ≈ 11 mm) to calculate non-linear reel rotational speeds, giving a modeled tape-position estimate (N_counter) across fast-forward and rewind operations; accuracy depends on measured or declared tape/deck parameters and should be treated as an estimate unless independently calibrated.

### Preservation Dimensions, Epistemic Tags & Non-Destructive Write Overlays

#### Five Preservation Dimensions
1. **Artifact Preservation**: Physical scans, packaging, cassette shells, manuals, labels, and other physical-object documentation.
2. **Signal Preservation**: Raw observed signals (for example, lossless FLAC captures from a tape deck or raw flux captures from a disk device). The original capture is a preservation anchor and is never replaced by a cleaned, time-corrected, canonical, or synthetic derivative.
3. **Information Preservation**: Recovered verified blocks, sectors, filesystems, BASIC code, and other decoded information, with uncertainty retained where recovery is incomplete.
4. **Behavioral / Semantic Preservation**: Execution flow, narration/data interleaving, cable connect/disconnect prompts, motor pauses, save/record behavior, and other evidence about how the software and media were intended to interact.
5. **Canonical / Synthetic Derivatives**: Reconstructed idealized media for emulation, comparison, deterministic regeneration, or re-mastering. These are explicitly derived artifacts, not substitutes for the source capture.

#### Epistemic Classification
Every decoded structure or derived claim carries an epistemic tag: `established` (standard/ROM verified), `observed` (empirically seen on real media), `inferred` (working hypothesis), `heuristic` (algorithmic best-fit), or `synthetic` (generated/normalized). These tags describe the status of the *claim*, not merely the file format. Provenance should identify the source evidence and transformation that produced each derivative where practical.

#### Non-Destructive Write Overlays & Media Writable Tracking
Media is tagged as read-only or writable (tracking physical write-protect notches/tabs):
* When writes occur (e.g., in-game saves or `CSAVE`), they **never overwrite the master capture**.
* Writes are recorded as **time-indexed or tape-counter-indexed write overlays** with exact start/end offsets (T_start, T_end).
* When rewinding, subsequent reads seamlessly draw from the overlay for modified regions and from the original master capture elsewhere.
* The UI surfaces the names and types of written overlay files in real time (e.g., `[OVERLAY @ 04:12-05:30: 'SAVED.BAS' (BASIC)]`).

---

## 6. Evidence, Models, and Preservation Status

`dwimsy` is intended to be useful for preservation without overstating what has actually been established. Technical facts, empirical observations, inferred structure, heuristics, and generated material should remain distinguishable.

### Status of Technical Claims

Where practical, documentation and manifests should identify one or more of:
* **established** — supported by a published format specification, ROM/disassembly evidence, service documentation, or independently verified implementation;
* **observed** — directly observed in a physical capture, hardware test, or reproducible experiment;
* **inferred** — a reasoned interpretation supported by available evidence but not yet independently established;
* **heuristic** — an algorithmic guess or best-fit result whose correctness depends on assumptions;
* **synthetic** — generated by dwimsy rather than observed on the source media.

A model parameter should likewise be distinguishable as measured, documented, estimated, or assumed. For example, a cassette model may use a published head-gap equation while still using an estimated head-gap value for a particular deck. The equation and the parameter therefore have different evidentiary status.

### Preservation Hierarchy

The preferred preservation chain is:

```text
physical artifact
      │
      ├── photographs / scans / notes
      │
      ▼
lossless source capture
      │  (for example, FLAC audio or raw flux)
      │
      ├── analysis and segmentation
      ├── recovered signal / timing
      ├── decoded information
      ├── behavioral annotations
      └── canonical / synthetic derivatives
```

A later derivative may be more useful for emulation or regeneration than the source capture, but it does not supersede it. When a transformation is lossy, synthetic, or heuristic, the source and the transformation parameters should remain available so that the result can be re-evaluated as algorithms improve.

### Mixed-Mode Media

A physical tape may contain materially different signal types in one continuous recording: for example, computer-modulated CMT data interspersed with narration or music. `dwimsy` should preserve the continuous source capture and represent the interpretation as a chronological segment timeline. Each segment can then have an appropriate derivative:

```text
master FLAC
    │
    ├── drama/music ──► timebase-corrected waveform derivative
    │
    └── CMT data ────► decoded information ──► canonical regeneration
```

The segment boundaries, timing model, and confidence/evidence supporting them remain separate artifacts. A regenerated mixed-mode tape is therefore reproducible without pretending to be the original physical recording.

### Physical-Equivalent Cassette Modeling

`cassette_model` is also a live hardware-compatibility component. In one direction it can model the signal path between a synthesized CMT stream and a real retrocomputer when the original deck is unavailable; in the other direction it can model the behavior of a particular deck/channel when generating replacement media.

This is distinct from canonical regeneration:

```text
canonical CMT
     │
     ├── canonical modulation ──► idealized signal
     │
     └── cassette_model(deck=X) ──► modeled physical-equivalent signal
```

The model must record its parameters and provenance, and should not be described as an exact reconstruction unless independently validated against the relevant hardware.

---

## 7. Systematic Flavor Taxonomy & No-Intro Naming

To prevent tool-name pollution and keep filenames concise while making it easy to cross-reference No-Intro, TOSEC, and MAME Software Lists where the resulting artifact actually matches their published definition, dwimsy defines a canonical default flavor (no extra tag) for each layer, alongside explicitly tagged variant siblings.
```text
Layer            Default Flavor (Untagged)     Tagged Variant Sibling
──────────────────────────────────────────────────────────────────────────
Layer 1 (Audio)  capture.flac                  capture [REGENERATED].wav
Layer 2 (Cont.)  game (Japan).t88 / .tsx       game (Japan) [canonical-timing].tsx
Layer 3 (Stream) game (Japan).p6 / .cas / .cmt game (Japan) [untrimmed].p6 / [unpadded].cas
Layer 4 (Payload) game (Japan).bin / .rom      game (Japan) [alt-load].bin
```

### Naming & Metadata Policy (Offline & Standalone)
`dwimsy` contains **no embedded software database** and performs **no network queries**. Filename generation follows a zero-friction fallback rule:
* **Default Fallback**: If no metadata is supplied, `dwimsy` derives concise, standard filenames from the input file's basename or internal tape preambles (e.g. `tape01.flac` → `tape01.cmt`, `tape01.t88`; internal headers → `01_DOOR.cmt`). Long multi-tag No-Intro names are skipped entirely when metadata is absent.
* **User-Supplied Metadata**: When full No-Intro style names are desired during ripping, they are derived directly from user-supplied options (e.g. `--name "Crazy Newton (Computer Land Hokkaido) (Japan) (PC-6001 32K Mode 2 Pages 2) [_] [CLOAD-RUN]"` or `--title "Crazy Newton" --publisher "Computer Land Hokkaido" --region "Japan" --system "PC-6001" --ram 32K --basic-mode 2 --pages 2 --load-cmd "CLOAD-RUN" --provisional`) or inherited from an input capture that already carries a No-Intro name.
* **Provisional Tag `[_]`**: Used to mark unconfirmed or provisional titles that require further manual verification.
* **Tape Loading Instructions `[COMMAND]`**: Suffixes like `[CLOAD-RUN]`, `[MON-R-GE000]`, `[LOAD'CAS1-'-RUN]`, `[RUN'CAS0-']`, or `[BLOAD'CAS-',R]` explicitly document the required BIOS loading command.
* **Multi-Side Archival Consolidation**: For composite tapes where sides have differing load commands or baud rates, the top-level archive name reflects comma-separated sets: `[MON-R-GE000, MON-R2-GE000]` and `(PC-8801 N88-BASIC V1 Mode)`. Default baud rates are omitted from individual sides.
* **Composite Side Designations Spanning Multiple Tapes**: For sets where physical packaging and in-game prompts designate composite sides across multiple tapes (e.g. *Tomato Hime* Part 1 `Side 1A`, Part 2 `Side 1B`, Part 3 `Side 2A`, Part 4 `Side 2B`), these designations supersede generic `(Tape X) (Side Y)` tags:
  - Long: `Salad no Kuni no Tomato Hime 1 (Side 1A) (Hudson Soft) [_]`
  - Short: `salad1_1a.cas`, `salad1_1a.wav`, `salad1_1a_orig.flac`
* **Multi-Platform Compilations on a Single Cassette**: For multi-system releases (e.g. *Tank Battle* containing PC-8801, FM-7, PC-6001mkII, FM-8 on one tape), the top-level archive summarizes all systems, while extracted tracks are indexed by file position with platform-specific loading commands:
  - Top Archive: `Tank Battle (ASCII) (Japan) (PC-8801, FM-7, PC-6001 mkII, FM-8) [_]`
  - File 01: `Tank Battle (File 01) (ASCII) (Japan) (PC-8801) [_] [LOAD'CAS1-'-RUN]` ↔ `n80_tank88_file01.cmt`
  - File 02: `Tank Battle (File 02) (ASCII) (Japan) (FM-7) [_] [RUN'CAS0-']` ↔ `fm7_tank7_file02.t77`
  - File 03: `Tank Battle (File 03) (ASCII) (Japan) (PC-6001 mkII Mode 5 Pages 2) [_] [CLOAD-RUN]` ↔ `n62_tank_file03.p6t`
  - File 04: `Tank Battle (File 04) (ASCII) (Japan) (FM-8) [_] [RUN'CAS0-']` ↔ `fm8_tank8_file04.t77`

### Canonical Default Collapsing
To provide clean, immediate usability in emulators while maintaining complete archival sets, `dwimsy` uses non-destructive hardlinking (`os.link`, falling back to `shutil.copy2`):
* **Side A as Canonical Default**: When Side A represents the primary release (e.g. standard 1200 baud version) and Side B is an alternate speed duplicate, `dwimsy` links `door_door_a.t88` to the unsuffixed default `door_door.t88`.
* **Multi-Take / Dump Collapsing**: When multiple audio takes or dumps exist (`tape01`, `copy01`), the verified master dump collapses to the unnumbered base name (`door_door.flac`).
* **Multi-Part / Sequential Media**: For multi-tape games (e.g. *Tomato Hime*), sequential parts are indexed `salad1_1a.cas`, `salad2_1b.cas`, `salad3_2a.cas`, `salad4_2b.cas` linked to their respective No-Intro long names.
* **Multi-Part / Mixed-Mode Media**: For mixed-mode releases (e.g. the PC-88 *Gundam* tape with interleaved narration/music and CMT data), `dwimsy` preserves the complete master capture and a chronological segment timeline. Data regions may yield canonical CMT/T88 derivatives, while adjacent drama/music regions remain tied to their exact master-FLAC timestamps and may receive piecewise timebase correction for a regenerated mixed-mode tape. The physical capture, segmentation evidence, and generated result remain separate artifacts.

### Pairing Rules

1. **PC-6001 (.p6 and .p6t Aligned Pairs)**:
   - `game (Japan).p6` ↔ `game (Japan).p6t`: Clean stream trimmed at verified BASIC 0x0000 EOF / MON :00 terminator for standard emulator compatibility.
   - `game (Japan) [untrimmed].p6` ↔ `game (Japan) [untrimmed].p6t`: Raw stream retaining physical trailing flush padding.
2. **MSX (.cas 8-Byte Padded vs. Unpadded Pairs)**:
   - `game (Japan).cas`: Standard 8-byte boundary padded stream (matching TOSEC / No-Intro / OpenMSX preservation databases).
   - `game (Japan) [unpadded].cas`: Compact unpadded byte stream (raw tight chunks).
   - `game (Japan).tsx`: Physical timing container with KCS Block 0x4B and Turbo Block 0x11.
3. **PC-88 / PC-80 (.t88 and .cmt Pairs)**:
   - `game (Japan).cmt` ↔ `game (Japan).t88`: Canonical DumpListEditor / c2t mastering timing.
   - `game (Japan) [untrimmed].cmt` ↔ `game (Japan) [untrimmed].t88`: Raw physical stream retaining trailing carrier overshoot.
4. **Fujitsu FM-7 / FM-8 (.t77 and .cmt Pairs)**:
   - `game (Japan).t77` ↔ `game (Japan).cmt`: Standard FM-7 / FM-8 timing container.
5. **Sharp MZ & Nintendo Family BASIC (.mzf, .mzt, and .m12 Pairs)**:
   - `game (Japan).mzf` ↔ `game (Japan).mzt`: Single-file MZF / multi-file concatenated MZT.
   - `game (Japan) [pat].mzt`: Preserves optional MZ700WIN header patch block.
   - `game (Japan).fbt` ↔ `game (Japan).mzf`: Famicom Data Recorder level dumps (Excitebike, Lode Runner).
6. **Sharp X1 (.tap and .cmt Pairs)**:
   - `game (Japan).tap` ↔ `game (Japan).cmt`: Sharp X1 2700-baud PWM container.
7. **Sinclair ZX Spectrum / Amstrad CPC (.tzx, .cdt, and .tap Pairs)**:
   - `game (UK).tzx` / `.cdt`: Unified TZX-family container (with Group, Pause, and Stop 48K blocks).
8. **Sega SC-3000 and Sord M5 (.cas Disambiguated Pairs)**:
   - `game (Japan) (SC-3000).cas`: Sega SC-3000 emulator container (`SEGA CASSETTE` header).
   - `game (Japan) (Sord M5).cas`: Sord M5 stream (`0x55` sync bursts).
9. **Multi-File Program Containers**:
   - `game (Japan).t88` / `.cas` / `.tap` / `.tzx` / `.mzt`: Unified bootable container bundling all chained sub-files in sequence.
   - `subfiles/01_file.cmt`, `02_file.cmt`: Individual sliced sub-files for disassembly and reverse-engineering.

---

## 8. CLI & Interface Conventions

### Main CLI Verbs `[ ] TODO`

Rather than forcing all workflows through a generic `convert` command, `dwimsy` provides explicit, typed semantic verbs:

```bash
# Inspect intermediate containers, headers, track tables, and baud rates
dwimsy inspect disk.d88

# Demodulate and recover data with confidence metrics and epistemic metadata
dwimsy recover capture.flac --profile=pc88-cmt

# Extract filesystem contents preserving epistemic tags and raw dumps
dwimsy extract disk.d88 -o ./payloads/

# Extract encapsulated tape logical stream (.cas) from a Sakhr/Al-Alamiah cas2rom cartridge
dwimsy extract game_sakhr.rom --target-stream-type cas -o game.cas

# Convert between format representations (inferred from extensions or explicit profiles)
dwimsy convert input.flac output.t88
dwimsy convert game.d88 game.wav --target-tape-type t88

# Disambiguate generic .cmt, .cas, and .wav files across platforms
dwimsy convert capture.wav output.cas --profile=msx
dwimsy convert capture.wav output.cas --profile=sega-sc3000
dwimsy convert game.cmt game.wav --profile=pc88
dwimsy convert game.cmt game.t77 --profile=fm7
dwimsy convert game.cmt game.tap --profile=x1

# Extract Family BASIC tokenized code, BG graphic tables & level maps
dwimsy extract game.mzt --profile=famicom-basic -o ./famicom_src/

# Launch live bridge in empty tape deck mode (zero initial inputs, ready for development)
dwimsy bridge --deck /dev/ttyUSB0

# Launch live bridge with image root directory for 2-line LCD browser
dwimsy bridge --image-root ./games/ --deck /dev/ttyUSB0

# Launch live bridge in ephemeral mode (overlays and created tapes kept only in RAM/temp)
dwimsy bridge --ephemeral --image-root ./games/

# Split continuous multi-side tape rip automatically on clear leader / hiss dropouts
dwimsy split continuous_rip.flac --multi-side -o ./extracted_sides/

# Archive multi-platform compilation tapes (Tape Login & Tank Battle models)
dwimsy archive "Tape_Login_Vol01.flac" -o ./Tape_Login_Archive/
dwimsy archive "Tank_Battle.flac" \
    --title "Tank Battle" \
    --publisher "ASCII" \
    --region "Japan" \
    --systems "PC-8801, FM-7, PC-6001 mkII, FM-8" \
    --provisional \
    -o ./Tank_Battle_Archive/

# Archive with full user-supplied No-Intro metadata, P6T autoboot footer & provisional tag
dwimsy archive capture.flac \
    --title "Crazy Newton" \
    --publisher "Computer Land Hokkaido" \
    --region "Japan" \
    --system "PC-6001" \
    --ram 32K \
    --basic-mode 2 \
    --pages 2 \
    --load-cmd "CLOAD-RUN" \
    --provisional \
    -o ./Crazy_Newton_Archive/

# Archive a PC-88 tape with full No-Intro long name, catalog ID, and loading command
dwimsy archive input01.t88 \
    --name "Door Door (Side A) (1983-02) (Enix) (Japan) (PC-8801 N88-BASIC V1 Mode) [E-G002 102-13-10] [_] [MON-R-GE000]" \
    -o ./Door_Door_Archive/

# Archive multi-tape MSX sets with BLOAD syntax and composite side tagging (Tomato Hime model)
dwimsy archive salad_tape1_a.flac \
    --name "Salad no Kuni no Tomato Hime 1 (Side 1A) (Hudson Soft) [_] [BLOAD'CAS-',R]" \
    -o ./Tomato_Hime_Archive/

# Compile a tape game into a bootable MSX or PC-6001mkII ROM cartridge (cas2rom / mkrom)
dwimsy package game.cas --target-cart-type msx-sakhr -o game.rom
dwimsy package game.p6 --target-cart-type p6001mk2 -o game_cart.rom

# Synthesize audio with nominal publisher tape geometry (e.g., C-15 shell with blank Side B)
dwimsy convert game.t88 game_c15.wav --tape-length C-15 --generate-side-b --lead-in 8s

# Restore audio or clean up container timing (w2w / t2t)
dwimsy restore degraded.flac clean.wav --canonical

# Slice into tracks (lossless PCM audio or container splits)
dwimsy split tape.flac -o ./extracted_tracks/

# Join tracks or folders into a single image (reads cue if present)
dwimsy join ./extracted_tracks/ -o master.wav

# Content-aware smart seek to specific file, block, or calibrated tape counter
dwimsy-ctl seek --file "STAGE2.BAS"
dwimsy-ctl seek --counter "0350"
dwimsy-ctl seek --next-group
dwimsy-ctl seek --next-block

# Media changing, blank save creation & carousel policy configuration
dwimsy-ctl media new-tape --preset C-30 --auto-name
dwimsy-ctl media new-disk --format fat8-2d --auto-name
dwimsy-ctl media swap-disk "Game_Disk2.d88"
dwimsy-ctl media flip-side
dwimsy-ctl media policy set auto-advance-loop

# Transport arming & record interlock control
dwimsy-ctl transport arm-record
dwimsy-ctl transport set-record-policy auto-arm

# Runtime conversion mode & profile switching
dwimsy-ctl profile set canonical-ideal
dwimsy-ctl profile set hardware-model --deck "Sanyo-PHC-DRIII"

# Stream character set conversion (JIS X 0201 / NEC / PC-6001 / MSX -> UTF-8 / ASCII)
dwimsy charset --from=pc98 --to=utf8 < input.txt > output.txt
```

### Streaming Pipes & Filters `[ ] TODO`
All single-purpose conversion filters support continuous stdin/stdout streaming using `-`:
```bash
# Stream tape audio through bandpass/CMT filter, demodulate to MSX CAS, and extract payload
cat capture.flac \
    | dwimsy-flac2wav - - \
    | dwimsy-cmt-filter - - --mode input \
    | dwimsy-msx-wav2cas - - \
    | dwimsy-cas-extract -

# Demodulate PC-88 audio stream to T88 container and extract sequential CMT stream
cat pc88_tape.flac \
    | dwimsy-flac2wav - - \
    | dwimsy-wav2t88 - - \
    | dwimsy-t882cmt - - > game.cmt

# Extract file from D88 image and pipe through streaming character converter to UTF-8
dwimsy-fat8-extract game.d88 README.TXT - \
    | dwimsy-conv --pc98-8bit-to-utf8 - -
```

### Side-Channel UI, Telemetry Layout & Animated Marquee Display `[ ] TODO`

To prevent UI telemetry from polluting piped data streams:
* **`stdout`**: Dedicated strictly to raw binary data streams (audio PCM, container bytes, payload).
* **`stderr`**: Formats an out-of-band 2-line "Virtual LCD" status display (ANSI in-place update), cleanly mapping to physical 16x2 / 20x2 / 40x2 character LCDs (HD44780 / OLED).
* **Essential Field Layout & Animated Marquee**:
  To fit all critical fields (**Tape Counter**, **Elapsed/Total Time**, **Block/Group Index**, **File Number**, **File Name**, and **Current Mode**) into compact displays, `dwimsy` uses a fixed top status bar paired with an animated scrolling marquee ticker on the bottom line:
  ```text
  Line 1 (Fixed)  : [C:0342] [04:15/15:00] [MODE:CANONICAL] [SPEED:100.2%]
  Line 2 (Marquee): F02/05 GRP01/03 BLK03/12 > "DRAGON_SLAYER.BAS" [CRC:OK] [REC:ARMED]
  ```
  - **Animated Text Scrolling**: When filenames or metadata strings exceed the line width (e.g. on 16x2 or 20x2 character displays), the text scrolls smoothly with edge pauses so no information is truncated.
  - **Live Overlay & New Media Alerts**: Write-overlay events, record-armed interlocks, fresh blank media insertions, tape leader detections, and carrier status flash cleanly in the marquee without disturbing the real-time audio/flux loop.
* **Interactive TTY Keystrokes & Out-of-Band Control Channel**:
  When `stdin`/`stderr` are on a TTY, direct keystrokes and colon commands control the engine without pausing audio streaming:
  * `Ctrl-S` / `Ctrl-Q`: Stop / Resume transport motion or recording.
  * `<Space>`: Toggle motor pause / play (or advance to next Loading Group).
  * `<R>`: Toggle virtual Record Arming mode.
  * `<N>`: Create, auto-name, and hot-insert a fresh blank save tape/disk.
  * `[` / `]`: Switch to previous / next side or tape in the Virtual Image Root.
  * `<` / `>`: Step transport backward or forward (fast-forward / rewind).
  * `<I>`: Open minimal 2-line LCD file browser (Virtual Image Root / File browser).
  * `<D>`: Discard / purge active write overlay and revert to pristine master.
  * `:import <path>`: Import an external image into the Virtual Image Root on-the-fly.
  * `:export <name> <dest>`: Export any file from the Virtual Image Root to disk.
  * `Arrow Keys` (←/→/↑/↓): Fast-forward, rewind, seek block/group, adjust speed trim.
  * `<Enter>` / `<ESC>`: Menu selection / Back & Cancel.
  * `<M>` or `<Tab>`: Cycle canonicalization / emulation profiles.
* **Remote App & Supervisor Telemetry Stream**:
  * Headless instances expose a lightweight bidirectional IPC socket (`/var/run/dwimsy.sock` or `\\.\pipe\dwimsy_ctl`) and local WebSocket server (`http://dwimsy.local:8080`).
  * `dwimsy` continuously pushes structured telemetry frames to connected supervisor clients:
    * *Signal/DSP*: RMS VU levels, DC bias, SNR, FSK carrier lock, baud tracking jitter.
    * *Transport*: Instantaneous motor speed (e.g. `+1.3%`), capstan tacho counts, head cylinder/track, record arming status, write-protect sense.
    * *Protocol/Filesystem*: Active sector ID, active Loading Group, detected filename and format during writes, CRC/parity flags.
  * Smartphone or desktop web dashboards can connect to display live waterfall spectrograms, monitor VU levels, flip tape sides, insert floppy images, upload/download virtual root files, toggle record arming, and tag cue markers remotely.
* **POSIX Signals & Appliance Buttons**:
  * `SIGUSR1` (Button A): Advance track / Swap disk / Flip tape side (A ↔ B).
  * `SIGUSR2` (Button B): Cycle profile (`Raw` → `Conditioned` → `Canonical` → `Cassette Model`).
  * `SIGHUP`: Reload geometry / re-sync.
  * `SIGINT` (`Ctrl-C`): Graceful shutdown and provenance flush.

### Positional Per-Input Options (SoX / FFmpeg Model) `[ ] TODO`

Options placed immediately before an input file act as scoped overrides:
```bash
dwimsy join \
    --profile pc88   loader.cmt \
    --profile pc6001 game.p6 \
    -o master.wav --wave tape --volume 0.85
```

### File Linking & Paired Naming `[ ] TODO`

* When metadata is supplied, `dwimsy` emits both a compact CLI name (`crazy_a.p6`) and an extended No-Intro long name (`Crazy Newton (Computer Land Hokkaido) (Japan) (PC-6001 32K Mode 2 Pages 2) [_] [CLOAD-RUN] 32k.p6`) in a flat directory.
* Links are created with `os.link`, falling back automatically to `shutil.copy2` on FAT32/exFAT, cross-device mounts, or unsupported environments.
* Input capture files are linked/copied directly inside output bundles under standard names.

---

## 9. Metadata, Checksums & Archival Packaging

### Multi-Level Hash Registry `[ ] TODO`

Every file entry across manifests, `README.md`, and inspection reports provides the complete hash suite (Size in bytes, CRC32, MD5, SHA1, SHA256) to enable cross-referencing against MAME Software Lists, TOSEC, and No-Intro:
```text
hashes:
  # Layer 1: Raw Analog Capture (Matches MAME Softlist / CHD hashing)
  layer1_analog_audio:
    filename: "door_door_tape01_a_orig.flac"
    size_bytes: 24741464
    crc32: "89ABCDEF"
    md5: "c4ca4238a0b923820dcc509a6f75849b"
    sha1: "356a192b7913b04c54574d18c28d46e6395428ab"
    sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

  # Layer 2: Physical Timing Container
  layer2_container:
    filename: "Door Door (Side A) (1983-02) (Enix) (Japan) (PC-8801 N88-BASIC V1 Mode) [E-G002 102-13-10] [_] [MON-R-GE000].t88"
    size_bytes: 27200
    crc32: "12345678"
    md5: "5d41402abc4b2a76b9719d911017c592"
    sha1: "da39a3ee5e6b4b0d3255bfef95601890afd80709"
    sha256: "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

  # Layer 3: Logical Stream (Trimmed & Untrimmed Flavors)
  layer3_logical_stream:
    trimmed_clean:
      filename: "Door Door (Side A) (1983-02) (Enix) (Japan) (PC-8801 N88-BASIC V1 Mode) [E-G002 102-13-10] [_] [MON-R-GE000].cmt"
      size_bytes: 26830
      crc32: "EEFF0011"
      md5: "098f6bcd4621d373cade4e832627b4f6"
      sha1: "2ef7bde608ce5404e97d5f042f95f89f1c232871"
      sha256: "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"
      no_intro_match: "Door Door (Japan) (PC-8801)"
    untrimmed_raw:
      filename: "Door Door (Side A) (1983-02) (Enix) (Japan) (PC-8801 N88-BASIC V1 Mode) [E-G002 102-13-10] [_] [MON-R-GE000] [untrimmed].cmt"
      size_bytes: 26856
      crc32: "AABBCCDD"
      md5: "ad0234829205b9033196ba818f7a872b"
      sha1: "7c211433f02071597741e6ff5a8ea34789abbf43"
      sha256: "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a"
```

### Transformation Provenance Graph & Write-Overlay Ledger `[ ] TODO`

Transformations, created media, and non-destructive write sessions are recorded with complete provenance:
```yaml
provenance:
  input:
    file: "door_door_tape01_a_orig.flac"
    sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  transformation: "wav2t88"
  tool_version: "dwimsy-core 0.1.0"
  parameters: { baud_tracking: "adaptive", agc: true, dc_block: true }
  confidence: 0.984
  output:
    file: "door_door_tape01_a.t88"
    sha256: "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

write_overlays:
  - overlay_id: 1
    master_sha1: "da39a3ee5e6b4b0d3255bfef95601890afd80709"
    overlay_path: "~/.cache/dwimsy/overlays/da39a3ee5e6b4b0d3255bfef95601890afd80709/session01.wav"
    tape_counter_start: "0342"
    tape_counter_end: "0410"
    timestamp_start_s: 252.18
    timestamp_end_s: 310.45
    detected_payload:
      filename: "SAVED.BAS"
      type: "PC-88 N88-BASIC Tokenized"
      crc: "9A8B7C6D"

created_media:
  - media_id: 1
    session_master_sha1: "da39a3ee5e6b4b0d3255bfef95601890afd80709"
    file_path: "~/.local/share/dwimsy/created/da39a3ee5e6b4b0d3255bfef95601890afd80709/save_tape01.p6t"
    preset: "C-30"
```

### Trailing Byte Trimming & Motor Coasting Ledger `[ ] TODO`

When BIOS routines (PC-6001, MSX CSAVE, PC-88) write padding bytes that CLOAD ignores during motor coast:
* **RLE Pattern Representation**: Documented in `manifest.yaml` as `pattern: "00*26"` or `pattern: "FF*18"`.
* **Byte Offset & Reason**: Stored in manifest metadata to allow reversible reconstruction.

---

## 10. Forensic DSP & Restoration Engines

* **Physical Tape Channel Modeling (`cassette_model.py`)**: `[ ] TODO` Physical and magneto-electric tape-head interface simulation:
  * **Wallace Gap Loss**: High-frequency spatial attenuation `L_gap(f) = 20 × log₁₀(|sin(πg/λ)/(πg/λ)|)` for head gap `g` (for example, ~1.5 µm as a model parameter) at tape speed `v` (for example, 4.76 cm/s; `λ = v/f`).
  * **IEC Type I Equalization**: Standard record pre-emphasis and playback de-emphasis (`τ₁ = 3180 µs`, `τ₂ = 120 µs`, `τ₃ = 12 µs`), balancing write demagnetization `H_demag(s) = 1 / (1 + sτ₁₂₀)`.
  * **Faraday Induction & Saturation**: Induced voltage `e(t) = −N × dΦ/dt` (+6 dB/octave slope) with an anhysteretic `M(H) = tanh(kH)` saturation model.
  * **Dual Operating Modes**:
    * *Physical-Equivalent Mode*: Models the signal path sufficiently to make a modern source behave like the audio signal a specified vintage deck/system would be expected to deliver to authentic retrocomputer hardware. This is a declared approximation, not a claim of exact waveform reconstruction.
    * *Canonical Regeneration Mode*: Generates intentionally standardized electrical signals for deterministic comparison, emulation, or writing replacement media. The result is synthetic and remains separate from the archival capture.
* **Piecewise Timebase Correction & Mixed-Mode Segmentation**: `[ ] TODO` For composite tapes containing interleaved narration/drama audio and modulated data (e.g. ASCII *Tape Login*, *Tank Battle*, PC-88 *Gundam 2*):
  * Distinguishes human speech from computer carrier tones using spectral entropy, spectral flatness (SFM → 0), and zero-crossing regularity (Δt bimodal distribution).
  * Segments the timeline into audio drama (`.ogg` / `.wav`) and data regions (`.t88` / `.t77` / `.cmt`, `.tap`, `.tzx`) referencing master FLAC timestamps.
  * Derives a tape-speed/timebase model from CMT timing observations where the format and signal quality make those observations reliable; this is an inference/model, not an automatic measurement of physical tape speed.
  * Applies piecewise timebase correction to analog audio tracks without altering their analog waveform, while data segments are canonically regenerated.
  * Emits a companion `<basename>.cue` sheet linking audio and data tracks to exact master FLAC timestamps.
* **Time-Base Correction (TBC)**: `[ ] TODO` Uses carrier timing observations (for formats where 2400 Hz Mark / 1200 Hz Space is established) to estimate playback-speed drift and wow/flutter into standard container timing (e.g., 4,800 ticks/sec container time). The result is an explicit timebase mapping; a particular container tick rate is a representation choice, not a universal physical clock.
* **Adaptive Midpoint FSK Slicer**: `[ ] TODO` Fast edge detection with Schmitt-trigger dynamic hysteresis and midpoint cycle discrimination (`N_mid = (Fₛ/4) × (1/f₀ + 1/f₁)`), using local envelope tracking (AGC attack/release) to ride out fading and dropouts.
* **Zero-Gap Demodulation**: `[ ] TODO` Snaps post-DATA carrier start ticks to the exact end tick of the preceding data block (`T_end = T_start + N_bytes × ticks_per_byte`).
* **Multi-Copy & Multi-Revolution Consensus (Disks & Tapes)**: `[ ] TODO` Merges multiple physical copies or multi-revolution dumps (floppy SCP/A2R/D88 or tape takes) using CRC-verified block/sector consensus.
* **Non-Linear Time Harmonization & Print-Through Recovery**: `[ ] TODO` Dynamic Time Warping on pulse transitions (Δt) to align time-reversed ghost signals from opposite tape sides and repair dropouts.
* **Context-Aware Semantic Recovery (ZX81)**: `[ ] TODO` Uses BASIC line link pointers, token tables, and disassembly branches to solve ambiguous pulse dropouts.
* **Dual-Track Concurrent Stereo**: `[ ] TODO` Independent channel classification and crosstalk bleed rejection (Sega AI Computer, Atari 8-bit, Famicom StudyBox).
* **Virtual Sanyo PHC-DRIII Shaper & Circuit Simulation**: `[ ] TODO` Software differentiator (d/dt), phase equalizer, and exact circuit transfer functions (`cmt_filter.py`):
  * **CMT-IN Input Shaping**: 2-pole bandpass `H_in(s)` tuned to ~2263 Hz (C31=0.1 µF, R21=2.7 kΩ, R20=12 kΩ, C29=1.5 nF) with diode clamping and Schmitt trigger comparator (JRC-311B).
  * **CMT-OUT Output Shaping**: Inverter (74LS14), AC coupling (C31=3.3 µF), LP edge smoothing (R41=1.2 kΩ, C32=22 nF, fc ≈ 6028 Hz), and attenuator divider (R40=4.7 kΩ, R39=100 Ω, -33.6 dB).
  * Octave-doubled fast audio synthesis (2400/4800 Hz).

---

## 11. Multi-Phase Implementation Roadmap

### Phase 0: Orchestration & Adapters `[ ] TODO`
*   Wrap `BaudAgnosticPulseRecognizer` and `T88ToWavSynthesizer` as `dwimsy` adapters.
*   Implement the `sidechannel` ANSI LCD and Marquee ticker polling adapter stats.
*   Standardize legacy tool `stderr` logging for UI interception.

### Phase 1: Minimum Viable Vertical Slice — PC-88 Only `[ ] TODO`

The goal of Phase 1 is a single, narrow, end-to-end path through the architecture — not breadth. No MSX, no disks, no full CLI verb set, no hardware side-channel. Just enough to prove the core abstractions hold up against one real platform with real sample files.

Tasks:
1. `[ ] TODO` Implement `dwimsy.core.pulse` (zero-crossing timer, TBC, AGC, DC-blocker), tuned initially against PC-88/PC-8801's 2400/1200 Hz FSK.
2. `[ ] TODO` Implement `dwimsy.core.audio`: streaming WAV reader/writer only. FLAC support is deferred to Phase 2, where it ships alongside MSX support (`flac2wav`).
3. `[ ] TODO` Implement `dwimsy.core.fsk`: FSK pulse classifier & UART framing, extracted from `wav2t88`/`t882wav`.
4. `[ ] TODO` Port `t882wav` and `wav2t88` as Netpbm-style filters, directly from `pc88_tape_tools`.
5. `[ ] TODO` Implement a minimal `dwimsy` CLI exposing only `convert`, wired to the two filters above. `restore`, `split`, `join`, and `inspect` are deferred to Phase 2, since they depend on flavor taxonomy, hash registry, and provenance features that don't exist yet.
   Verification: `[ ] TODO` Bit-exact roundtrip on a real PC-88 `.t88` sample (e.g. `input01.t88`) through `wav2t88` → `t882wav` → `wav2t88`, matching the original container byte-for-byte.

### Phase 2: MSX Generalization, The TZX Bridge, Full CLI, Disk Subsystems & Flavor Matrix `[ ] TODO`

Phase 2 opens by testing whether Phase 1's abstractions actually generalize — porting a second platform (MSX) before building out anything platform-specific-heavy like disk formats.

Tasks:
1. `[ ] TODO` Port `wav2cas`, `cas2wav`, and `flac2wav` (MSX FSK codec + streaming FLAC I/O), validating that `core.audio`/`core.fsk`/`core.pulse` generalize to a second platform without a rewrite.
2. `[ ] TODO` Implement `dwimsy.tape.tzx_family` as a universal physical-layer export target (The "KCS Bridge").
2. `[ ] TODO` Implement `dwimsy.dsp` (`cmt_filter` wave shaper and `cassette_modeler`), ported with MSX support.
3. `[ ] TODO` Implement `dwimsy.core.realtime` (live-stage contracts, bounded buffering/latency, resynchronization latency, backpressure), first exercised via live-capture support for PC-88 and MSX.
4. `[ ] TODO` Expand the `dwimsy` CLI verb set: `restore`, `split`, `join`, `inspect`.
5. `[ ] TODO` Implement `dwimsy.cli.sidechannel` (`stderr` virtual LCD, TTY keystrokes, POSIX/Win32 signal dispatcher).
6. `[ ] TODO` Integrate `dwimsy.core.charsets` (JIS X 0201, NEC semigraphics, MSX Katakana, ASCII, streaming CLI filter applet).
7. `[ ] TODO` Integrate `dwimsy.disk.d88` and `dwimsy.disk.fat8` (`d882fat8`, `fat82d88`, `d882t88`, `d88_explode`).
8. `[ ] TODO` Port `bin2fds.py` to Python 3 in `dwimsy.disk.fds` (`bin2fds` filter).
9. `[ ] TODO` Implement NONTAMA and MSX M-loader unpackers to standard BLOAD binaries (`mkrom`).
10. `[ ] TODO` Implement `platforms.cart_hooks`: MSX Sakhr `cas2rom` extractor/packer and PC-6001mkII `mkrom` generator.
11. `[ ] TODO` Implement `dwimsy.tape.variants`: Side-by-side flavor generator (Trimmed/Untrimmed, MSX unpadded, `.p6`/`.p6t` aligned pairs) with complete hash/size registry.
12. `[ ] TODO` Implement `dwimsy` archive bundle generator with `manifest.yaml` and `README.md`.

### Phase 3: Extended Tape Containers (TSX, P6T, UEF, Sord, Sega, Sharp, Fujitsu) `[ ] TODO`

Tasks:
1. `[ ] TODO` Implement `dwimsy.tape.tzx_family` (Unified TZX 1.20 / CDT / TSX with Block #4B KCS FSK & Group blocks).
2. `[ ] TODO` Implement `dwimsy.tape.p6t` and `dwimsy.tape.p6` with BIOS CSAVE padding trimmer, autostart footer generation and `mk2mon` labels.
3. `[ ] TODO` Integrate `dwimsy.tape.bbc` (BBC Micro Model B `.uef` via `cas2uef`).
4. `[ ] TODO` Implement Sord M5 and Sega SC-3000 (`.cas`) adapters.
5. `[ ] TODO` Implement Sharp MZ (`.mzf`/`.mzt`) and Sharp X1 (`.tap`) container engines with 80C49 deck logic.
6. `[ ] TODO` Implement Fujitsu FM-7 / FM-8 (`.t77`) pulse container and FSK codec.
7. `[ ] TODO` Implement `platforms.family_basic` (HuBASIC token parser, BG renderer, and HVC-008 level extractor).
8. `[ ] TODO` Add auto-sniffing for `.cas`/`.cmt` flavor disambiguation and multi-platform compilation splitting (*Tape Login* / *Tank Battle* multiplexer).

### Phase 4: Mixed-Mode Media, Dual-Track Stereo & Audio Discs `[ ] TODO`

Tasks:
1. `[ ] TODO` Build narrow-band FSK vs. broadband voice/music spectral classifier.
2. `[ ] TODO` Implement dual-track concurrent stereo profiles (Sega AI Computer, Atari 8-bit, Famicom StudyBox).
3. `[ ] TODO` Add non-magnetic modulated audio disc support (PiO magazine flexidiscs, Starpath Supercharger / MSX CD-DA audio tracks, Gakken GCX CD models).
4. `[ ] TODO` Implement companion `<basename>.cue` generator and cue-driven join.

### Phase 5: Advanced Modulations, Vintage 16-Bit Systems & Packaging `[ ] TODO`

Tasks:
1. `[ ] TODO` Implement `dwimsy.core.pulse_slicer` for PWM Turbo loaders (European MSX, Amstrad Speedlock).
2. `[ ] TODO` Implement Famicom StudyBox MFM stream decoder and full logic solenoid transport.
3. `[ ] TODO` Implement Coleco Adam DDP (80 ips high-speed tape) decoder and servo transport.
4. `[ ] TODO` Implement Gakken Manabu-kun (GCX) MSX-like tape & CD-DA audio disc decoder.
5. `[ ] TODO` Implement vintage 16-bit demodulators: IBM PC 5150 cassette (`.cas`/`.bin`) and Elektronika BK-0010 PDP-11 demodulator with KOI-7 Cyrillic decoding.
6. `[ ] TODO` Implement raw floppy flux decoders and multi-revolution consensus (Applesauce `.a2r`/`.woz`, Greaseweazle `.scp`/`.raw`).
7. `[ ] TODO` Finalize `pyproject.toml`, docstrings, and test suite for pip packaging.

---

## 12. Format & Protocol Technical Reference Guide

The tables in this section are engineering references, not authority by themselves. Values that are format-specific, hardware-specific, or derived from reverse engineering should be independently verified before being treated as established facts. Where a value is a model parameter rather than a format requirement, implementations should record its provenance and epistemic status.

### Physical Modulation Reference Table

| Platform / System          | Modulation Type  | Mark / 1 Frequency                           | Space / 0 Frequency                           | Baud / Data Rate                  | Bit Framing                           |
| :------------------------- | :--------------- | :------------------------------------------- | :-------------------------------------------- | :-------------------------------- | :------------------------------------ |
| **NEC PC-8001 / PC-8801**  | FSK              | 2400 Hz (2 cyc)                              | 1200 Hz (1 cyc)                               | 1200 / 600 baud                   | 1 Start (0), 8 Data (LSB), 2 Stop (1) |
| **NEC PC-6001 / PC-6601**  | FSK              | 2400 Hz (2 cyc)                              | 1200 Hz (1 cyc)                               | 1200 / 600 baud                   | 1 Start (0), 8 Data (LSB), 2 Stop (1) |
| **Fujitsu FM-7 / FM-8**    | FSK (T77)        | 2400 Hz (2 cyc)                              | 1200 Hz (1 cyc)                               | 1200 / 600 baud                   | 1 Start (0), 8 Data (LSB), 2 Stop (1) |
| **MSX / MSX2 (Standard)**  | FSK              | 2400 Hz (2 cyc)                              | 1200 Hz (1 cyc)                               | 1200 / 2400 baud                  | 1 Start (0), 8 Data (LSB), 2 Stop (1) |
| **MSX (Sanyo 2x Fast)**    | Octave FSK       | 4800 Hz (2 cyc)                              | 2400 Hz (1 cyc)                               | 2400 baud                         | 1 Start (0), 8 Data (LSB), 2 Stop (1) |
| **MSX (European Turbo)**   | PWM / Pulse      | Short edge pair                              | Long edge pair                                | 2000–4000+ baud                   | Raw bitstream, zero stop bits         |
| **Sharp MZ / MZ-700 / MZ-80K** | PWM (MZT)    | Long pulse pair (≈1000 Hz)                   | Short pulse pair (≈2000 Hz)                   | 1200 baud                         | 128-byte MZT header + tape sync blocks|
| **Sharp X1 (CZ-800 Series)** | Sharp PWM      | Fast pulse interval                          | Slow pulse interval                           | 2700 / 1200 baud                  | 80C49 logic framing & .tap descriptor |
| **Nintendo Famicom Family BASIC** | PWM (MZT) | Sharp MZ PWM pulse pair                      | Sharp MZ PWM pulse pair                       | 1200 baud                         | Sharp MZ-compatible modulation/framing|
| **Casio PV-2000 / FP-1100**| FSK / PWM        | 2400 Hz (2 cyc)                              | 1200 Hz (1 cyc)                               | 1200 / 2400 baud                  | Casio unified FSK/PWM tape framing    |
| **BBC Micro Model B**      | FSK (KCS)        | 2400 Hz (2 cyc)                              | 1200 Hz (1 cyc)                               | 1200 / 300 baud                   | 1 Start (0), 8 Data (LSB), 1 Stop (1) |
| **Amstrad CPC (Standard)** | 2-Tone PWM       | ≈667 Hz (750 μs)                             | ≈1333 Hz (375 μs)                             | ≈1000 / 2000 baud                 | 2KB data blocks + 16-bit CRC          |
| **Sord M5 / Sega SC-3000** | FSK              | 2400 Hz (2 cyc)                              | 1200 Hz (1 cyc)                               | 1200 baud                         | 1 Start (0), 8 Data (LSB), 2 Stop (1) |
| **Sega AI Computer**       | Dual FSK/Audio   | Right: 2400/1200 FSK                         | Left: Speech audio                            | 1200 baud                         | Synchronized concurrent stereo        |
| **Atari 8-bit (POKEY)**    | Dual FSK/Audio   | Right: ≈4 kHz                                | Left: Voice audio                             | 600 baud                          | 1 Start, 8 Data, 1 Stop, 128B blocks  |
| **IBM PC 5150**            | Tone Pulse       | 2000 Hz (500 μs)                             | 1000 Hz (1000 μs)                             | ≈1500 baud                        | 256B blocks + CRC16                   |
| **Elektronika BK-0010**    | Pulse Interval   | 2 pulses (500 μs)                            | 1 pulse (1000 μs)                             | ≈1200 baud                        | 16B header + PDP-11 memory image      |
| **Famicom StudyBox**       | Dual MFM/Audio   | Right: MFM Stream                            | Left: Speech audio                            | High-density MFM                  | 1T / 1.5T / 2T cell transitions       |
| **Coleco Adam DDP**        | High-Speed Pulse | 80 ips continuous                            | Bi-directional                                | High-speed DDP                    | 512B blocks + CRC                     |
| **Gakken Manabu-kun (GCX)**| FSK / CD-DA Audio| 2400/1200 FSK & CD-DA Tracks                 | Left: Lesson Audio / Right: Modulated Data    | 1200 baud / CD-DA                 | MSX-adjacent framing & CD tracks      |
| **Starpath Supercharger**  | High-Speed FSK   | ≈8.4 kHz carrier                             | Phase transitions                             | 8400 baud                         | 2KB multi-load banks                  |

### Container Signatures Reference
```text
Format      Extension   Header Signature / Magic Bytes
─────────────────────────────────────────────────────────────────────────────
PC-88 T88   .t88        50 43 2D 38 38 30 31 20 54 61 70 65 20 49 6D 61 67 65 28 54 38 38 29 00
PC-88 CMT   .cmt        D3 D3 D3... (BASIC), 24 24 24... (MON ML), 9C 9C 9C... (ASCII)
FM-7 T77    .t77        FBASIC / 2BS file headers, 0x00*N + 0x3C sync descriptors
MSX TSX     .tsx / .tzx 5A 58 54 61 70 65 21 1A ("ZXTape!") + ver 0x01 0x20/0x21
MSX CAS     .cas        1F A6 DE BA CC 13 7D 74 (8-byte BIOS sync header)
Sharp MZF   .mzf / .m12 01 (File type) + 16-byte filename + 128-byte header
Sharp MZT   .mzt        Multiple 128-byte MZF directory header blocks concatenated in sequence
Sharp X1    .tap        54 41 50 45 ("TAPE") or raw Sharp X1 2700-baud chunks
Family BASIC.mzt / .cas Sharp MZ-compatible PWM block structure with Famicom BASIC V2/V3 header
Famicom Data.fbt / .tp  Raw level dump blocks (Excitebike, Lode Runner, etc.)
BBC UEF     .uef        1F 8B (Gzip header) -> 55 45 46 20 46 69 6C 65 21 ("UEF File!")
Amstrad CDT .cdt        5A 58 54 61 70 65 21 1A ("ZXTape!")
Sinclair TZX.tzx        5A 58 54 61 70 65 21 1A ("ZXTape!")
PC-6001 P6T .p6t        PC6001V format with trailing timing/mode descriptors & autostart footer
PC-6001 P6  .p6         D3 D3 D3... + screen mode / page count descriptor
Sega CAS    .cas        53 45 47 41 20 43 41 53 53 45 54 54 45 ("SEGA CASSETTE")
Sord M5 CAS .cas        55 55 55 55 55 55 55 55 (Sync run) + 'HEADER'
NEC D88     .d88 / .d77 17-byte disk title + 0x00 + 0x00 0x00 0x00 0x00
FDS Image   .fds        46 44 53 1A ("FDS") or Block 1 '*NINTENDO-HVC*'
Applesauce  .woz / .a2r 57 4F 5A 31 / 57 4F 5A 32 | 41 32 52 32 ("A2R2")
Greaseweazle.scp        53 43 50 ("SCP")
C64 CRT     .crt        43 36 34 20 43 41 52 54 52 49 44 47 45 20 20 20 ("C64 CARTRIDGE   ")
```

### Consulted Literature & Technical Specifications Reference

1. **IEC Standard 60094-4 & 60094-5**: "Magnetic Tape Sound Recording and Reproducing Systems" — Standard equalization time constants for Type I cassettes (3180 µs, 120 µs, 12 µs).
   * URL: https://webstore.iec.ch/publication/723
   * Wayback Machine: https://web.archive.org/web/20220601/https://webstore.iec.ch/publication/723
2. **Wallace, R. L. (1951)**: "The Reproduction of Magnetically Recorded Signals", *Bell System Technical Journal*, 30(4), pp. 1145–1173 (Gap and spacing loss equations).
   * URL: https://doi.org/10.1002/j.1538-7305.1951.tb03700.x
3. **Jiles, D. C., & Atherton, D. L. (1986)**: "Theory of Ferromagnetic Hysteresis", *Journal of Magnetism and Magnetic Materials*, 61(1-2), pp. 48–60 (Anhysteretic tape magnetization and AC bias linearization models).
   * URL: https://doi.org/10.1016/0304-8853(86)90066-1
4. **Yamaha Corporation (1984)**: "Yamaha CX5M / YIS-503 Music Computer Service Manual",
   * Fig. 5-5-9: CMT-IN Cassette Interface Input Shaping Circuit (C31, R21, R20, C29, D1/D2, R33, JRC-311B comparator → PSG IOA7).
   * Fig. 5-4-10: PPI PC5 → CMT OUT Cassette Interface Output Shaping Circuit (PPI PC5 → 74LS14 4B inverter, C31, R41, C32, R40/R39 attenuator).
   * URL: https://archive.org/details/yamaha_cx5mu_service-manual
5. **ASCII Corporation / MSX Licensing Corporation (1983)**: "MSX Technical Data Handbook / MSX BIOS Specification",
   * PSG (AY-3-8910 / YM2149) Register 14 (I/O Port A), Bit 7: Cassette Data Input (CMT IN).
   * PPI (8255) Register C (I/O Port C), Bit 5: Cassette Data Output (CMT OUT).
   * URL: https://web.archive.org/web/20230330/http://map.grauw.nl/resources/msx_io_ports.php
6. **UEF Format Specification**:
   * URL: https://mdfs.net/Docs/Comp/BBC/FileFormat/UEFSpecs.htm
7. **CAS File Format Definition**:
   * URL: https://www.msx.org/forum/semi-msx-talk/emulation/how-do-exactly-works-cas-format
8. **Rob Hagemans / PC-BASIC Project**: "Protected File Format" — reverse-engineering of GW-BASIC's protected-save (`,P`) obfuscation scheme (the paired 11-byte/13-byte XOR key structure). Documents the algorithm's internal workings for GW-BASIC, not NEC's dialects.
   * URL: https://robhagemans.github.io/pcbasic/doc/2.0/#protected-file-format
9. **NEC (1983)**: "PC-8001 mkII SR N80-BASIC / N80SR-BASIC Reference Manual" — documents the `,P` protected-save *access method* (the `SAVE`/`BSAVE` flag itself) but not the obfuscation algorithm's internal workings.
10. **`fat8_d88_tool` project (original research)**: Recognizing that NEC's N88-BASIC protected-save format follows the same paired-XOR-key structure documented for GW-BASIC (per item 8) but with different key data baked into PC-88 ROM, and devising a known-plaintext `SAVE`-based method to recover the PC-88 combined XOR key without needing the ROM itself. The related PC-98 `N88-BASIC(86)` protected-save format uses an unrelated single-bit-rotation scheme, identified independently by direct known-plaintext testing rather than from any published reference. See the [`fat8_d88_tool` README](https://github.com/f-fix/fat8_d88_tool#de-obfuscation-pc98-version) for the full derivation and recovered key material.

---

## 13. Note on the code and the tools used to write it

Parts of this code were written (including some initial ones that began in other, separate projects) with assistance from LLM-integrated coding tools. If you don't like it, feel free to use other software or rewrite parts you dislike. PRs are welcome!

### How did I end up using those? Don't I dislike slop?

Yes, I hate slop. This project began because I wanted tape image conversion tools where the conversion steps were all clearly documented and readable code, but which also performed well enough in terms of accuracy to actually be the tool I use. I started out writing the tools myself, but my manual attempts hadn't yielded comparable accuracy to existing closed-source tools for some steps, so I started using the tools to help find the bugs and suggest improvements, and IMO the result is now good enough to actually be useful in some scenarios. In terms of slop, the tool-generated code doesn't closely resemble any existing solutions I have found. Rather it's a fairly passable translation of my requests into Python.
