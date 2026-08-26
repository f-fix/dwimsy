# Changelog

All notable changes to the dwimsy project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [0.1.6.2-dev] - 2026-08-26

### Changed
- Use HTML character references for LaTeX syntax and dash character bans in README.md.

## [0.1.6.1-dev] - 2026-08-25

### Added
- Direct execution entrypoints and standalone CLIs for maintainer tools (`dwimsy.meta.diff`, `dwimsy.meta.integrity`, `dwimsy.meta.lint`, `dwimsy.meta.version_bump`).
- Central maintainer namespace dispatcher `dwimsy.meta` (`dwimsy/meta/__main__.py`).
- First-class top-level `t882wav` and `wav2t88` commands under the central `dwimsy` CLI.
- Top-level `tests` command and `--list` test enumeration in `dwimsy.tests`.
- Documentation viewer commands `dwimsy readme`, `dwimsy license`, `dwimsy changelog`, and `dwimsy help` with TTY-aware safe pager fallback.
- Automated version bumping and baseline synchronization tool `dwimsy meta version-bump`.
- Repository hygiene and style invariant validator `dwimsy meta lint`.
- Universal CLI entrypoint self-test verification (`--help`, `--version`, `--test[=FILTER]`, and `--verbose`).
- Developer Workflow, Environment Variables, and Character & Syntax Considerations documentation in `README.md`.

## [0.1.6.0-dev] - 2026-08-23

### Added
- Native Phase 1 DSP and physical layer modules (`core.pulse`, `core.fsk`, `core.audio`).
- PC-88 protocol and container models (`tape.t88`, `protocols.pc88`).
- Streaming filter applets (`t882wav`, `wav2t88`) and unified CLI (`convert`, `inspect`, `split`, `join`).
- In-process test discovery and execution engine (`dwimsy.tests`, `dwimsy tests`, `dwimsy --test`).
- Portable single-file unpacker and in-memory module loader (`dwimsy.meta.bundle`, `dwimsy.meta.unbundle`).
- Content-addressed project integrity and modification detection (`dwimsy.meta.integrity`).
- Canonical working tree comparison against portable baseline (`dwimsy.meta.diff`).
