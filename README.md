# dwimsy
dwimsy - retrocomputing media preservation, demodulation, restoration, and preparation

**Version: 0.1.6.69-dev** (Milestone 1.6 [IN PROGRESS], 2026-09-02)

grandiose version: (Phase 1 & Milestone 1.5 Complete, Milestone 1.6 in progress)
> **D**oing **W**hat **I** **M**ean, **S**alvaging **Y**esteryear - Format-Aware Media Transducer & Preservation Gateway
>
> A modular toolkit for vintage computer tapes, disks, ROMs, and audio captures.

> [!IMPORTANT]
> **DEVELOPMENT STATUS: PHASE 1 & MILESTONE 1.5 COMPLETE; MILESTONE 1.6 IN PROGRESS.**
> Native core libraries for Phase 1 (`core.pulse`, `core.fsk`, and `core.audio`), streaming filters (`cli.filters.t882wav` and `cli.filters.wav2t88`), the unified CLI (`dwimsy convert`, `inspect`, `split`, `join`, `t882wav`, `wav2t88`), documentation viewers (`dwimsy readme`, `dwimsy license`, `dwimsy changelog`, `dwimsy help`), test runner (`dwimsy tests`), and native PC-88 container/protocol modules (`tape.t88`, `protocols.pc88`) are implemented in pure Python standard library. **Milestone 1.6** is establishing the developer infrastructure, packaging, testing, and integrity architecture. The current CLI registers implemented tools and labeled roadmap placeholders: `dwimsy tests`, `dwimsy readme`, `dwimsy license`, `dwimsy changelog`, `dwimsy help`, `dwimsy meta bundle`, `unbundle`, `diff`, `integrity`, `fetch-deps`, `version-bump`, and `lint` are implemented; `bundle-fixtures` remains a Milestone 1.6 placeholder.

### For now, see:

- **[`f-fix/pc88_tape_tools`](https://github.com/f-fix/pc88_tape_tools)** - working NEC PC-8001/PC-8801 tools: `pc88_tape_tools.py` (`.t88`↔`.cmt` conversion, splitting/joining, and structural `analyze`), `t882wav.py` (streaming `.t88`→`.wav` FSK synthesis with `tape`/`acoustic`/`shaped`/`ideal` modes), and `wav2t88.py` (streaming `.wav`→`.t88` demodulation with AGC and baud auto-detection). All three have self-test suites (`--test`) and stdin/stdout piping. Its DSP logic was extracted into `core.pulse`, `core.fsk`, and `core.audio` in Milestone 1, while its container models and protocol state machines are natively implemented in `dwimsy.tape.t88` and `dwimsy.protocols.pc88`. It remains pinned in `deps/` as a dual-run verification baseline during Milestone 1.6 parser and container hardening, and will be permanently ejected upon Milestone 1.6 exit.
  * *Refactoring Status:* Core DSP, container models, and protocol state machines natively implemented in `dwimsy.core.*`, `dwimsy.tape.t88`, and `dwimsy.protocols.pc88`. Submodule retained as verification baseline through Milestone 1.6, then ejected.
- **[`f-fix/wav2cas`](https://github.com/f-fix/wav2cas)** - working MSX-family tools: `wav2cas.py` (WAV/FLAC→CAS demodulation with AGC, adaptive thresholding, and per-block confidence scoring), `cas2wav.py` (CAS→WAV synthesis), `flac2wav.py` (pure-Python FLAC decode, stdin/stdout capable), `cmt_filter.py` (component-level simulation of the MSX CMT-IN/CMT-OUT analog circuits), and `cassette_model.py` (physical tape-channel modeling: IEC pre-emphasis, magnetic saturation, Wallace gap loss). These map to `core.fsk` (Milestone 1), `core.audio` (`flac2wav`), `dsp.filter`, and `dsp.modeler` (`cassette_model`) in Milestone 2. Note `wav2cas.py`/`cas2wav.py` currently take plain file paths only, not `-` for stdin/stdout, unlike the other three tools here; dwimsy's `cli.filters.*` layer is intended to normalize that so all tape tools operate as continuous Unix streaming filters.
  * *Refactoring Status:* Target for `dwimsy.dsp` and MSX physical layer generalization.
- **[`f-fix/fat8_d88_tool`](https://github.com/f-fix/fat8_d88_tool)** - a working D88/FAT8 extractor, tested against PC-6001/PC-6001mkII/PC-6001mkIISR, PC-8801, PC-98, and even a Pasopia disk image, including PC-88/PC-98 obfuscated-save deobfuscation (N88-BASIC bit rotation and PC-88 143-byte combined XOR key recovery) and JIS-adjacent / PC-6001 semigraphics character mapping. It includes dedicated streaming line-by-line character set conversion modes (`--pc98-8bit-to-utf8`, `--pc6001-8bit-to-utf8`, `--utf8-to-pc98-8bit`, `--utf8-to-pc6001-8bit`) which will form a dedicated `dwimsy charset` verb and filter applet (`dwimsy-conv`). It's the intended source for `disk.d88`, `disk.fat8`, `core.charsets` (Milestone 2), and `core.fs` filename sanitization. The author's own README is candid that the code "started in ChatGPT" and "is uglier than sin" pending cleanup - a good example of a real candidate for dwimsy's promised readable, documented conversion steps. Tokenized-BASIC detokenization and RBYTE encode/decode (`rbyte.py`, `rbyte88.py`, `rbyte_enc.py`, `rbyte88_enc.py`) are still separate, unintegrated pieces.
  * *Refactoring Status:* Will be used as a backend for `dwimsy extract` disk workflows.
- **[`f-fix/nontama_to_bload`](https://github.com/f-fix/nontama_to_bload)** - two working unpackers, `nontama_to_bload.py` (PC-6001mkII NONTAMA rolling-XOR loader tapes, verified against ~18 released games) and `mload_to_bload.py` (MSX "M"-loader rolling-XOR tapes with bitsum verification), plus `mkrom.py` for building bootable cartridges from the results (handling PC-6001mkII port 0xF0 bank switching and Beluga port 0x7F). Maps to `platforms.unpack` and `platforms.cart_hooks` (Milestone 2). Each unpacker is a standalone script today; dwimsy's plan is to route their output through the shared Layer 3/4 stream and payload handling rather than writing `.bin` directly.
- **[`f-fix/cas2uef`](https://github.com/f-fix/cas2uef)** - a working, narrowly-scoped `cas2uef.py` that converts "compact" (unpadded, non-8-byte-aligned) MSX CAS from DumpListEditor directly into BBC Micro `.uef`. The author's own README flags that the result isn't archival-quality, since CAS carries no timing data and the tool heuristically inserts pauses at detected file-header boundaries. This is the intended basis for `tape.bbc` (Milestone 3), though in dwimsy it's planned to route through the shared logical-stream layer instead of converting directly, so the heuristic pause-insertion can eventually be replaced with real timing where available.
- **[`f-fix/bin2fds`](https://github.com/f-fix/bin2fds)** - a working but self-described "super ugly" **Python 2** script that converts raw `.bin` (such as FDSStick dumps) to Famicom Disk System `.fds`, including multi-side images. Slated for a straight Python 3 port as `disk.fds` (Milestone 2); until then it's the odd one out in this list, since it isn't even Python 3 yet.
## Table of Contents
1. [Overview & Approach](#1-overview--approach)
2. [Development Strategy](#2-development-strategy)
   - [Test Fixtures & the Road to Redistributable Coverage](#test-fixtures--the-road-to-redistributable-coverage)
   - [Content-Addressed Fixture Indexing & Discovery](#content-addressed-fixture-indexing--discovery)
   - [Running the Test Suite](#running-the-test-suite)
3. [Installation & Usage](#3-installation--usage)
   - [For Developers (Git Submodules)](#for-developers-git-submodules)
   - [Usage](#usage)
     - [`dwimsy convert`](#dwimsy-convert)
     - [`dwimsy inspect`](#dwimsy-inspect)
     - [`dwimsy split`](#dwimsy-split)
     - [`dwimsy join`](#dwimsy-join)
     - [`dwimsy t882wav` & `dwimsy wav2t88`](#dwimsy-t882wav--dwimsy-wav2t88)
     - [`dwimsy tests`](#dwimsy-tests)
     - [`dwimsy help`](#dwimsy-help)
     - [`dwimsy readme` & `dwimsy license`](#dwimsy-readme--dwimsy-license)
     - [`dwimsy changelog`](#dwimsy-changelog)
     - [`dwimsy meta` (Maintainer & Repository Lifecycle)](#dwimsy-meta-maintainer--repository-lifecycle)
       - [`dwimsy meta bundle`](#dwimsy-meta-bundle)
       - [`dwimsy meta unbundle`](#dwimsy-meta-unbundle)
       - [`dwimsy meta diff`](#dwimsy-meta-diff)
       - [`dwimsy meta integrity`](#dwimsy-meta-integrity)
       - [`dwimsy meta version-bump`](#dwimsy-meta-version-bump)
       - [`dwimsy meta fetch-deps`](#dwimsy-meta-fetch-deps)
       - [`dwimsy meta lint`](#dwimsy-meta-lint)
       - [`dwimsy meta bundle-fixtures`](#dwimsy-meta-bundle-fixtures)
   - [Standalone Filter Applets](#standalone-filter-applets)
   - [Developer Workflow](#developer-workflow)
   - [Environment Variables](#environment-variables)
   - [Character & Syntax Considerations](#character--syntax-considerations)
4. [Existing Project Lineage & Asset Repositories](#4-existing-project-lineage--asset-repositories)
5. [Component Implementation Status Matrix](#5-component-implementation-status-matrix)
6. [Representation Layers, Real-Time Planes & Hardware Gateway](#6-representation-layers-real-time-planes--hardware-gateway)
   - [Representation Layers and Orthogonal Planes](#representation-layers-and-orthogonal-planes)
   - [Real-Time Streaming Contract](#real-time-streaming-contract)
   - [Timebase as a First-Class Representation](#timebase-as-a-first-class-representation)
   - [Hardware Transducer & Tri-Directional Control Gateway ("DWIMSY Box")](#hardware-transducer--tri-directional-control-gateway-dwimsy-box)
   - [On-Demand Disk / Track Streaming](#on-demand-disk--track-streaming)
   - [Transport Automation Spectrum: From Manual Relays to Fully Logic-Controlled Decks](#transport-automation-spectrum-from-manual-relays-to-fully-logic-controlled-decks)
   - [Runtime Media Management, Adaptive Modes & Content-Aware Transport](#runtime-media-management-adaptive-modes--content-aware-transport)
     - [1. Runtime Media Changes, Jukebox Policies & Composite Sets (transport.changer)](#1-runtime-media-changes-jukebox-policies--composite-sets-transportchanger)
     - [2. Virtual Image Root & 2-Line Status LCD File Browser (transport.browser)](#2-virtual-image-root--2-line-status-lcd-file-browser-transportbrowser)
     - [3. Out-of-Band Import/Export Control Channel & Ephemeral Mode](#3-out-of-band-importexport-control-channel--ephemeral-mode)
     - [4. Automated Physical Side/Tape Slicing & Leader Detection (--multi-side)](#4-automated-physical-sidetape-slicing--leader-detection---multi-side)
     - [5. Loading Groups & Multi-Block Chaining (transport.seeker)](#5-loading-groups--multi-block-chaining-transportseeker)
     - [6. Runtime Conversion Mode & Modulation Switching (dsp.router)](#6-runtime-conversion-mode--modulation-switching-dsprouter)
     - [7. Multi-Platform Compilation Splitting & Multi-File Container Packaging (tape.multiplex)](#7-multi-platform-compilation-splitting--multi-file-container-packaging-tapemultiplex)
     - [8. Three-Tier Ambiguity Resolution Strategy](#8-three-tier-ambiguity-resolution-strategy)
     - [9. Content-Aware "Smart Seek" (Intelligent Fast-Forward & Rewind) (transport.seeker)](#9-content-aware-smart-seek-intelligent-fast-forward--rewind-transportseeker)
   - [Fresh Blank Media Creation, Auto-Naming & Out-of-Band Storage](#fresh-blank-media-creation-auto-naming--out-of-band-storage)
   - [ROM Cartridges as Tape Containers & BIOS Hook Injections (platforms.cart_hooks)](#rom-cartridges-as-tape-containers--bios-hook-injections-platformscart_hooks)
   - [Physical Cassette Shell Profiling & Nominal Whole-Tape Geometry (tape.geometry)](#physical-cassette-shell-profiling--nominal-whole-tape-geometry-tapegeometry)
   - [Preservation Dimensions, Epistemic Tags & Non-Destructive Write Overlays](#preservation-dimensions-epistemic-tags--non-destructive-write-overlays)
7. [Evidence, Models, and Preservation Status](#7-evidence-models-and-preservation-status)
8. [Systematic Flavor Taxonomy & No-Intro Naming](#8-systematic-flavor-taxonomy--no-intro-naming)
9. [CLI & Interface Conventions](#9-cli--interface-conventions)
10. [Metadata, Checksums & Archival Packaging](#10-metadata-checksums--archival-packaging)
11. [Forensic DSP & Restoration Engines](#11-forensic-dsp--restoration-engines)
12. [Multi-Phase Implementation Roadmap](#12-multi-phase-implementation-roadmap)
13. [Format & Protocol Technical Reference Guide](#13-format--protocol-technical-reference-guide)
14. [Revision History](#14-revision-history)
15. [Note on the code and the tools used to write it](#15-note-on-the-code-and-the-tools-used-to-write-it)
16. [Multi-Stream Version Reconciliation, In-Memory Bootloader & Isolation](#16-multi-stream-version-reconciliation-in-memory-bootloader--isolation)
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
* **Evidence and Claims Are Separate**: A decoded file, segmentation boundary, timing model, or semantic interpretation may be useful without being certain. Wherever practical, dwimsy records the evidence, transformation, confidence, and epistemic status that support a derived result. Canonicalization is purpose-specific and lossy by definition; it never replaces the preservation source capture.
* **Automated Physical Side/Tape Slicing (`--multi-side`)**: Automatically detects non-magnetic clear leader tape and magnetic tape hiss dropouts (15-25 dB step-change), splitting continuous deck digitizations into verified `Tape X Side A/B` boundaries.
* **Standard [No-Intro Naming Conventions](https://wiki.no-intro.org/index.php?title=Naming_Convention)**: Defaults to clean naming for all output files. Tool name/version tags are strictly avoided in filenames (except where mandated by container specifications like TSX tool metadata blocks).
* **Systematic Flavor Taxonomy & No-Intro Naming**: Each layer has an untagged canonical default flavor (e.g. standard 8-byte padded `.cas` for MSX, trimmed `.cmt` for PC-88). Non-default variants (untrimmed raw streams, compact unpadded CAS) receive standard qualifier tags and exist side-by-side to guarantee hash matches across MAME Softlists, No-Intro, and TOSEC.
* **Canonical Default Collapsing**: `dwimsy` automatically emits both explicit long names and collapsed canonical default slugs (e.g., `door_door_a.t88` and `door_door.t88` linked to Side A; `salad1_1a.cas` linked to primary part) via non-destructive hardlinking (`os.link`).
* **Contrasting Audio Representation**: Long names treat the raw capture as default (`.flac`) and tag synthesized audio as `[REGENERATED].wav`; short CLI slugs treat usable synthesized audio as default (`.wav`) and qualify raw captures with `_orig.flac`.
* **Self-Contained Archival Bundles**: Input capture files are linked/copied directly inside output bundles alongside full hash suites (Size, CRC32, MD5, SHA1, SHA256) at every abstraction layer.
* **Layered Architecture & Cross-Copy Consensus**: Multi-copy differential recovery and consensus voting operate at signal, flux, container, and logical sector/record layers for both disks and tapes.
* **Fault-Tolerant Automation (`fsck` Model)**: Non-interactive conversions process valid data and isolate corrupted sections with diagnostic logs rather than crashing. An offline interactive recovery mode assists with manual bit/pulse repairs.
* **The Archival Rule (No Premature Inference)**: Never infer structure when the container or physical capture explicitly provides structure (e.g. D88 track offset tables). Preserve the observed source representation before applying interpretation, correction, canonicalization, or synthesis.
* **Information Conservation**: A transformation cannot recover information that its input representation does not contain (e.g., CAS → UEF necessarily invents timing, which must be explicitly marked as `synthetic` / `heuristic`). Canonicalization is purpose-specific and lossy by definition; it never replaces the preservation source capture.
* **Unified KCS Physical Layer**: For FSK-based systems (PC-88, MSX, BBC Micro, etc.), `dwimsy` utilizes a unified KCS-block (Kansas City Standard) internal representation, allowing high-fidelity export to hardware-compatible containers like TZX, TSX, and CDT.
* **Non-Destructive Write Overlays & Hash-Indexed Media Creation**: Saving to virtual or physical media never overwrites pristine captures. Overlays are stored out-of-band in `~/.cache/dwimsy/overlays/<SHA1>/`, while newly created save media is placed in `~/.local/share/dwimsy/created/<SHA1>/` (associated with the initial tape hash, or `da39a3ee5e6b4b0d3255bfef95601890afd80709` for empty sessions).

---

## 2. Development Strategy

`dwimsy` employs a **Direct Native Extraction, Fault-Tolerant Ingestion & Staged Submodule Ejection** strategy, superseding temporary wrapper scaffolding:

*   **Phase 0 Consolidated into Phase 1**: Rather than maintaining temporary wrapper classes around monolithic legacy scripts, the PC-88 demodulation and synthesis pipeline was decomposed directly into clean native modules (`core.pulse`, `core.fsk`, `core.audio`) in pure Python standard library.
*   **Milestone 1.5 for Full PC-88 Parity**: Milestone 1 proved the core streaming vertical slice (audio capture ↔ FSK pulses ↔ container stream). Milestone 1.5 brought native parity for container-level operations (`dwimsy.tape.t88`, `dwimsy.protocols.pc88`, `split`, `join`, `.t88` ↔ `.cmt`, and structural inspection).
*   **Milestone 1.6 for State-Machine Hardening & Final Submodule Ejection**: Hardens the PC-88 reference implementation with true grammar-based state-machine parsing, full MON checksum validation, fault-tolerant "emit & tag" (`fsck` model) error recovery, WAV `data` chunk boundary clamping, T88 truncation detection, and unified CLI testing (`dwimsy tests`), enabling the clean, permanent ejection of `deps/pc88_tape_tools`.
*   **Fault-Tolerant "Emit & Tag" Model (`fsck` Model)**: In the interests of archival integrity and field usability, corrupted or truncated streams do not crash with unhandled exceptions, nor are errors silently swallowed. The engine reports diagnostics to `stderr`/manifest with exact byte offsets, emits the salvaged payload with an explicit `[truncated]` / `[corrupt]` qualifier and `observed-truncated` epistemic tag, and falls back to raw binary (`.bin`/`.raw`) when high-level structure breaks down.
*   **Dual-Track Parsing (State Machine vs. Resync Fallback)**: The primary parse path is a strict, deterministic state machine. When an unrecognized sequence or corrupted checksum is encountered, the parser drops into a clearly signaled *Resynchronization Mode* that scans forward for known pilot carriers or sync preambles, isolating the intervening unparsed bytes as a `[corrupt_gap]` block.
*   **Staged Submodule Ejections Across Phases 1 & 2**: Rather than waiting for a monolithic Phase 2 completion, submodules are ejected in fine-grained milestones: `pc88_tape_tools` (Milestone 1.6), `wav2cas` (Milestone 2.1), `fat8_d88_tool` & `bin2fds` (Milestone 2.3), and `nontama_to_bload` (Milestone 2.4).
*   **Parallel Verification**: As legacy logic is migrated into clean `core.*` modules, we verify new implementations side-by-side against original standalone tools on identical synthetic waveforms and real captures to ensure bit-level parity and zero regressions.

### Test Fixtures & the Road to Redistributable Coverage

Development and verification currently rely on real cassette captures from the author's personal collection - genuine analog tape audio, plus matching container/logical-stream exports from established tools like DumpListEditor, used to validate that ported logic actually agrees with independent, trusted references. **These are not redistributable and will not be checked into this repository.** They're a private, on-loan working set for active development, not permanent project fixtures - anyone reproducing this project's test results from scratch currently can't, and that's a known, accepted gap for now rather than an oversight.

The intended long-term fix isn't "find more tapes to check in" - it's to prove `dwimsy`'s own resynthesis is good enough to make the problem go away. If `t882wav`'s `tape`/`shaped` modes and `dsp.modeler`'s physical cassette-channel simulation can produce audio realistic enough to stand in for a genuine capture during testing, then **synthetic "pseudotapes," built from content that's freely redistributable from the ground up, become the project's permanent, public, CI-friendly regression fixtures** - no loaned material required at all.

Validating that a pseudotape is actually realistic enough for this, though, needs two things this project doesn't currently have:
- **Redistribution-cleared real tape captures** to compare pseudotapes against, ideally spanning several platforms and tape conditions (fresh, worn, print-through, speed drift).
- **Real hardware access** across the project's target platforms - including some models outside the author's personal collection - to confirm pseudotapes actually load on physical machines, not just in emulators or `dwimsy`'s own demodulator.

`[ ] TODO` **Open call**: solicit redistribution-OK tape captures and, ideally, contributors with real hardware access for platforms not already in the author's collection, to serve as permanent reproducibility fixtures once pseudotape resynthesis is validated against them.


### Content-Addressed Fixture Indexing & Discovery

To ensure long-term reproducibility and eliminate fragile filename assumptions (where one user names a capture `snippet.wav`, another `door_door_1200.wav`, and another `input01.t88`), `dwimsy` uses **content-addressed fixture indexing** (`dwimsy.tests.fixtures`):

* **Semantic Fixture Registry (`FIXTURE_REGISTRY`)**: Maps canonical IDs (e.g. `pc88_door_door_1200_wav`, `pc88_door_door_1200_t88`, `pc88_digdug_600_wav`) to verified SHA-1, CRC32, file size, and descriptive metadata.
* **Filename-Agnostic Discovery (`FixturePool`)**: Scans candidate directories (`--fixtures`, `DWIMSY_TEST_FIXTURES`, in-tree `tests/fixtures/`, `~/.local/share/dwimsy/fixtures/`), indexes files by SHA-1 hash, and automatically binds them to tests.
* **Informative Skip Diagnostics**: If a private fixture is missing, tests skip cleanly with the exact title and hash:
  `skipped 'Fixture "Door Door (Enix)" (SHA1: e24687b3...) not found in fixture pool.'`

### Running the Test Suite

The test suite can be run directly via the unified CLI, standard Python runners, or standalone aliases:

```bash
# Unified CLI test runner (runs in-process from disk or in-memory bundle payload):
dwimsy --test

# Or via Python module runner:
python3 -m dwimsy.tests
python3 -m dwimsy.tests       # or python3 -m dwimsy --test

# Pass custom private fixture path via CLI:
python3 -m dwimsy.tests -v     # or python3 -m dwimsy --test
dwimsy-tests -v -f ./tests/fixtures/

# Scoped testing for specific subsystems:
python3 -m dwimsy.tests fsk -v
dwimsy t882wav --test          # tests only synthesis logic
dwimsy wav2t88 --test          # tests only demodulation logic

# Direct execution via unittest or pytest:
python3 tests                  # default mode
python3 tests -v               # verbose mode
python3 -m pytest tests/ -v    # optional pytest runner
```

**Installing the private test fixtures**, if you have access to them (see above - they aren't in this repository and won't be requested): place them under `tests/fixtures/`, following the layout `tests/fixtures/README.md` documents (`snippet.wav`/`snippet2.wav` under `set1`/`set2`, and real `.t88`/`.cmt` pairs like `input16` directly under `tests/fixtures/`). Fixture-dependent tests skip cleanly rather than failing when their specific input is missing, so the exact skip count in any given run isn't a fixed property of the suite - it depends entirely on which fixtures happen to be installed: with none present, several tests across `core.pulse`/`core.fsk`/`cli.filters` skip; installing just `snippet.wav`/`snippet2.wav` unlocks most of those; adding `input16.t88`/`input16.cmt` on top unlocks the rest, at which point a full run passes with nothing skipped. A custom fixture location can be pointed to instead via the `DWIMSY_TEST_FIXTURES` environment variable, which every fixture-dependent test checks before falling back to `tests/fixtures/`.

---

## 3. Installation & Usage

### For Developers (Git Submodules)
`dwimsy` orchestrates several specialized tools. To fetch the complete source tree including all sub-component logic, use the recursive clone or update commands:

**New Checkout (Fresh Clone):**
```bash
git clone --recursive https://github.com/f-fix/dwimsy.git
```

**Existing Checkout (Update):**
If you have already cloned the repository but the `deps/` directories are empty:
```bash
git pull
git submodule update --init --recursive
```

### Usage

### Standalone Bundle Basics

### Developer Cheat Sheet (The -a Escape Hatch)

Any `dwimsy` bundle or installed command can be forced into a maintainer personality using the `-a` (argv0) override. This allows you to treat any bundle as a toolkit for inspecting or reconstructing other parts of the project.

| Task | Command |
| :--- | :--- |
| **List History** | `python3 dwimsy_bundle.py --version-list` |
| **Diff Checkout** | `python3 dwimsy_bundle.py -a dwimsy meta diff baseline unbundled` |
| **Extract Source** | `python3 dwimsy_bundle.py -a dwimsy-meta-unbundle ./src --deps` |
| **Reconstruct Bundle** | `python3 dwimsy_bundle.py --version=V --version-restrict-to=V -a dwimsy meta bundle --baseline -o out.py` |



Project Homepage: https://github.com/f-fix/dwimsy
Version: 0.1.6.69-dev (2026-09-02)

`dwimsy` is also distributed as a standalone, self-extracting single-file Python script (`dwimsy_0.1.6.69-dev.py`).

To use the embedded dwimsy CLI directly from the bundle:
```bash
python3 dwimsy_0.1.6.69-dev.py dwimsy --help
python3 dwimsy_0.1.6.69-dev.py dwimsy --version
python3 dwimsy_0.1.6.69-dev.py dwimsy readme
python3 dwimsy_0.1.6.69-dev.py dwimsy license
python3 dwimsy_0.1.6.69-dev.py dwimsy changelog
```

To extract the repository tree to disk:
```bash
python3 dwimsy_0.1.6.69-dev.py meta unbundle /path/to/target --deps
```


`dwimsy` is currently invoked from a checkout as `python3 -m dwimsy <command> ...`. **The package is not yet packaged for installation**: there is currently no `pyproject.toml`/`setup.py` console-script entry point, so `pip install -e .` and the bare `dwimsy` command are future Milestone 1.6 work. The currently implemented primary commands are exactly four: `convert`, `inspect`, `split`, and `join`. Two standalone filter applets are also implemented: `t882wav` and `wav2t88`. The `tests`, `help`, `readme`, `changelog`, `license`, and `meta` commands are now fully implemented and available in Milestone 1.6. The current CLI does implement `--help-all`; use `python3 -m dwimsy --help`, `python3 -m dwimsy --help-all`, or `python3 -m dwimsy <command> --help` from the repository environment.

`python3 -m dwimsy` is the recommended form when the repository is the current directory (or the checkout has otherwise been added to `PYTHONPATH`/installed). It does **not** work from an arbitrary directory in the current un-packaged checkout. `dwimsy/__main__.py` also makes the package directory itself directly executable - `python3 path/to/dwimsy <command> ...`, pointing at the `dwimsy/` directory rather than a file - which does work from elsewhere on disk:

```bash
# Equivalent invocations, verified to produce byte-identical output:
python3 -m dwimsy convert game.wav game.t88 --baud 600              # from the repo root
python3 path/to/dwimsy convert game.wav game.t88 --baud 600      # from elsewhere on disk
python3 dwimsy convert game.wav game.t88 --baud 600              # bare package directory from repo root
```

```text
$ python3 -m dwimsy --help
usage: dwimsy [-h] [-V] [-T] [-v] [--help-all] <command> ...

dwimsy - retrocomputing media preservation, demodulation, and conversion.

positional arguments:
  <command>
    convert      Convert between media representations (WAV, T88, CMT).
    inspect      Inspect media container headers and structural contents.
    split        Split multi-file tape images into individual program files.
    join         Join multiple files into a single .cmt or .t88 tape image.
    t882wav      Synthesize PCM WAV audio from a T88 cassette image.
    wav2t88      Demodulate PCM WAV audio into a T88 cassette image.
    tests        Run the dwimsy unit test suite in-process.
    readme       Output project README documentation.
    license      Output project LICENSE terms.
    changelog    Output project revision history from CHANGELOG.md.
    help         Interactive technical manual viewer.
    meta         Maintainer tools and repository lifecycle management.
    charset      [TODO / Milestone 2.3] Streaming character set converter.
    extract      [TODO / Milestone 2.3] Payload and filesystem extractor.
    package      [TODO / Milestone 2.4] ROM cartridge compiler (cas2rom /
                 mkrom).
    bridge       [TODO / Milestone 2.5] Real-time hardware transport gateway.
    archive      [TODO / Milestone 2.5] Archival preservation bundle
                 generator.
    recover      [TODO / Milestone 4.0] Forensic bit/pulse recovery engine.

options:
  -h, --help     show this help message and exit
  -V, --version  show program's version number and exit
  -T, --test     Run unit tests and self-test assertions in-process
  -v, --verbose  Increase test or command verbosity
  --help-all     Show full detailed help for all subcommands at once and exit

Project Homepage: https://github.com/f-fix/dwimsy
Tip: Run 'dwimsy <command> --help' or 'dwimsy --help-all' to view detailed options for all commands.
```

#### `dwimsy convert`

> **Status:** [x] `COMPLETE` for the currently implemented PC-88 WAV ↔ T88 ↔ CMT paths (Milestone 1). MSX, CAS, and disk-format conversion remain [ ] `TODO` in later milestones.

Converts between `.wav` (audio), `.t88` (container), and `.cmt` (logical stream) - in either direction, inferred from file extensions unless `--from-format`/`--to-format` are given explicitly. `-` means stdin/stdout, so all three stages chain through standard pipes.

```text
$ dwimsy convert --help
usage: dwimsy convert [-h] [--from-format FROM_FORMAT] [--to-format TO_FORMAT]
                      [--mode {tape,cassette,acoustic,motor,spinup,shaped,pc,ideal,square}]
                      [--baud {600,1200}] [--bauds BAUDS]
                      [--flavor {verbatim,reconstructed,kinematic-infilled,rom-authentic,canonical}]
                      [--sample-rate SAMPLE_RATE] [--channels {1,2}]
                      [--stereo-mode {dual,left,right,diff}]
                      [--channel {auto,left,right,mix,diff}]
                      [--amplitude AMPLITUDE] [--speed SPEED] [--invert]
                      [--confidence CONFIDENCE] [-q]
                      input output

positional arguments:
  input                 Input file or '-' for stdin
  output                Output file or '-' for stdout

options:
  -h, --help            show this help message and exit
  --from-format FROM_FORMAT
                        Explicit input format (wav, t88, cmt)
  --to-format TO_FORMAT
                        Explicit output format (wav, t88, cmt)
  --mode {tape,cassette,acoustic,motor,spinup,shaped,pc,ideal,square}, -m {tape,cassette,acoustic,motor,spinup,shaped,pc,ideal,square}, --wave {tape,cassette,acoustic,motor,spinup,shaped,pc,ideal,square}
                        Synthesis mode
  --baud {600,1200}, -b {600,1200}
                        Baud rate override (600 or 1200)
  --bauds BAUDS         Comma-separated candidate baud rates for autodetect
                        mode (default: 600,1200)
  --flavor {verbatim,reconstructed,kinematic-infilled,rom-authentic,canonical}
                        Demodulation timing flavor (default: reconstructed)
  --sample-rate SAMPLE_RATE, -r SAMPLE_RATE
                        Audio sample rate (default: 44100)
  --channels {1,2}, -c {1,2}
                        Audio channels (default: 1)
  --stereo-mode {dual,left,right,diff}
                        Stereo routing
  --channel {auto,left,right,mix,diff}
                        Input channel
  --amplitude AMPLITUDE, -a AMPLITUDE, --volume AMPLITUDE, -v AMPLITUDE
                        Audio amplitude 0.01..1.0 (default: 0.80)
  --speed SPEED, -s SPEED
                        Speed multiplier (default: 1.0)
  --invert              Invert audio polarity
  --confidence CONFIDENCE, -C CONFIDENCE, --min-confidence CONFIDENCE
                        Minimum byte confidence (default: 0.75)
  -q, --quiet           Suppress progress output
```

```bash
# Demodulate a real cassette capture to a T88 container, forcing 600 baud
dwimsy convert capture.wav game.t88 --baud 600

# Extract the T88's logical byte stream to .cmt
dwimsy convert game.t88 game.cmt

# Re-synthesize audio from a T88 for playback into real hardware
dwimsy convert game.t88 game.wav --mode tape

# Chain through stdin/stdout
cat capture.wav | dwimsy convert - - --to-format t88 > game.t88
```

#### `dwimsy inspect`

> **Status:** [x] `COMPLETE` (PC-88 T88 & CMT structural analysis in Milestone 1.5; multi-layer/archive inspect [ ] `TODO` in Milestone 2.5)

Reports T88/CMT structure: block breakdown, tick timing, detected baud, and any recognized program files on the tape.

```text
$ dwimsy inspect --help
usage: dwimsy inspect [-h] [-v] [-c {auto,left,right,mix,diff}] input

positional arguments:
  input                 Input file or '-' to inspect

options:
  -h, --help            show this help message and exit
  -v, --verbose         Show verbose block structure
  -c {auto,left,right,mix,diff}, --channel {auto,left,right,mix,diff}
                        Audio channel routing mode for WAV inspection
                        (default: auto)
```

Real example, run against an actual 1980s cassette capture of *Dig Dug* (Dempa Micomsoft, PC-8801):

```text
$ dwimsy convert snippet2.wav game.t88 --baud 600
$ dwimsy inspect game.t88 -v
================================================================================
TAPE ANALYSIS REPORT: game.t88
================================================================================
File Size: 135 bytes
Format:    .t88 Container (Manuke Station / X88000)
Magic:     b'PC-8801 Tape Image(T88)'
Version:   0x0100
Blocks:    8
Duration:  00:03.733 (17,919 ticks @ 4800 Hz)
Payload:   21 data bytes
Tones:     2 Mark (2400 Hz), 1 Space (1200 Hz), 1 Blank Gaps
Est. Baud: 600 baud (~88.0 ticks/byte)

--- T88 Block Breakdown ---
  #000 | VERSION | len=    2 bytes
  #001 | GAP     | tick        0..159      (   159 ticks,  0.033s)
  #002 | SPACE   | tick      159..12872    ( 12713 ticks,  2.649s)
  #003 | MARK    | tick    12872..15163    (  2291 ticks,  0.477s)
  #004 | DATA    | tick    15163..16571    (  1408 ticks,  0.293s) | dlen=   16 [600 baud] [name='DIGDUG' type='BASIC Program (0xD3)']
  #005 | MARK    | tick    16571..17479    (   908 ticks,  0.189s)
  #006 | DATA    | tick    17479..17919    (   440 ticks,  0.092s) | dlen=    5 [600 baud] b'(\x00d\x00\x9d'
  #007 | END     | len=    0 bytes

--- Cassette Content / Programs on Tape ---
Total Programs / Streams Detected: 1
#   | Filename     | File Format / Type                  | Size (Bytes) | Details
------------------------------------------------------------------------------------------
1   | DIGDUG       | BASIC Program (0xD3)                | 21           | Code: 21B
```

#### `dwimsy split`

> **Status:** [x] `COMPLETE` (PC-88 T88 & CMT program splitting in Milestone 1.5; state-machine hardening [ ] `TODO` in Milestone 1.7)

Splits a multi-file tape image into one output file per detected program.

```text
$ dwimsy split --help
usage: dwimsy split [-h] [-o OUTPUT_DIR] [--format {cmt,t88}] [-b BAUD]
                    [--comment COMMENT]
                    input

positional arguments:
  input                 Input .cmt or .t88 file

options:
  -h, --help            show this help message and exit
  -o OUTPUT_DIR, --output-dir OUTPUT_DIR
                        Output directory for split files
  --format {cmt,t88}    Target split format: 'cmt' (default) or 't88'
  -b BAUD, --baud BAUD  Baud rate override for T88 output
  --comment COMMENT     Optional comment embedded in T88 headers
```

```bash
dwimsy split multi_game.t88 -o ./extracted/ --format t88
```

#### `dwimsy join`

> **Status:** [x] `COMPLETE` (PC-88 T88 & CMT concatenation in Milestone 1.5; state-machine hardening [ ] `TODO` in Milestone 1.7)

Merges multiple `.cmt`/`.t88` files into one combined tape image, supporting per-input baud overrides.

```text
$ dwimsy join --help
usage: dwimsy join [-h] -o OUTPUT [--format {cmt,t88}] [-b BAUD]
                   [--bauds BAUDS] [--cmt-baud CMT_BAUD] [--comment COMMENT]
                   inputs [inputs ...]

positional arguments:
  inputs                Input files to merge (supports positional -b/--baud a
                        la SoX)

options:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        Output destination path
  --format {cmt,t88}    Target output format ('cmt' or 't88', inferred from
                        output extension by default)
  -b BAUD, --baud BAUD  Global baud rate override for all T88 outputs
  --bauds BAUDS         Sequential comma-separated baud rates per input (e.g.
                        '1200,600')
  --cmt-baud CMT_BAUD   Default baud rate for raw .cmt inputs when producing
                        .t88
  --comment COMMENT     Optional comment embedded in T88 header
```

```bash
dwimsy join part1.t88 part2.cmt -o prepared.t88 --bauds 1200,600
```


#### `dwimsy t882wav` & `dwimsy wav2t88`

> **Status:** [x] `COMPLETE` (Milestone 1 / Milestone 1.6 top-level routing)

Direct top-level aliases for the streaming filter applets `dwimsy-t882wav` and `dwimsy-wav2t88`, converting directly between `.t88` container streams and `.wav` audio.

```bash
# Synthesize audio from T88 via top-level CLI
dwimsy t882wav game.t88 game.wav --mode tape

# Demodulate audio to T88 via top-level CLI
dwimsy wav2t88 capture.wav game.t88 --baud 600
```

#### `dwimsy tests`

> **Status:** [x] `COMPLETE` (Milestone 1.6)

Runs the built-in in-process test discovery and execution engine across all unit tests and lint verifications:

```text
$ python -m dwimsy.tests --help
usage: python -m dwimsy.tests [-h] [-V] [-T] [patterns ...] [-v] [-l] [--help-all]

Discover and run dwimsy unit tests in-process (from disk or in-memory bundle payload).

positional arguments:
  patterns       Optional test file patterns or subsystem keywords (e.g. 'core', 'tape', 'convert')

options:
  -h, --help     show this help message and exit
  -V, --version  show program's version number and exit
  -T, --test     Run unit tests in-process (optional pattern filter)
  -v, --verbose  Increase test runner verbosity
  -l, --list     List discovered unit test IDs without running them
  --help-all     Show full help documentation and exit
```

```bash
# Run complete test suite
dwimsy tests

# Run via flag alias
dwimsy --test -v

# List all discovered unit test IDs
dwimsy tests --list

# Scoped testing for a single subsystem keyword or pattern
dwimsy tests convert -v
dwimsy tests meta -v
dwimsy tests integrity -v
```

#### `dwimsy help`

> **Status:** [x] `COMPLETE` (Milestone 1.6)

Displays the interactive technical reference manual for any CLI verb or core subsystem, with automatic paging when connected to an interactive terminal:

```bash
# View deep technical manual for convert
dwimsy help convert

# View complete full manual across all subcommands
dwimsy help --help-all
```

#### `dwimsy readme` & `dwimsy license`

> **Status:** [x] `COMPLETE` (Milestone 1.6)

Outputs the project `README.md` and `LICENSE` files. When run on an interactive terminal, outputs via a terminal pager (`pydoc.pager`); when redirected to a pipe or file, streams plain text without paging.

* **Resolution Precedence**:
  1. *Local Source Checkout*: If running from a source working tree, reads the live on-disk `README.md` / `LICENSE` alongside `dwimsy/`, reflecting local edits immediately without rebuilding.
  2. *Installed System Package / Bundle*: When running from a portable bundle or installed package, reads the canonical text directly from `dwimsy.meta.unbundle.blztar` in memory with zero external file dependencies.

```bash
# Interactive terminal viewer (scroll with arrows, q to exit)
dwimsy readme
dwimsy license

# Stream canonical documentation to stdout or file
dwimsy readme > README.md
dwimsy license > LICENSE
```

#### `dwimsy changelog`

> **Status:** [x] `COMPLETE` (Milestone 1.6)

Inspects project revision history from the canonical `CHANGELOG.md` file (with `blztar` asset fallback in portable bundle mode):

```bash
# View revision history in terminal
dwimsy changelog
```

#### `dwimsy meta` (Maintainer & Repository Lifecycle)

> **Status:** [x] `AVAILABLE` (Milestone 1.6)

Maintainer and packaging tooling is consolidated under `dwimsy meta <command>` to keep the top-level user CLI clean:

```text
$ dwimsy meta --help
usage: dwimsy meta [-h] [-V] [-T] [-v] [--help-all] <meta-command> ...

dwimsy meta - Maintainer tools and repository lifecycle management.

positional arguments:
  <meta-command>
    bundle         Generate a self-extracting single-file Python unpacker
                   bundle of dwimsy.
    unbundle       Extract dwimsy standalone bundle to a target directory.
    diff           Show differences between the working tree and embedded
                   baseline.
    integrity      Verify the canonical portable-project integrity hash.
    fetch-deps     Fetch or materialize legacy reference submodules into
                   deps/.
    version-bump   Advance revision, record changelog, and synchronize bundle
                   baseline.
    lint           Verify repository headers, docstrings, markdown syntax, and
                   dash policy.
    bundle-fixtures
                   [TODO / Milestone 1.6] Package private test fixtures.

options:
  -h, --help       show this help message and exit
  -V, --version    show program's version number and exit
  -T, --test       Run scoped meta self-tests in-process (optional pattern filter)
  -v, --verbose    Increase output verbosity
  --help-all       Show full detailed help for all meta subcommands and exit
```

##### `dwimsy meta bundle`
Generates a standalone, self-extracting single-file Python unpacker script of `dwimsy`, enabling offline propagation to other systems or LLM sessions.

```text
$ dwimsy meta bundle --help
usage: dwimsy meta bundle [-h] [-o OUTPUT] [-t TAG] [--baseline] [--with-deps] [--status] [--diff]

Generate a self-extracting single-file Python unpacker bundle of dwimsy.

options:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        Output script path or '-' for stdout (default: auto-derived)
  -t TAG, --tag TAG     Optional short descriptive tag/label (e.g. 'parser-fix')
  --baseline            Directly emit the installed canonical baseline bundle module
                        (dwimsy/meta/bundle.py) as output without bundling working tree
  --with-deps           Include legacy submodule scaffolding from deps/
  --status              List uncommitted/modified and untracked files before bundling
  --diff                Display working tree diff on stdout before bundling
```

* **Modes of Operation**:
  * `dwimsy meta bundle` (default): Packages the *live* working tree into a self-extracting `.py` script (appending `_mod` if modified).
  * `dwimsy meta bundle --baseline`: Reconstructs the baseline standalone unpacker from the embedded baseline `blztar` payload and its canonical, blztar-elided `unbundle.py` template.

```bash
# Bundle live working tree -> generates dwimsy_0.1.6.69-dev.py
dwimsy meta bundle

# Emit sealed baseline bundle directly
dwimsy meta bundle --baseline -o ./dwimsy_0.1.6.69-dev.py
```

##### `dwimsy meta unbundle`
Extracts a portable bundle to a normal source tree. The `unbundle.py` written to disk is reconstituted from the canonical blztar-elided template stored inside the bundle, with the bundle payload substituted back in. Its timestamp is preserved from that canonical template.

Safe unbundling features:
* **Safe In-Place Upgrades**: Unbundling into an existing clean checkout of an older release in `VersionSpace` performs an in-place version upgrade without requiring `--force`.
* **Rollback Command**: When unbundling changes the on-disk version, a notice prints the exact command to revert to the previous version (`python3 dwimsy/meta/unbundle.py --version=<prev_version> <target_directory>`).
* **Overwrite Protection**: Refuses without `--force` if `dwimsy/meta/unbundle.py` would be overwritten and the incoming bundle payload does not contain the previous on-disk version in its history.
* **Extraction Banner**: On completion, reports the extracted version banner (`Successfully extracted dwimsy <version> (<timestamp> <hash>) to <target_directory>`).

```bash
# Extract the bundle to a directory
dwimsy meta unbundle ./restored

# Include the frozen reference dependencies
dwimsy meta unbundle ./restored --deps

# Revert an upgraded checkout back to a previous version
python3 dwimsy/meta/unbundle.py --version=0.1.6.56-dev .
```


##### Version Retention Policy (3-3-3 Rule)
To balance historical context with bundle size, `dwimsy` maintains a tiered retention policy in the primary stream:
*   **The Tip**: The current working version (HEAD) is always retained.
*   **Latest Patches**: The last **3** sealed versions within the current `major.minor` branch.
*   **Minor Milestones**: The last **3** minor release tips (the latest patch of each minor version).
*   **Major Milestones**: The last **3** major release tips.

##### Semantic Version Selection
The `--version` flag and other version operations support semantic prefix matching:
*   `--version=0.1` matches the latest stable (non-pre-release, non-build) version in the `0.1.x` series.
*   `--version=0.1.6-dev` performs an exact match or matches the latest build of that pre-release.
*   **SemVer Strictness**:
    *   **Bare versions** (e.g., `0.1`, `1.0.0`) will **never** match a pre-release (e.g., `-dev`) or a build (e.g., `+mod`).
    *   To match a pre-release, you must explicitly include the pre-release identifier in your selector (e.g., `--version=0.1-dev`).

##### `dwimsy meta diff`
Shows the canonical project diff between the current working tree and the embedded baseline, or between two specified version targets. The comparison elides the generated `blztar` payload in `unbundle.py`, writes the unified diff to stdout, and does not create a bundle file.

* **Inside a Checkout**: Running `dwimsy meta diff` without arguments compares the bundle's baseline against the unbundled on-disk working tree.
* **Outside a Checkout**: Running without arguments raises a version resolution error because `unbundled` is undefined outside checkouts. To compare an unbundled directory with the bundle version from anywhere, use `--version-include-primary=. --version=alt` or specify explicit version tags.
* **Hermetic Multi-Version Diffs**: Running `dwimsy meta diff [VER1] [VER2]` compares any two versions or streams from `VersionSpace` hermetically without requiring an on-disk checkout.

```bash
# Diff working tree against embedded baseline (from inside a checkout)
dwimsy meta diff

# Diff two historical versions hermetically
dwimsy meta diff 0.1.6.55-dev 0.1.6.56-dev

# Compare on-disk checkout against bundle baseline from an external directory
python3 dwimsy_0.1.6.69-dev.py --version-include-primary=. dwimsy meta diff baseline alt
```

##### `dwimsy meta integrity`
Verifies the canonical portable-project SHA-256 hash against `_version.py`, reporting clean status or the PEP 440 local version identifier (`+mod.<short_hash>`). The integrity window includes `dwimsy/**/*.py`, `tests/**/*.py`, `tests/**/*.md`, `README.md`, `LICENSE`, `CHANGELOG.md`, `.gitignore`, `.gitmodules`, and one lazy recursive glob for each `.gitmodules` entry. `dwimsy/meta/unbundle.py` is included with its generated `blztar` payload elided before hashing.

```bash
# Verify the current working tree
dwimsy meta integrity

# Verify the embedded baseline project
dwimsy meta integrity --baseline
```

##### `dwimsy meta version-bump`

> **Status:** [x] `COMPLETE` (Milestone 1.6)

Atomically advances the package revision, updates `dwimsy/_version.py` and `README.md`, logs an entry to `CHANGELOG.md`, builds a fresh standalone bundle, and synchronizes `dwimsy/meta/unbundle.py`:

```bash
# Increment patch component and synchronize baseline
dwimsy meta version-bump --patch -m "Implement CLI architecture and doc viewers"

# Explicit version bump
dwimsy meta version-bump 0.1.6.1-dev
```

##### `dwimsy meta fetch-deps`
Clones all required legacy submodules in non-Git or bundled checkouts by parsing `.gitmodules` (from disk or `blztar`):

```text
$ dwimsy meta fetch-deps --help
usage: dwimsy meta fetch-deps [-h] [--baseline] [-f]

options:
  -h, --help   show this help message and exit
  --baseline   Extract frozen reference submodules directly from the bundled
               baseline payload without network access
  -f, --force  Overwrite existing deps/ directory if present
```

##### `dwimsy meta lint`

> **Status:** [x] `COMPLETE` (Milestone 1.6)

Validates all repository hygiene invariants: pure ASCII Python source, strict hyphen-minus dash policy, no &apos;&apos;&apos; triple single-quotes, and no inline LaTeX math in Markdown files:

```bash
dwimsy meta lint
```

##### `dwimsy meta bundle-fixtures` *(planned; not currently implemented)*

> **Status:** [ ] `TODO` (Milestone 1.6)

Packages locally present private test fixtures into a self-extracting unpacker script.

### Standalone Filter Applets

The `convert` verb's PC-88 logic is also directly reachable as two independent, Netpbm-style single-purpose filters - matching the architecture's `cli.filters.*` design goal, and useful for shell pipelines that don't need the unified verb's format auto-detection.

#### `dwimsy-wav2t88` (`dwimsy/cli/filters/wav2t88.py`)

> **Status:** [x] `COMPLETE` (Milestone 1; option harmonization [ ] `IN PROGRESS` in Milestone 1.6)

```text
$ python3 dwimsy/cli/filters/wav2t88.py --help
usage: dwimsy-wav2t88 [-h] [-V] [--baud {600,1200}]
                      [--channel {auto,left,right,mix,diff}] [--bauds BAUDS]
                      [--flavor {verbatim,reconstructed,kinematic-infilled,rom-authentic,canonical}]
                      [--confidence CONFIDENCE] [-q] [-T]
                      [input] [output]

Stream PC-8001 / PC-8801 WAV audio to standard .t88 tape image.

positional arguments:
  input                 Input WAV file or '-' for stdin
  output                Output .t88 file or '-' for stdout

options:
  -h, --help            show this help message and exit
  -V, --version         show program's version number and exit
  --baud {600,1200}, -b {600,1200}
                        Forced baud rate
  --channel {auto,left,right,mix,diff}, -c {auto,left,right,mix,diff}
                        Input channel
  --bauds BAUDS         Candidate baud rates
  --flavor {verbatim,reconstructed,kinematic-infilled,rom-authentic,canonical}
                        Timing flavor
  --confidence CONFIDENCE, -C CONFIDENCE, --min-confidence CONFIDENCE
                        Minimum confidence threshold
  -q, --quiet           Suppress logging
  -T, --test            Run filter self-tests in-process and exit
```

```bash
python3 dwimsy/cli/filters/wav2t88.py capture.wav game.t88 --baud 600
```

#### `dwimsy-t882wav` (`dwimsy/cli/filters/t882wav.py`)

> **Status:** [x] `COMPLETE` (Milestone 1; option harmonization [ ] `IN PROGRESS` in Milestone 1.6)

```text
$ python3 dwimsy/cli/filters/t882wav.py --help
usage: dwimsy-t882wav [-h] [-V]
                      [--mode {tape,cassette,acoustic,motor,spinup,shaped,pc,ideal,square}]
                      [--sample-rate SAMPLE_RATE] [--channels {1,2}]
                      [--stereo-mode {dual,left,right,diff}]
                      [--amplitude AMPLITUDE] [--baud {600,1200}]
                      [--speed SPEED] [--invert] [-q] [-T]
                      [input] [output]

Stream PC-8001 / PC-8801 .t88 tape container image to standard WAV audio.

positional arguments:
  input                 Input .t88 file or '-' for stdin
  output                Output .wav file or '-' for stdout

options:
  -h, --help            show this help message and exit
  -V, --version         show program's version number and exit
  --mode {tape,cassette,acoustic,motor,spinup,shaped,pc,ideal,square}, -m {tape,cassette,acoustic,motor,spinup,shaped,pc,ideal,square}, --wave {tape,cassette,acoustic,motor,spinup,shaped,pc,ideal,square}
                        Synthesis mode
  --sample-rate SAMPLE_RATE, -r SAMPLE_RATE
                        Audio sample rate (default: 44100)
  --channels {1,2}, -c {1,2}
                        Channels: 1 (mono) or 2 (stereo)
  --stereo-mode {dual,left,right,diff}
                        Stereo routing
  --amplitude AMPLITUDE, -a AMPLITUDE, --volume AMPLITUDE, -v AMPLITUDE
                        Peak amplitude 0.01..1.0
  --baud {600,1200}     Baud override
  --speed SPEED, -s SPEED
                        Speed multiplier
  --invert              Invert polarity
  -q, --quiet           Suppress progress
  -T, --test            Run filter self-tests in-process and exit

Note: --mode accepts tape, acoustic, shaped, ideal, cassette, motor, spinup,
pc, square.
```

### Developer Workflow

To maintain absolute synchronization between the source checkout and the portable self-extracting bundle, development follows a strict circularity-breaking verification loop:

1. **Make changes** to the source tree in `dwimsy/`, `tests/`, or project metadata.
2. **Run tests & lints** locally:
   ```bash
   dwimsy tests
   dwimsy meta lint
   ```
3. **Advance revision & synchronize baseline**:
   ```bash
   dwimsy meta version-bump
   ```
   This automatically updates `dwimsy/_version.py`, `README.md`, logs an entry to `CHANGELOG.md`, builds a fresh standalone bundle, and refreshes the embedded payload in `dwimsy/meta/unbundle.py`.
4. **Verify clean canonical baseline diff**:
   ```bash
   dwimsy meta diff
   ```
   *Invariant Rule:* `dwimsy meta diff` must produce zero lines of stdout and exit with return code `0`.
5. **Run final test verification**:
   ```bash
   dwimsy tests -v
   ```
6. **Deliver**: Commit or distribute the verified bundle alongside modified source files.

> [!WARNING]
> **Do not manually edit `blztar` in `unbundle.py`**: The `blztar` assignment inside `dwimsy/meta/unbundle.py` is an automatically generated asset stream. Modifying it by hand corrupts the archive stream or breaks canonical integrity hashing. Always use `dwimsy meta bundle` or `dwimsy meta version-bump` to refresh the baseline.

### Environment Variables

`dwimsy` recognizes a concise set of standard environment variables:

| Environment Variable | Target Subsystem | Default | Description |
|:---|:---|:---|:---|
| `DWIMSY_BUNDLE_BUILD` | Meta & Test Engine | `None` / `0` | When set to `1`, signals in-process bundle self-testing and suppresses on-disk subprocess invocations that require extracted filesystem packages. |
| `DWIMSY_TEST_FIXTURES` | Test Fixture Pool | `tests/fixtures` | Explicit filesystem path override for local private fixture repositories and real tape captures. |
| `DWIMSY_TEST_REPO_ROOT` | Integrity & Runner | `None` (Auto) | Explicit repository root path override used during ephemeral temporary directory test execution. |

### Character & Syntax Considerations

To ensure cross-platform terminal compatibility, clean diff tracking, and seamless script-driven automated patching:

1. **Pure ASCII Source Code**: All Python source files outside `deps/` are strictly 100% pure ASCII.
2. **Hyphen-Minus Dash Policy**: All non-`deps/` files (`.py`, `.md`, `.txt`) strictly use ASCII hyphen-minus `-` (`0x2D`). Unicode em dashes (&mdash; `U+2014`) and en dashes (&ndash; `U+2013`) are forbidden.
3. **Reserved Syntax for Meta-Coding**: Triple single quotes (&apos;&apos;&apos;) are strictly forbidden in all non-`deps/` Python and Markdown files. All docstrings and multi-line strings must use double-quote delimiters (`"""` or `r"""`). This reserves &apos;&apos;&apos; as guaranteed collision-free wrapper syntax for meta-programming and automated code generation tools.
4. **Standard GFM Markdown Math**: Markdown files use literal Unicode symbols (e.g. `≈`, `µs`, `→`, `~`) and backtick code spans; raw inline LaTeX delimiters (&dollar;...&dollar;) and LaTeX commands (&bsol;approx, &bsol;text, &bsol;frac) are forbidden to ensure clean rendering on standard GitHub and terminal Markdown parsers.

## 4. Existing Project Lineage & Asset Repositories

`dwimsy` integrates and unifies code, tables, and DSP algorithms from several existing repositories:

* [`f-fix/pc88_tape_tools`](https://github.com/f-fix/pc88_tape_tools): NEC PC-8001 / PC-8801 `.t88` container state machines, `.cmt` stream extraction, and `t882wav` / `wav2t88` streaming FSK audio converters.
* [`f-fix/wav2cas`](https://github.com/f-fix/wav2cas): MSX FSK demodulation (`wav2cas`), audio synthesis (`cas2wav`), streaming FLAC decoding (`flac2wav`), analog signal conditioning (`cmt_filter`), and physical cassette channel simulation (`cassette_modeler`).
* [`f-fix/fat8_d88_tool`](https://github.com/f-fix/fat8_d88_tool): NEC PC-8801 / PC-8001 / PC-98 / PC-6001 / Pasopia D88 floppy disk container parsing, FAT8 filesystem extraction/injection, JIS X 0201 / NEC / PC-6001 semigraphics character transcoding filters, N88-BASIC / PC-88 obfuscation engines, and deterministic OS filename sanitization.
* [`f-fix/nontama_to_bload`](https://github.com/f-fix/nontama_to_bload): PC-6001mkII NONTAMA loader and MSX "M"-loader unpackers, PC-6001 and MSX Japanese character mappings, and `mkrom` cartridge builder.
* [`f-fix/cas2uef`](https://github.com/f-fix/cas2uef): MSX `.cas` to BBC Micro Model B `.uef` timing container converter.
* [`f-fix/bin2fds`](https://github.com/f-fix/bin2fds): Raw binary to Nintendo Famicom Disk System / Mitsumi Quick Disk `.fds` image generator.

---

## 5. Component Implementation Status Matrix

| Subsystem / Module | Description | Status | Target Milestone |
| :--- | :--- | :---: | :---: |
| **`core.pulse`** | Edge timing, zero-crossing, time-base correction (TBC), dynamic glitch rejection, AGC - tuned first against PC-88/PC-8801's 2400/1200 Hz FSK | `[x] DONE` | Milestone 1 |
| **`core.audio`** | Streaming WAV reader/writer (strict `data` chunk boundary clamping ships in M1.7; FLAC in M2.1) | `[x] DONE` | Milestone 1 |
| **`core.fsk`** | FSK pulse classifier & UART framing with unified drift tracking | `[x] DONE` | Milestone 1 |
| **`cli.filters.*`** | `t882wav` and `wav2t88` streaming filters, backed by `dwimsy.core.*` | `[x] DONE` | Milestone 1 |
| **`tape.t88`** | T88 container reader/writer (`T88File`, `T88Block`, `DataSubHeader`, lead-in/gap synthesis, split/join) | `[x] DONE` | Milestone 1.5 |
| **`protocols.pc88`** | PC-88 ROM protocol state machine: BASIC (0xD3), MON (0x24/0x3A), ASCII (0x9C), NONTAMA (0xFF), MON O/I | `[x] DONE` | Milestone 1.5 |
| **`cli.split_join`** | PC-88 tape splitting (`dwimsy split`) and concatenation (`dwimsy join`) | `[x] DONE` | Milestone 1.5 |
| **`cli.inspect` (deep)** | Full acoustic audio inspection (energy, cycles, speed drift) & deep structural ROM/T88 report | `[x] DONE` | Milestone 1.5 |
| **`meta.integrity`** | Canonical portable-project hashing, baseline checks, `unbundle.py` payload elision & runtime mod-detection | `[x] DONE` | Milestone 1.6 |
| **`meta.bundle`**    | Single-file unpacker generator, baseline reconstruction, `blztar` storage & diff support | `[x] DONE` | Milestone 1.6 |
| **`meta.unbundle`**  | Portable bundle extractor, canonical self reconstruction and in-memory asset provider | `[x] DONE` | Milestone 1.6 |
| **`meta.bundle_fixtures`**| Content-addressed test fixture packager (`dwimsy meta bundle-fixtures`) | `[ ] TODO` | Milestone 1.6 |
| **`meta.version_bump`**| `dwimsy meta version-bump` (advances revision, seals code-hash, updates `CHANGELOG.md`) | `[x] DONE` | Milestone 1.6 |
| **`meta.diff`**     | Canonical working-tree vs embedded-baseline diff | `[x] DONE` | Milestone 1.6 |
| **`meta.fetch_deps`**| `dwimsy meta fetch-deps` (materializes `.gitmodules` dependencies in non-git checkouts) | `[x] DONE` | Milestone 1.6 |
| **`cli.changelog`**  | `dwimsy changelog` (interactive revision history viewer reading `CHANGELOG.md`) | `[x] DONE` | Milestone 1.6 |
| **`cli.doc_viewers`**| `dwimsy readme` & `dwimsy license` (on-disk precedence with `blztar` fallback) | `[x] DONE` | Milestone 1.6 |
| **`cli.help`**       | `dwimsy help [verb\|topic]` (interactive pydoc technical manual viewer) | `[x] DONE` | Milestone 1.6 |
| **`tests.fixtures`** | Content-addressed fixture registry (`FixtureSpec`) and discovery pool (`FixturePool`) | `[x] DONE` | Milestone 1.6 |
| **`tests.runner`**   | `dwimsy tests` CLI test suite runner with keyword and subsystem filtering | `[x] DONE` | Milestone 1.6 |
| **`packaging`**      | Standard `pyproject.toml` with clean console script entry points | `[ ] TODO` | Milestone 1.6 |
| **`protocols.pc88` (hardened)**| Strict grammar state machine, full MON address/payload checksums, and `[truncated]` emission | `[ ] TODO` | Milestone 1.7 |
| **`tape.t88` (hardened)**| Strict T88 block length verification and canonical 24-byte signature checking | `[ ] TODO` | Milestone 1.7 |
| **`core.audio` (hardened)**| Strict WAV `data` chunk boundary clamping (ignoring trailing RIFF metadata chunks) | `[ ] TODO` | Milestone 1.7 |
| **`deps.pc88_tape_tools`**| Permanent ejection of `deps/pc88_tape_tools` submodule scaffolding | `[ ] TODO` | Milestone 1.7 |
| **`dsp.filter`** | Analog filter/wave-shaper & differentiator (`cmt_filter`, ported with MSX support) | `[ ] TODO` | Milestone 2.1 |
| **`dsp.modeler`** | Magnetic tape channel simulator (`cassette_modeler`, ported with MSX support) | `[ ] TODO` | Milestone 2.1 |
| **`tape.cas`** | MSX `.cas` reader/writer (8-byte padded & compact unpadded flavors) | `[ ] TODO` | Milestone 2.1 |
| **`protocols.msx`** | MSX BIOS cassette protocol state machine (`1F A6` sync tokens) | `[ ] TODO` | Milestone 2.1 |
| **`deps.wav2cas`** | Permanent ejection of `deps/wav2cas` submodule scaffolding | `[ ] TODO` | Milestone 2.1 |
| **`tape.tsx`** | MSX `.tsx` container (TZX Block 0x4B KCS FSK & Block 0x11 Turbo) | `[ ] TODO` | Milestone 2.2 |
| **`disk.d88`** | D88 sector container reader & writer | `[ ] TODO` | Milestone 2.3 |
| **`disk.fat8`** | FAT8 filesystem parser & injector | `[ ] TODO` | Milestone 2.3 |
| **`disk.fds`** | FDS / QuickDisk container engine (`bin2fds` Python 3 port) | `[ ] TODO` | Milestone 2.3 |
| **`core.charsets`** | Unicode ↔ JIS X 0201 / NEC / MSX / KOI-7 streaming transcoder | `[ ] TODO` | Milestone 2.3 |
| **`deps.fat8_d88_tool`**| Permanent ejection of `deps/fat8_d88_tool` & `deps/bin2fds` submodules | `[ ] TODO` | Milestone 2.3 |
| **`platforms.unpack`** | NONTAMA & MSX M-Loader binary unpackers (`mkrom`) | `[ ] TODO` | Milestone 2.4 |
| **`platforms.cart_hooks`**| ROM cartridge tape containers, BIOS hook extractors & `cas2rom` packagers | `[ ] TODO` | Milestone 2.4 |
| **`deps.nontama_to_bload`**| Permanent ejection of `deps/nontama_to_bload` submodule scaffolding | `[ ] TODO` | Milestone 2.4 |
| **`core.realtime`** | Live-stage contracts, bounded buffering/latency accounting, clocks, backpressure and resynchronization | `[ ] TODO` | Milestone 2.5 |
| **`cli.sidechannel`** | `stderr` virtual LCD, TTY keystrokes & POSIX/Win32 signal dispatcher | `[ ] TODO` | Milestone 2.5 |
| **`ui.remote`** | IPC control daemon (Unix socket / Named Pipe / WebSocket) for web/phone UI | `[ ] TODO` | Milestone 2.5 |
| **`core.fs`** | Filename sanitizer & `link_or_copy` hardlinker/copier | `[ ] TODO` | Milestone 2.5 |
| **`core.transport`** | Transport automation engine: Tier 1 manual, Tier 2 relay, Tier 3 solenoid logic | `[ ] TODO` | Milestone 2.5 |
| **`transport.changer`**| Media changer, auto-naming, blank media generator & jukebox policies | `[ ] TODO` | Milestone 2.5 |
| **`transport.browser`**| LCD 2-line virtual image root browser with type-to-navigate & context tracking | `[ ] TODO` | Milestone 2.5 |
| **`transport.seeker`** | Content-aware smart seek (file/block/marker navigation & cueing) | `[ ] TODO` | Milestone 2.5 |
| **`dsp.router`** | Dynamic mode & modulation router (pilot sniff, auto-turbo switch) | `[ ] TODO` | Milestone 2.5 |
| **`metadata.archive`** | Archival bundle exporter & `README.md` generator | `[ ] TODO` | Milestone 2.5 |
| **`tape.variants`** | Multi-flavor generator (Trimmed/Untrimmed, CAS unpadded, P6/P6T pairs) | `[ ] TODO` | Milestone 2.5 |
| **`tape.geometry`** | Physical cassette shell profiling (C-10..C-90, custom lengths, hub math) | `[ ] TODO` | Milestone 2.5 |

## 6. Representation Layers, Real-Time Planes & Hardware Gateway

A codec operates on a representation stream and declares its real-time properties independently of whether its endpoint is a file, pipe, emulator, or physical deck.

```text
┌────────────────────────────────────────────────────────┐
│ Layer 4: Semantic File & Payload Layer        [ ] TODO │
│   • Executable Binaries (BLOAD, Load/Exec RAM images)  │
│   • Detokenized Plaintext Source (N-BASIC, MSX, FOCAL) │
│   • Unicode Charsets (JIS X 0201, NEC, MSX, KOI-7)     │
├──────────────────────────⇕─────────────────────────────┤
│ Layer 3: Filesystem & Protocol Layer          [ ] TODO │
│   • Sector FS: FAT8, FAT12, CP/M, Coleco DDP           │
│   • Unified Headers: Sharp MZ 128-byte (Tape/QD/Disk)  │
│   • Stream Protocols: PC-88 (D3/24/9C), MSX (1F A6)    │
│   • Custom Loaders: NONTAMA, Speedlock, PWM Turbo      │
├──────────────────────────⇕─────────────────────────────┤
│ Layer 2: Physical Timing & Sector Containers  [ ] TODO │
│   • Tape Containers: .t88, .tsx, .p6t, .uef, .cdt, .tzx│
│   • Floppy Images  : .d88, .dsk (MSX sectors == CMT)   │
│   • Spiral Disks   : .fds, .qd, .qdf                   │
│   • ROM Cartridges : .rom, .crt (MSX AB, C64, cas2rom) │
├──────────────────────────⇕─────────────────────────────┤
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
  Provenance / Preservation   raw prepared copys, derivatives, hashes, epistemic tags
  Live I/O                    bounded-latency streaming between endpoints
```

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
 (Host / Emu) ◄───┼─► Parallel / Serial / IEC / Solenoid Engine ◄─┼───► (Deck/Drive)
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

#### 1. Runtime Media Changes, Jukebox Policies & Composite Sets (transport.changer)
Media swaps occur both via external triggers (user hotkey, phone UI, physical button) and through automated **inference engines**:
* **Manual / Out-of-Band Triggers**: Hot-swapping virtual disks or flipping tape sides (`[` / `]` keys) without resetting the running audio/flux stream or dropping connection to the retrocomputer.
* **Automated Sequential Advance**:
  - **Auto-Flip**: Detects optical leader / end-of-tape (EOT) silence or post-data motor stop and automatically queues Side B.
  - **Multi-Tape / Multi-Disk Carousel**: Automatically traverses multi-tape sets (`Tape 1 Side A` → `Side B` → `Tape 2 Side A` → `Side B` → `...` → loop back to `Tape 1 Side A`).
  - **Composite Side Carousel Sequence**: For multi-tape sets with publisher composite side designations (e.g. *Tomato Hime*), sequences in exact physical order: `Side 1A` → `Side 1B` → `Side 2A` → `Side 2B`.
* **Hardware Bus Synthesis**: During an automated or manual disk change, `dwimsy` asserts `/DISK_CHANGE` (pin 34) and pulses `/INDEX` / `/READY` to signal the retrocomputer BIOS that media has been swapped.

#### 2. Virtual Image Root & 2-Line Status LCD File Browser (transport.browser)
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
* **SHA1-Indexed Persistent Overlays**: In non-ephemeral mode, write overlays are stored out-of-band under `~/.cache/dwimsy/overlays/<SHA1>/`, indexed by the source tape SHA-1 hash. Selecting an image with an existing overlay presents an instant choice: `[1] Use Overlay`, `[2] Clean Master`, `[3] Delete Overlay`. Pressing `<D>` in TTY mode discards the active overlay.
* **Pipeline / Filter Default**: Standalone filter applets and piped stream conversions default to cold, read-only mode. If a matching overlay is found in cache, `dwimsy` displays an informational notice on `stderr` explaining the `--overlay` activation flag.
* **Deterministic Verification (`--no-overlay`)**: Explicitly bypasses overlay reading for reproducible verification and testing.

#### 4. Automated Physical Side/Tape Slicing & Leader Detection (--multi-side)
When digitizing continuous captures containing multiple cassette sides or tapes:
* **Spectrographic Leader & Hiss Profiling**: Identifies non-magnetic clear leader tape and transport stops via a 15-25 dB step-change dropping from magnetic bias hiss (E_bias ≈ −50 dBFS) to electronic preamp floor (E_floor ≤ −75 dBFS).
* **Validated Lifecycle Interlock**: Only commits a side split when the audio region satisfies a complete tape lifecycle (Leader In → Valid Program/Audio Payload → Leader Out).
* **Default Carousel Sequencing**: Automatically assigns sequential layout (`Tape 01 Side A` → `Side B` → `Tape 02 Side A` → `Side B`) unless overridden by user metadata.

#### 5. Loading Groups & Multi-Block Chaining (transport.seeker)
To prevent tedious manual keystrokes during multi-block loading on systems without motor control (e.g. Sinclair ZX Spectrum games like *R-Type* or *Bubble Bobble*, Speedlock protection schemes, MSX multi-loaders, or PC-6001 NONTAMA stages):
* **Three-Level Structural Hierarchy**:
  1. *Block / Record (Layer 2)*: Atomic physical data frame (TZX block, 19-byte Spectrum header, MSX 16-byte chunk, PC-88 `: [addr]` record).
  2. *Loading Group / Load Group (Layer 3)*: Contiguous sequence of blocks streamed in one continuous, uninterrupted pass by the computer's active loader without stopping the tape.
  3. *Segment (Timeline / Mixed-Mode)*: Chronological macro-region on a composite mixed-mode tape (e.g. *Gundam 2* `Segment 01` [Data] ↔ `Segment 02` [Audio Drama]).
* **Automated Group Boundary Detection**:
  - *TZX / TSX / CDT Metadata*: Evaluates block pause values. Non-zero pauses stream automatically; zero-pause blocks (Block `0x20` Stop the Tape / Block `0x2A` Stop in 48K) or TZX Group markers (`0x21`/`0x22`) seal the Loading Group and engage transport auto-pause.
  - *Audio Cadence*: Inter-block gaps < 2.0s maintain continuous streaming; silence drops ≥ 3.0s-5.0s trigger stage auto-pause.
  - *Loader Protocol Signatures*: Recognizes linked loader patterns (Speedlock, NONTAMA, PC-88 CSAVE → MON chains) and groups them automatically.

#### 6. Runtime Conversion Mode & Modulation Switching (dsp.router)
Mode switching operates across two distinct dynamics:
* **User-Driven Real-Time A/B Testing**: The operator toggles output modes on-the-fly (`Raw Passthrough` ↔ `Conditioned Filter` ↔ `Canonical Ideal` ↔ `Cassette Hardware Model`) while listening to the real hardware to diagnose edge-case demodulation issues.
* **Inferred / Sniffed In-Stream Modulation Switching**:
  - **Hybrid Speed Loaders**: Software often begins with a standard ROM BIOS FSK header (1200 baud) and switches mid-stream to high-speed custom PWM or Turbo tones (e.g. 3600+ baud). `dwimsy` continuously monitors pilot frequencies and dynamically hot-switches demodulators mid-stream with zero dropped samples.
  - **Adaptive DSP Fallback**: If signal SNR or carrier eye pattern degrades below a confidence threshold, the router dynamically engages secondary phase equalization or alternate slicer hysteresis.

#### 7. Multi-Platform Compilation Splitting & Multi-File Container Packaging (tape.multiplex)
For compilation tapes containing programs for multiple target systems and spoken human narration (such as ASCII's *Tape Login* and *Tank Battle* series, or multi-part releases like *Gundam 2* and *Tomato Hime*):
* **Hard Program Fencing**: Intervening human speech/commentary tracks or extended leader silences (>5s) act as hard program boundaries, preventing unrelated titles from merging.
* **Chained Multi-File Container Integrity**: Multi-part programs (e.g., PC-88 tokenized BASIC loader → machine-language engine → graphics/map data; MSX multi-block loads; PC-6001 BASIC → NONTAMA payload) are preserved together inside a single, unified, bootable emulator container image (`.t88`, `.cas`, `.p6t`, `.t77`, `.mzt`, `.tap`, `.cdt`, `.tzx`). This ensures emulators load all subsequent stages automatically without hanging on missing sub-files.
* **Dissected Payload Extraction**: In addition to the bootable multi-file container, individual sub-files (`.cmt`, `.bin`, detokenized `.bas`) are unpacked into a `subfiles/` directory for developer inspection.

#### 8. Three-Tier Ambiguity Resolution Strategy
Generic extensions like `.cmt` (used by PC-88, PC-6001, MSX, FM-7), `.cas` (used by MSX, Sega SC-3000, Sord M5, Casio, CoCo), `.mzt` (Sharp MZ single/multi-file dumps vs QD BSD images), and `.wav` are resolved through a deterministic hierarchy:
1. **Tier 1: Explicit Namespaced Filter Applets**: Direct invocation of single-purpose Unix filters (`dwimsy-msx-wav2cas`, `dwimsy-sega-wav2cas`, `dwimsy-sord-wav2cas`, `dwimsy-wav2t88`, `dwimsy-t882wav`) establishes unambiguous platform context.
2. **Tier 2: Explicit Profile Switches**: High-level commands accept `--profile=` overrides (`--profile=pc88`, `--profile=msx`, `--profile=sega-sc3000`, `--profile=sord-m5`, `--profile=pc6001`, `--profile=fm7`, `--profile=mz700`, `--profile=mz2000`, `--profile=x1`, `--profile=cpc`, `--profile=spectrum`, `--profile=famicom-basic`).
3. **Tier 3: In-Stream Layer 3 Protocol Sniffing**: If no profile is specified, `dwimsy` parses the demodulated stream through parallel platform recognizers (checking for MSX `1F A6` sync tokens, PC-88 `0xD3`/`0x24`/`0x9C` preambles, PC-6001 mode descriptors, Sharp 128B directory blocks, Sharp X1 `.tap` headers, Family BASIC headers, Sega "SEGA CASSETTE", Sord `0x55`+`HEADER`, or FM-7/FM-8 headers).

#### 9. Content-Aware "Smart Seek" (Intelligent Fast-Forward & Rewind) (transport.seeker)
Instead of blind time-based skipping, `dwimsy` provides structure-aware transport navigation:
* **Named File & Header Seeking**: Seek directly to a named file (e.g., `seek --file "STAGE2.BIN"` or `seek --type BASIC`).
* **Loading Group Navigation**: Step forward or backward by entire loading groups (`seek --next-group`, `seek --prev-group`).
* **Block & Record Navigation**: Step forward or backward by logical data blocks (`seek --next-block`, `seek --prev-block`).
* **Semantic Marker Seeking**: Instantly cue to narration cue points, audio drama segments, or user cable swap prompts.
* **Calibrated Tape Counter Seek**: Navigates using physical reel rotation models (`seek --counter "0450"`), translating between tape ticks and elapsed source FLAC time.
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

### ROM Cartridges as Tape Containers & BIOS Hook Injections (platforms.cart_hooks)

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

### Physical Cassette Shell Profiling & Nominal Whole-Tape Geometry (tape.geometry)

In vintage software distribution, software was duplicated onto standard or custom physical cassette shells (e.g., a 3-minute program released on a C-10 or C-15 cassette, with the remainder of Side A and the entirety of Side B left unrecorded). When synthesizing audio from logical streams or timing containers (e.g., `.t88`/`.cas`/`.cmt` → `.wav`), `dwimsy` allows declaring **nominal whole-tape geometry**:

* **Standard & Custom Shell Presets**: Supports standard tape lengths (`C-10`, `C-15`, `C-20`, `C-30`, `C-46`, `C-60`, `C-90`, `C-120`) and custom publisher-cut runtimes (e.g., `--tape-length 8.5m` or `--side-duration 4m15s`).
* **Realistic Lead-in & Trailing Infill**: Positions program data after standard non-magnetic clear leader tape and initial magnetic lead-in silence (e.g. 5-10s), then pads trailing tape with realistic modeled analog tape silence / residual bias noise up to the full nominal side length.
* **Side B Infill & Unrecorded Replication**: Optionally produces a structurally matched, unrecorded or blank Side B waveform to mirror the complete physical retail artifact.
* **Reel Hub Physics & Counter Calibration**: Uses tape thickness models (e.g., standard 18 µm for C-60 vs. 12 µm for C-90) and hub diameter (r₀ ≈ 11 mm) to calculate non-linear reel rotational speeds, giving a modeled tape-position estimate (N_counter) across fast-forward and rewind operations; accuracy depends on measured or declared tape/deck parameters and should be treated as an estimate unless independently calibrated.

### Preservation Dimensions, Epistemic Tags & Non-Destructive Write Overlays

#### Five Preservation Dimensions
1. **Artifact Preservation**: Physical scans, packaging, cassette shells, manuals, labels, and other physical-object documentation.
2. **Signal Preservation**: Raw observed signals (for example, lossless FLAC captures from a tape deck or raw flux captures from a disk device). The original capture is a preservation anchor and is never replaced by a cleaned, time-corrected, canonical, or synthetic derivative.
3. **Information Preservation**: Recovered verified blocks, sectors, filesystems, BASIC code, and other decoded information, with uncertainty retained where recovery is incomplete.
4. **Behavioral / Semantic Preservation**: Execution flow, narration/data interleaving, cable connect/disconnect prompts, motor pauses, save/record behavior, and other evidence about how the software and media were intended to interact.
5. **Canonical / Synthetic Derivatives**: Reconstructed idealized media for emulation, comparison, deterministic regeneration, or re-preparation. These are explicitly derived artifacts, not substitutes for the source capture.

#### Epistemic Classification
Every decoded structure or derived claim carries an epistemic tag: `established` (standard/ROM verified), `observed` (empirically seen on real media), `inferred` (working hypothesis), `heuristic` (algorithmic best-fit), or `synthetic` (generated/normalized). These tags describe the status of the *claim*, not merely the file format. Provenance should identify the source evidence and transformation that produced each derivative where practical.

#### Non-Destructive Write Overlays & Media Writable Tracking
Media is tagged as read-only or writable (tracking physical write-protect notches/tabs):
* When writes occur (e.g., in-game saves or `CSAVE`), they **never overwrite the source capture**.
* Writes are recorded as **time-indexed or tape-counter-indexed write overlays** with exact start/end offsets (T_start, T_end).
* When rewinding, subsequent reads seamlessly draw from the overlay for modified regions and from the original source capture elsewhere.
* The UI surfaces the names and types of written overlay files in real time (e.g., `[OVERLAY @ 04:12-05:30: 'SAVED.BAS' (BASIC)]`).

---

## 7. Evidence, Models, and Preservation Status

`dwimsy` is intended to be useful for preservation without overstating what has actually been established. Technical facts, empirical observations, inferred structure, heuristics, and generated material should remain distinguishable.

### Status of Technical Claims

Where practical, documentation and manifests should identify one or more of:
* **established** - supported by a published format specification, ROM/disassembly evidence, service documentation, or independently verified implementation;
* **observed** - directly observed in a physical capture, hardware test, or reproducible experiment;
* **inferred** - a reasoned interpretation supported by available evidence but not yet independently established;
* **heuristic** - an algorithmic guess or best-fit result whose correctness depends on assumptions;
* **synthetic** - generated by dwimsy rather than observed on the source media.

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

### Deliberate Algorithmic Deviations from the Ported Reference Tools

`core.pulse` and `core.fsk` are ports of `pc88_tape_tools`/`wav2t88`/`t882wav`'s demodulation logic, and are held to a high bar: any behavioral difference from those reference tools needs to be either a bug, or a deliberate, justified, and documented improvement - not an incidental side effect of refactoring. Four differences were evaluated against that bar and kept:

* **Sub-sample interpolation always uses the true previous sample.** The original code skipped updating its zero-crossing reference value on the specific sample where a full cycle completed, meaning the *following* transition's interpolated timing could read a stale value from two samples back rather than one. There's no signal-processing reason to prefer the stale value; this was corrected.
* **The Space-tone classification ceiling now scales with measured tape speed drift**, the same way the Mark-tone boundary already did. Mark and Space tones share a common tape-transport clock, so real motor speed variation shifts both proportionally - the original only adapted the Mark side, which could misclassify genuine (correspondingly slow) Space cycles as gaps on a sufficiently slow-running deck.
* **The UART start-bit threshold's `1200.0 Hz` literal is now the configured `space_freq` parameter**, removing a hardcoded assumption in an otherwise-parameterized module.
* **The glitch-rejection window is derived from the configured `center_freq`/`bandwidth` (`max(20µs, 0.25 / max_f)`)** rather than a fixed 100 microseconds. This is a necessary physical correction for multi-baud systems: in MSX's 2400-baud fast mode (which uses 4800 Hz Mark tones), a valid half-cycle is nominally ~104.17 µs, and drops to ~99.2 µs under legitimate +5% motor speed drift. A rigid 100 µs filter would reject valid fast-mode data cycles as noise glitches. The adaptive formula scales cleanly across tone frequencies while rejecting transient electrical spikes.

All four were verified the same way: running `dwimsy convert` against real, hash-fingerprinted 1980s cassette captures and diffing the resulting `.t88` container **byte-for-byte** against the actual, current, unmodified `wav2t88.py` reference tool on the same input. All four are active simultaneously in that comparison, and the result still matches exactly - meaning none of them changes any classification decision on real, measurably-drifting tape audio, while all four close a real gap for tone frequencies or drift conditions the two available real captures don't happen to exercise.

### Mixed-Mode Media

A physical tape may contain materially different signal types in one continuous recording: for example, computer-modulated CMT data interspersed with narration or music. `dwimsy` should preserve the continuous source capture and represent the interpretation as a chronological segment timeline. Each segment can then have an appropriate derivative:

```text
source FLAC
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

## 8. Systematic Flavor Taxonomy & No-Intro Naming

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
* **Multi-Take / Dump Collapsing**: When multiple audio takes or dumps exist (`tape01`, `copy01`), the verified source dump collapses to the unnumbered base name (`door_door.flac`).
* **Multi-Part / Sequential Media**: For multi-tape games (e.g. *Tomato Hime*), sequential parts are indexed `salad1_1a.cas`, `salad2_1b.cas`, `salad3_2a.cas`, `salad4_2b.cas` linked to their respective No-Intro long names.
* **Multi-Part / Mixed-Mode Media**: For mixed-mode releases (e.g. the PC-88 *Gundam* tape with interleaved narration/music and CMT data), `dwimsy` preserves the complete source capture and a chronological segment timeline. Data regions may yield canonical CMT/T88 derivatives, while adjacent drama/music regions remain tied to their exact prepared copy-FLAC timestamps and may receive piecewise timebase correction for a regenerated mixed-mode tape. The physical capture, segmentation evidence, and generated result remain separate artifacts.

### Pairing Rules

1. **PC-6001 (.p6 and .p6t Aligned Pairs)**:
   - `game (Japan).p6` ↔ `game (Japan).p6t`: Clean stream trimmed at verified BASIC 0x0000 EOF / MON :00 terminator for standard emulator compatibility.
   - `game (Japan) [untrimmed].p6` ↔ `game (Japan) [untrimmed].p6t`: Raw stream retaining physical trailing flush padding.
2. **MSX (.cas 8-Byte Padded vs. Unpadded Pairs)**:
   - `game (Japan).cas`: Standard 8-byte boundary padded stream (matching TOSEC / No-Intro / OpenMSX preservation databases).
   - `game (Japan) [unpadded].cas`: Compact unpadded byte stream (raw tight chunks).
   - `game (Japan).tsx`: Physical timing container with KCS Block 0x4B and Turbo Block 0x11.
3. **PC-88 / PC-80 (.t88 and .cmt Pairs)**:
   - `game (Japan).cmt` ↔ `game (Japan).t88`: Canonical DumpListEditor / c2t preparation timing.
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

## 9. CLI & Interface Conventions

`dwimsy` provides explicit, typed semantic verbs alongside direct streaming filter shortcuts. Each command declares its implementation status below:

### Implementation Status Overview of Primary Verbs & Filters

```text
┌───────────────────────────┬───────────────────────────────────┬───────────────────────────────┐
│ Command / Subcommand      │ Capability Description            │ Implementation Status         │
├───────────────────────────┼───────────────────────────────────┼───────────────────────────────┤
│ dwimsy convert            │ Bidirectional format converter    │ [x] COMPLETE (PC-88)          │
│ dwimsy inspect            │ Media container inspection        │ [x] COMPLETE (PC-88 T88/CMT)  │
│ dwimsy split              │ Multi-file tape splitting         │ [x] COMPLETE (PC-88 T88/CMT)  │
│ dwimsy join               │ Multi-file tape concatenation     │ [x] COMPLETE (PC-88 T88/CMT)  │
│ dwimsy t882wav / wav2t88  │ Direct PC-88 streaming filters    │ [x] COMPLETE (Milestone 1)    │
│ dwimsy tests              │ Test suite runner                 │ [x] COMPLETE (M1.6)          │
│ dwimsy help               │ Pydoc technical manual viewer     │ [x] COMPLETE (M1.6)          │
│ dwimsy readme / license   │ Documentation / License viewers   │ [x] COMPLETE (M1.6)          │
│ dwimsy changelog          │ Revision history viewer           │ [x] COMPLETE (M1.6)          │
│ dwimsy meta bundle        │ Self-packaging portable unpacker  │ [x] COMPLETE (M1.6)          │
│ dwimsy meta unbundle      │ Portable bundle extractor         │ [x] COMPLETE (M1.6)          │
│ dwimsy meta bundle-fixtures│ Test fixture archive packager    │ [ ] TODO (M1.6)              │
│ dwimsy meta version-bump  │ Version advance & code-hash seal  │ [x] COMPLETE (M1.6)          │
│ dwimsy meta fetch-deps    │ Non-git submodule materializer    │ [x] COMPLETE (M1.6)          │
│ dwimsy meta integrity     │ Portable-project integrity checker│ [x] COMPLETE (M1.6)          │
│ dwimsy wav2cas / cas2wav  │ MSX FSK streaming filters         │ [ ] TODO (Milestone 2.1)      │
│ dwimsy flac2wav           │ Pure-Python streaming FLAC decode │ [ ] TODO (Milestone 2.1)      │
│ dwimsy cmt-filter         │ Analog circuit simulation filter  │ [ ] TODO (Milestone 2.1)      │
│ dwimsy d882fat8 / bin2fds │ Disk converters & charsets        │ [ ] TODO (Milestone 2.3)      │
│ dwimsy charset            │ Streaming character set converter │ [ ] TODO (Milestone 2.3)      │
│ dwimsy extract            │ Payload & filesystem extractor    │ [ ] TODO (Milestone 2.3/2.4)  │
│ dwimsy package            │ ROM cartridge compiler (cas2rom)  │ [ ] TODO (Milestone 2.4)      │
│ dwimsy bridge             │ Real-time hardware gateway/deck   │ [ ] TODO (Milestone 2.5)      │
│ dwimsy archive            │ Archival bundle generator         │ [ ] TODO (Milestone 2.5)      │
│ dwimsy recover            │ Forensic bit/pulse recovery       │ [ ] TODO (Phase 4 / 5)        │
│ dwimsy-ctl                │ Real-time transport control daemon│ [ ] TODO (Milestone 2.5)      │
└───────────────────────────┴───────────────────────────────────┴───────────────────────────────┘
```

### Main CLI Verbs

```bash
# === 1. IMPLEMENTED COMMANDS [x] COMPLETE ===

# Inspect intermediate containers, headers, track tables, and baud rates (PC-88 T88 & CMT)
dwimsy inspect game.t88 -v

# Convert between format representations (PC-88 WAV, T88, CMT)
dwimsy convert capture.wav game.t88 --baud 600
dwimsy convert game.t88 game.cmt
dwimsy convert game.t88 game.wav --mode tape

# Split multi-file tape images into individual program files (PC-88 T88/CMT)
dwimsy split multi_game.t88 -o ./extracted/ --format t88

# Join multiple files into a single tape image (PC-88 T88/CMT)
dwimsy join part1.t88 part2.cmt -o prepared.t88 --bauds 1200,600


# === 2. TOOLING, PACKAGING & TESTING COMMANDS (Milestone 1.6) ===

# Registered placeholder commands remain visible in `--help`; they report their planned milestone until implemented.

# Run unit and integration tests (via -T until the `test` placeholder is implemented)
dwimsy tests
python3 -m dwimsy.tests -v     # or python3 -m dwimsy --test
python3 -m dwimsy.tests fsk -v

# Display technical reference manual for any verb or core subsystem
dwimsy help fsk
dwimsy help t88

# View canonical documentation and license (streams plain Markdown when redirected)
dwimsy readme
dwimsy license
dwimsy readme > README.md
dwimsy license > LICENSE

# Display recent changelog from CHANGELOG.md in terminal
dwimsy changelog -n 5 -v

# Package dwimsy into a standalone self-extracting script with custom tag
dwimsy meta bundle --tag "wav-clamping" --with-deps

# Output the canonical baseline unpacker script directly without bundling working tree
dwimsy meta bundle --baseline -o dwimsy_0.1.6.0_clean.py

# Package local private test fixtures for a specific platform
dwimsy meta bundle-fixtures --platform pc88 -o pc88_fixtures.py

# Advance revision, lock code-hash, and record changelog message in CHANGELOG.md
dwimsy meta version-bump -m "Fix WAV data chunk boundary clamping" -d "Ignore trailing metadata chunks"

# Clone dependencies in non-git checkouts
dwimsy meta fetch-deps

# Verify working tree code integrity against canonical hash
dwimsy meta integrity


# === 3. PLANNED COMMANDS & RECOVERY WORKFLOWS [ ] TODO (Phase 2 & Beyond) ===

# Inspect intermediate containers, headers, track tables, and baud rates (D88 Disks)
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
dwimsy join ./extracted_tracks/ -o prepared.wav

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

### Streaming Pipes & Filters `[ ] TODO (Milestone 2.1 - 2.3)`
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

### Side-Channel UI, Telemetry Layout & Animated Marquee Display `[ ] TODO (Milestone 2.5)`

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
  * `<D>`: Discard / purge active write overlay and revert to pristine prepared copy.
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

### Forward Architecture & CLI Design Notes

* **`dwimsy bridge` Appliance Mode (Milestone 2.5)**: Unlike streamable Unix filters (e.g. `dwimsy-t882wav`) which require shell arguments and standard I/O pipes, `dwimsy bridge` is designed as a **zero-argument, double-click launchable appliance**. On systems configured for OS `.py` launching, double-clicking `dwimsy-bridge` or launching without arguments starts with graceful interactive first-run configuration (serial port selection, default cassette/disk geometry) rather than exiting with an argument error.
* **`dwimsy shell` Programmatic Dispatch (Future Milestone)**: To support an eventual interactive REPL shell (`dwimsy shell`), all CLI subcommand handlers in `dwimsy.cli` are structured as callable functions taking parsed arguments rather than assuming process termination (`sys.exit()`). An in-process REPL loop can thus dispatch commands directly without spawning fresh child processes.

### Positional Per-Input Options (SoX / FFmpeg Model) `[ ] TODO (Milestone 2.5)`

Options placed immediately before an input file act as scoped overrides:
```bash
dwimsy join \
    --profile pc88   loader.cmt \
    --profile pc6001 game.p6 \
    -o prepared.wav --wave tape --volume 0.85
```

### File Linking & Paired Naming `[ ] TODO (Milestone 2.5)`

* When metadata is supplied, `dwimsy` emits both a compact CLI name (`crazy_a.p6`) and an extended No-Intro long name (`Crazy Newton (Computer Land Hokkaido) (Japan) (PC-6001 32K Mode 2 Pages 2) [_] [CLOAD-RUN] 32k.p6`) in a flat directory.
* Links are created with `os.link`, falling back automatically to `shutil.copy2` on FAT32/exFAT, cross-device mounts, or unsupported environments.
* Input capture files are linked/copied directly inside output bundles under standard names.

## 10. Metadata, Checksums & Archival Packaging

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
    sha1: "fb43a1a63c467a92b2345d6e246736d5e305e714"
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
    prepared copy_sha1: "da39a3ee5e6b4b0d3255bfef95601890afd80709"
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
    session_prepared copy_sha1: "da39a3ee5e6b4b0d3255bfef95601890afd80709"
    file_path: "~/.local/share/dwimsy/created/da39a3ee5e6b4b0d3255bfef95601890afd80709/save_tape01.p6t"
    preset: "C-30"
```

### Trailing Byte Trimming & Motor Coasting Ledger `[ ] TODO`

When BIOS routines (PC-6001, MSX CSAVE, PC-88) write padding bytes that CLOAD ignores during motor coast:
* **RLE Pattern Representation**: Documented in `manifest.yaml` as `pattern: "00*26"` or `pattern: "FF*18"`.
* **Byte Offset & Reason**: Stored in manifest metadata to allow reversible reconstruction.

---

## 11. Forensic DSP & Restoration Engines

* **Physical Tape Channel Modeling (`cassette_model.py`)**: `[ ] TODO` Physical and magneto-electric tape-head interface simulation:
  * **Wallace Gap Loss**: High-frequency spatial attenuation `L_gap(f) = 20 × log₁₀(|sin(πg/λ)/(πg/λ)|)` for head gap `g` (for example, ~1.5 µm as a model parameter) at tape speed `v` (for example, 4.76 cm/s; `λ = v/f`).
  * **IEC Type I Equalization**: Standard record pre-emphasis and playback de-emphasis (`τ₁ = 3180 µs`, `τ₂ = 120 µs`, `τ₃ = 12 µs`), balancing write demagnetization `H_demag(s) = 1 / (1 + sτ₁₂₀)`.
  * **Faraday Induction & Saturation**: Induced voltage `e(t) = −N × dΦ/dt` (+6 dB/octave slope) with an anhysteretic `M(H) = tanh(kH)` saturation model.
  * **Dual Operating Modes**:
    * *Physical-Equivalent Mode*: Models the signal path sufficiently to make a modern source behave like the audio signal a specified vintage deck/system would be expected to deliver to authentic retrocomputer hardware. This is a declared approximation, not a claim of exact waveform reconstruction.
    * *Canonical Regeneration Mode*: Generates intentionally standardized electrical signals for deterministic comparison, emulation, or writing replacement media. The result is synthetic and remains separate from the archival capture.
* **Piecewise Timebase Correction & Mixed-Mode Segmentation**: `[ ] TODO` For composite tapes containing interleaved narration/drama audio and modulated data (e.g. ASCII *Tape Login*, *Tank Battle*, PC-88 *Gundam 2*):
  * Distinguishes human speech from computer carrier tones using spectral entropy, spectral flatness (SFM → 0), and zero-crossing regularity (Δt bimodal distribution).
  * Segments the timeline into audio drama (`.ogg` / `.wav`) and data regions (`.t88` / `.t77` / `.cmt`, `.tap`, `.tzx`) referencing source FLAC timestamps.
  * Derives a tape-speed/timebase model from CMT timing observations where the format and signal quality make those observations reliable; this is an inference/model, not an automatic measurement of physical tape speed.
  * Applies piecewise timebase correction to analog audio tracks without altering their analog waveform, while data segments are canonically regenerated.
  * Emits a companion `<basename>.cue` sheet linking audio and data tracks to exact source FLAC timestamps.
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

## 12. Multi-Phase Implementation Roadmap

### Phase 0: Orchestration & Scaffolding `[x] CONSOLIDATED INTO PHASE 1`
*   Phase 0's goal of establishing stream contracts (`stdout` binary data vs. `stderr` out-of-band telemetry) and validating data flow was absorbed directly into the native Phase 1 implementation without requiring temporary wrapper classes.

### Phase 1: Minimum Viable Vertical Slice - PC-88 Only `[x] COMPLETE`

The goal of Phase 1 was a single, narrow, end-to-end path through the architecture - not breadth. No MSX, no disks, no full CLI verb set, no hardware side-channel. Just enough to prove the core abstractions hold up against one real platform with clean, composable libraries.

Tasks:
1. `[x] DONE` Implement `dwimsy.core.pulse` (zero-crossing timer, dynamic glitch rejection, AGC, DC-blocker), tuned initially against PC-88/PC-8801's 2400/1200 Hz FSK.
2. `[x] DONE` Implement `dwimsy.core.audio`: streaming WAV reader/writer.
3. `[x] DONE` Implement `dwimsy.core.fsk`: FSK pulse classifier with carrier drift tracking & UART byte framer, extracted from `wav2t88`/`t882wav`.
4. `[x] DONE` Port `t882wav` and `wav2t88` as Netpbm-style streaming filters (`dwimsy.cli.filters.*`), backed directly by `dwimsy.core.*`.
5. `[x] DONE` Implement a minimal `dwimsy` CLI exposing `convert` and basic `inspect` (for `.t88`/`.cmt`).
   Verification: `[x] VERIFIED` Bit-exact roundtrip on real PC-88 `.t88` samples (e.g. `input01.t88`, `input16.t88`) and real audio captures (`snippet.wav` at 1200 baud, `snippet2.wav` at 600 baud) through `wav2t88` ↔ `t882wav`, matching original container data byte-for-byte across test fixtures.

### Phase 1.5: Full PC-88 Parity `[x] COMPLETE`

The goal of Phase 1.5 was functional, parameter, and diagnostic parity with the full `pc88_tape_tools` feature set (`pc88_tape_tools.py`, `t882wav.py`, `wav2t88.py`), providing a self-contained PC-88 reference implementation.

Tasks:
1. `[x] DONE` Implement `dwimsy.tape.t88`: native container reader, writer, block model (`T88File`, `T88Block`, `DataSubHeader`), lead-in/carrier/gap synthesis, and `split_t88_file` / `join_t88_files`.
2. `[x] DONE` Implement `dwimsy.protocols.pc88`: authentic ROM BIOS and Monitor state machine parsers for Tokenized BASIC (`0xD3`), MON Machine Language (`0x24`/`0x3A`), ASCII Sequential (`0x9C`), custom bootstrap loaders (`0xFF` NONTAMA), and headerless MON O/I streams.
3. `[x] DONE` Implement `dwimsy split` for PC-88: program-aware slicing of multi-file `.cmt` and `.t88` images into individual standalone files with preserved carrier lead-ins.
4. `[x] DONE` Implement `dwimsy join` for PC-88: concatenation of multiple `.cmt` and `.t88` files into unified multi-part images with standard inter-block gap and carrier tags.
5. `[x] DONE` Port `pc88_tape_tools.py analyze`, `t882wav.py --inspect`, and `wav2t88.py --inspect` into unified native `dwimsy inspect` (reporting stereo channel energy balance/recommendations, Mark/Space cycle counts, carrier drift speed offset, memory load ranges, BASIC line numbers, record counts, and baud rates).
6. `[x] DONE` Port all CLI flags and aliases (`--flavor`, `--bauds`, `--invert`, `-a`/`-v`/`--volume`, `--channel`, `-v`/`--verbose`, `--help-all`) and standalone executable filter applet support.

### Phase 1.6: Infrastructure, Self-Packaging & CLI Symmetries `[ ] IN PROGRESS`

The goal of Milestone 1.6 is to establish the complete developer tooling, self-packaging, test execution, and documentation pipeline, providing a clean safety harness before parser hardening and Phase 2.

Tasks:
1. `[x] DONE` **`dwimsy.meta.integrity`**: Canonical portable-project hashing, including tests, project metadata, lazy `.gitmodules` dependency globs, and `unbundle.py` with its `blztar` payload elided. Supports runtime modification detection and `--baseline` checks.
2. `[x] DONE` **`dwimsy.meta.bundle` (`dwimsy meta bundle`)**: Self-packaging unpacker generation, embedded `blztar`, baseline reconstruction, canonical `unbundle.py` template handling, and `--diff` support.
3. `[ ] TODO` **Single-Source Asset Resolution Hierarchy**: Maintain `README.md`, `LICENSE`, `CHANGELOG.md`, and `.gitmodules` as canonical on-disk files. Resolve text with local working tree precedence (when not a system package), falling back to in-memory `blztar` decompression when running as an installed system package.
4. `[x] DONE` **`dwimsy meta version-bump` & `CHANGELOG.md`**: Built the atomic `dwimsy meta version-bump` command to increment revision, generate new code-hash, update build dates, prepend entries to `CHANGELOG.md`, and seal `dwimsy/meta/bundle.py`.
5. `[x] DONE` **`dwimsy changelog`**: Implemented `dwimsy changelog` to parse and display revision history from `CHANGELOG.md` (or `blztar` fallback).
6. `[x] DONE` **`dwimsy readme` & `dwimsy license`**: Implemented CLI documentation viewers with `pydoc.pager` interactive TTY viewing and plain streaming for pipes/files.
7. `[x] DONE` **`dwimsy help`**: Implemented `dwimsy help [verb|topic]` to display interactive pydoc technical manuals for CLI verbs and core subsystems.
8. `[x] DONE` **`dwimsy meta fetch-deps`**: Parse `.gitmodules` from disk or `blztar` and materialize frozen reference submodules in non-git checkouts.
9. `[ ] TODO` **`dwimsy meta bundle-fixtures`**: Implement `dwimsy meta bundle-fixtures` to package local private fixture subsets into self-extracting unpackers targeting `tests/fixtures/`.
10. `[x] DONE` **`dwimsy.tests.fixtures`**: Implement content-addressed fixture registry (`FixtureSpec`) and discovery pool (`FixturePool`) indexing by SHA-1 hash rather than non-semantic filenames.
11. `[x] DONE` **Test runner infrastructure**: Central in-process test runner with target filtering, listing (`--list`), and scoped `dwimsy <verb> --test` execution via `dwimsy tests`. Subprocess tests are explicitly skipped during portable bundle verification because child interpreters cannot inherit the in-memory bundle importer; unbundle first to run them.
12. `[ ] TODO` **Packaging & Shebangs**: Add `pyproject.toml` with console script entry points (`dwimsy`, `dwimsy-t882wav`, `dwimsy-wav2t88`, `dwimsy-tests`), and ensure all CLI-executable scripts start with `#!/usr/bin/env python3`.

### Phase 1.7: PC-88 State-Machine Parser, Checksums & Submodule Ejection `[ ] TODO`

The goal of Milestone 1.7 is to eliminate structural vulnerabilities in the reference PC-88 parser, enforce strict container/audio boundaries, and permanently eject the `pc88_tape_tools` submodule scaffolding.

Tasks:
1. `[ ] TODO` **Deterministic State-Machine Parser**: Refactor `CMTFile.split()` from forward byte-scanning into a formal grammar-based state machine (`SYNC` → `HEADER` → `PAYLOAD` → `CHECKSUM` → `TERMINATOR`), eliminating false-split vulnerabilities when binary payloads contain `0xD3`/`0x24`/`0x9C` bytes.
2. `[ ] TODO` **Full MON Record Checksum Validation**: Validate high/low address checksums and payload checksums for every consumed Intel-Hex/MON record, terminating only on verified `:00` records or carrier drops.
3. `[ ] TODO` **Fault-Tolerant "Emit & Tag" Error Handling (`fsck` Model)**: Ensure truncated/corrupted streams and blocks log diagnostics to `stderr`/manifest and emit the salvaged payload with `[truncated]` / `[corrupt]` qualifiers and `observed-truncated` epistemic tags, falling back to raw binary rather than crashing.
4. `[ ] TODO` **WAV `data` Chunk Clamping**: Enforce strict chunk boundary clamping in `StreamingWavReader` (`core.audio`), ensuring reads stop at `data_size` and ignore trailing metadata chunks (`LIST`, `INFO`, `cue `).
5. `[ ] TODO` **T88 Truncation & Magic Hardening**: Enforce declared block length verification in `T88Block.unpack()` and `StreamingT88Reader`, and separate canonical 24-byte signature verification from permissive legacy sniffing.
6. `[ ] TODO` **Eliminate Exception Swallowing**: Remove bare `except Exception: pass` blocks in `split_t88_file()` and `join_t88_files()`, logging typed diagnostics.
7. `[ ] TODO` **Adversarial Test Suite & Submodule Ejection**: Add adversarial regression tests covering fake headers in payloads, embedded `0x3A` colons, bad checksums, verify 100% test pass rate, and permanently eject `deps/pc88_tape_tools`.

### Phase 2: MSX Generalization, Disk Subsystems, Unpackers & Core Realtime `[ ] TODO`

Phase 2 is structured into fine-grained milestones to allow accelerated submodule ejections and progressive validation:

#### Milestone 2.1: MSX Tape & DSP Codec Migration (Eject `wav2cas`) `[ ] TODO`
1. `[ ] TODO` Port `wav2cas.py`, `cas2wav.py`, and `flac2wav.py` (pure-Python streaming FLAC decode) into `dwimsy.core.audio` and `dwimsy.tape.cas` (8-byte padded and compact unpadded flavors).
2. `[ ] TODO` Port `cmt_filter.py` into `dwimsy.dsp.filter` (MSX CMT-IN/CMT-OUT analog circuit simulation).
3. `[ ] TODO` Port `cassette_model.py` into `dwimsy.dsp.modeler` (magnetic tape channel simulation with Wallace gap loss and IEC equalization).
4. `[ ] TODO` Implement `dwimsy.protocols.msx` (BIOS `1F A6` sync tokens and header state machine).
5. `[ ] TODO` **Submodule Ejection**: Verify 100% MSX parity and permanently eject `deps/wav2cas`.

#### Milestone 2.2: MSX TSX Container Integration `[ ] TODO`
1. `[ ] TODO` Implement `dwimsy.tape.tsx` (MSX TSX container with KCS Block `0x4B` and Turbo Block `0x11`).
2. `[ ] TODO` Connect MSX FSK demodulator directly to TSX Block `0x4B` for archival preservation of non-BIOS and custom-loader tapes.

#### Milestone 2.3: Disk Subsystems & Character Transcoders (Eject `fat8_d88_tool` & `bin2fds`) `[ ] TODO`
1. `[ ] TODO` Port `fat8_d88_tool` into `dwimsy.disk.d88` (D88 sector container) and `dwimsy.disk.fat8` (FAT8 filesystem parser/injector).
2. `[ ] TODO` Port RBYTE encoding/decoding and PC-88/PC-98 BASIC save deobfuscation key recovery.
3. `[ ] TODO` Port `core.charsets` (JIS X 0201, NEC semigraphics, MSX Katakana, ASCII, and streaming CLI converter `dwimsy charset`).
4. `[ ] TODO` Port `bin2fds.py` from Python 2 to Python 3 in `dwimsy.disk.fds`.
5. `[ ] TODO` **Submodule Ejection**: Verify disk and charset parity and permanently eject `deps/fat8_d88_tool` and `deps/bin2fds`.

#### Milestone 2.4: Binary Unpackers & ROM Cartridge Hooks (Eject `nontama_to_bload`) `[ ] TODO`
1. `[ ] TODO` Port `nontama_to_bload.py` and `mload_to_bload.py` into `dwimsy.platforms.unpack`.
2. `[ ] TODO` Port `mkrom.py` and MSX Sakhr `cas2rom` into `dwimsy.platforms.cart_hooks`.
3. `[ ] TODO` **Submodule Ejection**: Verify unpacker/ROM parity and permanently eject `deps/nontama_to_bload`.

#### Milestone 2.5: Core Realtime Contracts, Side-Channel UI & Telemetry `[ ] TODO`
1. `[ ] TODO` Implement `dwimsy.core.realtime` (live-stage contracts, bounded buffering/latency, resynchronization latency, backpressure).
2. `[ ] TODO` Implement `dwimsy.cli.sidechannel` (2-line ANSI Virtual LCD marquee on `stderr`, TTY keystrokes, POSIX/Win32 signals).
3. `[ ] TODO` Implement `dwimsy.ui.remote` (IPC control daemon / WebSockets / web & phone dashboard).
4. `[ ] TODO` Implement `dwimsy.core.transport`, `transport.changer`, `transport.browser`, `transport.seeker`, and `dsp.router`.
5. `[ ] TODO` Implement `tape.variants`, `tape.geometry`, and `metadata.archive` bundle generation.

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
6. `[ ] TODO` Implement raw floppy flux decoders and multi-revolution consensus (Applesauce .a2r/.woz, Greaseweazle .scp/.raw).
7. `[ ] TODO` Finalize `pyproject.toml`, docstrings, and test suite for pip packaging.

## 13. Format & Protocol Technical Reference Guide

The tables in this section are engineering references, not authority by themselves. Values that are format-specific, hardware-specific, or derived from reverse engineering should be independently verified before being treated as established facts. Where a value is a model parameter rather than a format requirement, implementations should record its provenance and epistemic status.

### Physical Modulation Reference Table

| Platform / System          | Modulation Type  | Mark / 1 Frequency                           | Space / 0 Frequency                           | Baud / Data Rate                  | Bit Framing                           |
| :------------------------- | :--------------- | :------------------------------------------- | :-------------------------------------------- | :-------------------------------- | :------------------------------------ |
| **NEC PC-8001 / PC-8801**  | FSK              | 2400 Hz (2 cyc)                              | 1200 Hz (1 cyc)                               | 1200 / 600 baud                   | 1 Start (0), 8 Data (LSB), 2 Stop (1) |
| **NEC PC-6001 / PC-6601**  | FSK              | 2400 Hz (2 cyc)                              | 1200 Hz (1 cyc)                               | 1200 / 600 baud                   | 1 Start (0), 8 Data (LSB), 2 Stop (1) |
| **Fujitsu FM-7 / FM-8**    | FSK (T77)        | 2400 Hz (2 cyc)                              | 1200 Hz (1 cyc)                               | 1200 / 600 baud                   | 1 Start (0), 8 Data (LSB), 2 Stop (1) |
| **MSX / MSX2 (Standard)**  | FSK              | 2400 Hz (2 cyc)                              | 1200 Hz (1 cyc)                               | 1200 / 2400 baud                  | 1 Start (0), 8 Data (LSB), 2 Stop (1) |
| **MSX (Sanyo 2x Fast)**    | Octave FSK       | 4800 Hz (2 cyc)                              | 2400 Hz (1 cyc)                               | 2400 baud                         | 1 Start (0), 8 Data (LSB), 2 Stop (1) |
| **MSX (European Turbo)**   | PWM / Pulse      | Short edge pair                              | Long edge pair                                | 2000-4000+ baud                   | Raw bitstream, zero stop bits         |
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
PC-88 T88   .t88        50 43 2D 38 38 30 31 20 54 61 70 65 20 49 6D 61 67 65 28 54 38 38 29 00 (24B) + 00 01 00 02 01 00 (VERSION tag)
PC-88 CMT   .cmt        D3 D3 D3... (BASIC), 24 24 24... (MON ML), 9C 9C 9C... (ASCII)
FM-7 T77    .t77        58 4D 37 20 54 41 50 45 20 49 4D 41 47 45 20 30 ("XM7 TAPE IMAGE 0", 16B)
MSX TSX     .tsx / .tzx 5A 58 54 61 70 65 21 1A ("ZXTape!\x1a") + ver 0x01 0x20/0x21
MSX CAS     .cas        1F A6 DE BA CC 13 7D 74 (8-byte BIOS sync header)
Sharp MZF   .mzf / .m12 01 (File type) + 16-byte filename + 128-byte header
Sharp MZT   .mzt        Multiple 128-byte MZF directory header blocks concatenated in sequence
Sharp X1    .tap        54 41 50 45 ("TAPE") or raw Sharp X1 2700-baud chunks
Family BASIC.mzt / .cas Sharp MZ-compatible PWM block structure with Famicom BASIC V2/V3 header
Famicom Data.fbt / .tp  Raw level dump blocks (Excitebike, Lode Runner, etc.)
BBC UEF     .uef        1F 8B (Gzip header) -> 55 45 46 20 46 69 6C 65 21 ("UEF File!")
Amstrad CDT .cdt        5A 58 54 61 70 65 21 1A ("ZXTape!\x1a")
Sinclair TZX.tzx        5A 58 54 61 70 65 21 1A ("ZXTape!\x1a")
PC-6001 P6T .p6t        PC6001V format with trailing timing/mode descriptors & autostart footer
PC-6001 P6  .p6         D3 D3 D3... + screen mode / page count descriptor
Sega CAS    .cas        53 45 47 41 20 43 41 53 53 45 54 54 45 ("SEGA CASSETTE")
Sord M5 CAS .cas        55 55 55 55 55 55 55 55 (Sync run) + 'HEADER'
NEC D88     .d88 / .d77 17-byte disk title + 0x00 + 0x00 0x00 0x00 0x00
FDS Image   .fds        46 44 53 1A ("FDS\x1a") or Block 1 '\x01*NINTENDO-HVC*'
Applesauce  .woz / .a2r 57 4F 5A 31 / 57 4F 5A 32 | 41 32 52 32 ("A2R2") | 41 32 52 33 ("A2R3")
Greaseweazle.scp        53 43 50 ("SCP")
C64 CRT     .crt        43 36 34 20 43 41 52 54 52 49 44 47 45 20 20 20 ("C64 CARTRIDGE   ")
```

### Consulted Literature & Technical Specifications Reference

1. **IEC Standard 60094-4 & 60094-5**: "Magnetic Tape Sound Recording and Reproducing Systems" - Standard equalization time constants for Type I cassettes (3180 µs, 120 µs, 12 µs).
   * URL: https://webstore.iec.ch/publication/723
   * Wayback Machine: https://web.archive.org/web/20220601/https://webstore.iec.ch/publication/723
2. **Wallace, R. L. (1951)**: "The Reproduction of Magnetically Recorded Signals", *Bell System Technical Journal*, 30(4), pp. 1145-1173 (Gap and spacing loss equations).
   * URL: https://doi.org/10.1002/j.1538-7305.1951.tb03700.x
3. **Jiles, D. C., & Atherton, D. L. (1986)**: "Theory of Ferromagnetic Hysteresis", *Journal of Magnetism and Magnetic Materials*, 61(1-2), pp. 48-60 (Anhysteretic tape magnetization and AC bias linearization models).
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
8. **Rob Hagemans / PC-BASIC Project**: "Protected File Format" - reverse-engineering of GW-BASIC's protected-save (`,P`) obfuscation scheme (the paired 11-byte/13-byte XOR key structure). Documents the algorithm's internal workings for GW-BASIC, not NEC's dialects.
   * URL: https://robhagemans.github.io/pcbasic/doc/2.0/#protected-file-format
9. **NEC (1983)**: "PC-8001 mkII SR N80-BASIC / N80SR-BASIC Reference Manual" - documents the `,P` protected-save *access method* (the `SAVE`/`BSAVE` flag itself) but not the obfuscation algorithm's internal workings.
10. **`fat8_d88_tool` project (original research)**: Recognizing that NEC's N88-BASIC protected-save format follows the same paired-XOR-key structure documented for GW-BASIC (per item 8) but with different key data baked into PC-88 ROM, and devising a known-plaintext `SAVE`-based method to recover the PC-88 combined XOR key without needing the ROM itself. The related PC-98 `N88-BASIC(86)` protected-save format uses an unrelated single-bit-rotation scheme, identified independently by direct known-plaintext testing rather than from any published reference. See the [`fat8_d88_tool` README](https://github.com/f-fix/fat8_d88_tool#de-obfuscation-pc98-version) for the full derivation and recovered key material.

---

## 14. Revision History

### [0.1.6.0-dev] - 2026-08-23 (Milestone 1.6) `[ ] IN PROGRESS` (Hash: unsealed / pending `version-bump`)
* **Summary**: Milestone 1.6: Developer infrastructure, self-packaging, testing & documentation architecture
  * `[x] COMPLETE`: Content-addressed test fixture registry (`dwimsy.tests.fixtures`) and discovery pool (`FixturePool`)
  * `[ ] PLANNED`: Add `dwimsy meta bundle` (with `--baseline` export) and `dwimsy meta bundle-fixtures` portable unpacker generators
  * `[ ] PLANNED`: Add `dwimsy meta version-bump`, `dwimsy changelog`, `dwimsy help`, `dwimsy meta fetch-deps`, and `dwimsy meta integrity`
  * `[ ] PLANNED`: Maintain `README.md` and `CHANGELOG.md` as canonical markdown sources of truth with in-memory `blztar` fallback
  * `[x] COMPLETE`: Unified `dwimsy tests` CLI runner with scoped subsystem filtering

### [0.1.5.0] - 2026-08-23 (Milestone 1.5 Baseline) `[x] COMPLETE`
* **Summary**: Milestone 1 & 1.5: Native PC-88 DSP vertical slice and container/protocol parity
  * Native core DSP libraries: `core.pulse`, `core.fsk`, and `core.audio` (Streaming WAV reader/writer)
  * Native PC-88 container and protocol models: `tape.t88` and `protocols.pc88`
  * Streaming CLI filters (`cli.filters.t882wav`, `cli.filters.wav2t88`) and initial verbs (`convert`, `inspect`, `split`, `join`)

## 15. Note on the code and the tools used to write it


Parts of this code were written (including some initial ones that began in other, separate projects) with assistance from LLM-integrated coding tools. If you don't like it, feel free to use other software or rewrite parts you dislike. PRs are welcome!

### How did I end up using those? Don't I dislike slop?

Yes, I hate slop. This project began because I wanted tape image conversion tools where the conversion steps were all clearly documented and readable code, but which also performed well enough in terms of accuracy to actually be the tool I use. I started out writing the tools myself, but my manual attempts hadn't yielded comparable accuracy to existing closed-source tools for some steps, so I started using the tools to help find the bugs and suggest improvements, and IMO the result is now good enough to actually be useful in some scenarios. In terms of slop, the tool-generated code doesn't closely resemble any existing solutions I have found. Rather it's a fairly passable translation of my requests into Python.


## 16. Multi-Stream Version Reconciliation, In-Memory Bootloader & Isolation

### Purpose & The Airgapped Workflow Model

Development sometimes happens on machines with python3 and nothing else (no git binary, no network, no package manager). Work still needs to happen there and reconcile with the connected, git-tracked mainline.

Core workflows supported:
1. Airgapped development: start from a standalone bundle, make edits, and seal versions offline.
2. Safe static transport (--include): import foreign bundle streams without executing foreign code.
3. Manual reconciliation (meta diff): compare versions across streams and branches; conflicts are surfaced for human resolution.
4. Historical security fixes: branch with --alt, refine, seal, reinsert with --splice, and --prune temporary branches.

### Stream Naming & Reserved Identifiers
- Stream 0 is `primary`.
- Alternate streams are `alt1`, `alt2`, ... (`alt0_` is invalid and rejected).
- `primary_TAG` aliases bare `TAG`.
- `_sealed` is reserved as a selector and tag suffix case-insensitively.

### Selector Taxonomy:
- `sealed` / `primary_sealed`: latest sealed primary release.
- `alt_sealed`: latest sealed release in first alternate stream containing one.
- `altN_sealed`: latest sealed release in `altN`.
- `primary`: primary head (`unbundled` if on disk, else `baseline`).
- `alt`: head of `alt1`.
- `altN`: head of `altN`.
- `unbundled`: current working-directory version on disk.
- `baseline`: latest embedded primary version.

### Multi-Stream Composite Bundle Naming
Multi-stream bundles delimit stream versions using comma `,` with uniform `,altN` notation:
- 1 stream: `dwimsy_VERSION1.py` (or `.pyz`)
- 2 streams: `dwimsy_VERSION1,alt1_VERSION2.py` (shortened to `dwimsy_VERSION1,alt1.py` if `VERSION2 == VERSION1`)
- 3+ streams: `dwimsy_VERSION1,alt1_VERSION2,alt2_VERSION3.py` (shortened to `,altN` if `VERSION_N == VERSION_{N-1}`)

### --list-versions Notation
- Two independent grep-friendly stateless annotation tokens:
  1. Named-selector membership: `=keyword` (exact head) / `=~keyword` (in match set).
  2. Peer content-equivalence: `=primary_TAG` / `=altN_TAG` (fully-qualified, symmetric).
- Column Layout: `[stream] <version>  <timestamp>  <hash>  [<annotations>]  [<provenance>]`.
- Timestamps: ISO 8601 UTC timestamps (`YYYY-MM-DDTHH:MM:SSZ`) derived from layer metadata.
- Hashes: 12-character short hashes by default for easy visual correlation with `--version` and `+mod.<short_hash>` tails. Specifying `--verbose` (`dwimsy --version-list --verbose`) expands hashes to full 64-character SHA-256 strings.
- Single Shared Entry: When an on-disk checkout is content-identical to the baseline, the redundant top `[unbundled]` row is omitted, and the primary baseline row includes `=unbundled` in its annotations (`[=baseline, =primary, =unbundled, =selected]`).
- Provenance column is unconditional on every row: `[=unbundled: .]`, `[=primary: dwimsy_0.1.6.69-dev.py]`, `[=~primary: ...]`, `[=altN: path]`, `[=~altN: path]`.

### Execution Model & The Three Paths
- Path A: Default in-memory virtual mount via `BundleFinder` (zero disk writes).
- Path B: Reconstruct-and-inject into single ephemeral file for non-baseline embedded versions.
- Path C: Pass-through or swap-and-lie execution for disk-backed checkouts based on exact blztar byte comparison.

### Distribution Shapes & .pyc Support
- `.py`: Standalone self-extracting script.
- `.pyz`: Compressed zipapp executable.
- `.pyc`: Precompiled bytecode distribution: `python3 -m py_compile dwimsy/meta/unbundle.py` and rename to `dwimsy.pyc`.
- `-a` / `--argv0`: Authoritative display-name and self-location override, supporting Windows batch wrappers (`@py -3 "%~dp0dwimsy.pyz" --argv0="%~n0" %*`).

### Version Export & Dependency Shadow Fallback
- Prune-to-one-layer (`--prune`) is the supported way to export a version as a standalone snapshot.
- Dependency shadow fallback (`deps/`): inside a git checkout, falls back to embedded shadow copy iff declared in live `.gitmodules`; outside a checkout, falls back unconditionally.

### Explicit Non-Goals
- No auto-merging (`meta merge` is intentionally excluded).
- No speculative patching (`meta patch` is deferred).
- Coarse-grained version tags and changelog prose serve as the complete audit trail.
