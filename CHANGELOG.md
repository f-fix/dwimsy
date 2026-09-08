# Changelog

All notable changes to the dwimsy project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.6.109-dev] - 2026-09-08T06:37:35Z

### Changed
- Document unimplemented status and milestone targets for 'recover' and 'bundle-fixtures' commands.

## [0.1.6.108-dev] - 2026-09-08T06:02:17Z

### Changed
- Reformatted

## [0.1.6.107-dev] - 2026-09-08T05:20:33Z

### Changed
- Implement pure-Python airgapped .gitignore matching, boundary isolation, and universal --with-git/--without-git CLI flags.

## [0.1.6.106-dev] - 2026-09-08T01:51:41Z

### Changed
- Protect Git-ignored target files during unbundle and rollback.

## [0.1.6.105-dev] - 2026-09-07T23:53:13Z

### Changed
- Fix unbundle docstring synchronization and version resolution performance.

## [0.1.6.104-dev] - 2026-09-07T19:57:44Z

### Changed
- Improve test runner isolation, discovery, and version resolution performance.

## [0.1.6.103-dev] - 2026-09-07T18:08:17Z

### Changed
- Reformatted

## [0.1.6.102-dev] - 2026-09-07T18:07:47Z

### Changed
- Reformatted

## [0.1.6.101-dev] - 2026-09-07T10:11:47Z

### Changed
- Fix base-layer timestamps, tighten changelog fallback, and avoid unnecessary timestamp TAR scans.

## [0.1.6.100-dev] - 2026-09-07T09:53:12Z

### Changed
- Reformatted

## [0.1.6.99-dev] - 2026-09-07T09:08:56Z

### Changed
- Fix clean working tree bundle baseline generation, prohibit empty layers, and enforce no trailing whitespace linter

## [0.1.6.98-dev] - 2026-09-07T06:34:10Z

### Changed
- Fix rollback history truncation and blztar preservation

## [0.1.6.97-dev] - 2026-09-07T04:54:25Z

### Changed
- Fix unbundle manifest timestamp and unbundle.py idempotency

## [0.1.6.96-dev] - 2026-09-07T03:49:19Z

### Changed
- Use second-exact changelog timestamps for version bundles

## [0.1.6.95-dev] - 2026-09-07

### Changed
- Canonicalize layer timestamps during packing and unbundling; avoid rewriting identical unbundle.py

## [0.1.6.94-dev] - 2026-09-07

### Changed
- Record 1-second resolution layer mtimes for newly created layers

## [0.1.6.93-dev] - 2026-09-07

### Changed
- Fix --version-list timestamps and unbundle rollback instructions

## [0.1.6.92-dev] - 2026-09-06

### Changed
- Honor canonical manifest during bundle creation and exclude unmanifested build artifacts.

## [0.1.6.91-dev] - 2026-09-06

### Changed
- Honor canonical manifest during bundle creation and exclude unmanifested build artifacts.

## [0.1.6.90-dev] - 2026-09-06

### Changed
- Fix information-loss safety and version-labelled diff output

## [0.1.6.89-dev] - 2026-09-06

### Changed
- Require --force for information-losing rollback and version-space pruning; fix CLI help and dispatch consistency.

## [0.1.6.88-dev] - 2026-09-06

### Changed
- Fix CLI entry-point consistency, historical rollback, and baseline bundle handling

## [0.1.6.87-dev] - 2026-09-06

### Changed
- Fix historical rollback cleanup and baseline bundling

## [0.1.6.86-dev] - 2026-09-06

### Changed
- Fix per-side VersionSpace formatting in meta diff

## [0.1.6.85-dev] - 2026-09-06

### Changed
- Standardize $VERSION_SUMMARY diff normalization using active VersionSpace

## [0.1.6.84-dev] - 2026-09-06

### Changed
- Fix $VERSION_SUMMARY multi-stream preservation in diff engine

## [0.1.6.83-dev] - 2026-09-06

### Changed
- Fix $VERSION_SUMMARY target VersionSpace slicing in diff engine

## [0.1.6.82-dev] - 2026-09-06

### Changed
- Fix $VERSION_SUMMARY diff substitution in cross-stream comparisons and preserve stream source in slicing

## [0.1.6.81-dev] - 2026-09-06

### Changed
- Fix $VERSION_SUMMARY diff slicing, is_modified declared version check, and PagedHelpAction on --help

## [0.1.6.80-dev] - 2026-09-06

### Changed
- Fix $VERSION_SUMMARY diff substitution, PagedHelpAction on --help, and unbundle upgrade detection

## [0.1.6.79-dev] - 2026-09-06

### Changed
- Fix diff $VERSION_SUMMARY normalization, meta diff paging, and standalone hermeticity

## [0.1.6.78-dev] - 2026-09-05

### Changed
- Fix live-tree inclusion and portable diff selectors

## [0.1.6.77-dev] - 2026-09-04

### Changed
- Fix bundle delta layer tag injection and unbundle rollback banner

## [0.1.6.76-dev] - 2026-09-04

### Changed
- Harden standalone test discovery and runner state isolation

## [0.1.6.75-dev] - 2026-09-03

### Changed
- Polish hermetic test runner and finalize v9.1 implementation fixes

## [0.1.6.74-dev] - 2026-09-03

### Changed
- Complete hermetic standalone test discovery and preserve fixture and metadata coverage

## [0.1.6.73-dev] - 2026-09-03

### Changed
- Make standalone self-tests hermetic and avoid surrounding checkout test discovery

## [0.1.6.72-dev] - 2026-09-03

### Changed
- Harden standalone test isolation, diff checkout boundaries, and unbundle git metadata handling

## [0.1.6.71-dev] - 2026-09-03

### Changed
- Fix version-bump silently defaulting to --patch when no explicit bump tier is given; require an explicit --major/--minor/--patch/--rev (matching the existing non-empty message requirement). Fix stray extra blank lines in README.md before the Project Homepage line.

## [0.1.6.70-dev] - 2026-09-02

### Changed
- Reformatted

## [0.1.6.69-dev] - 2026-09-02

### Changed
- Implement multistream specification compliance and harden the release bundle

## [0.1.6.68-dev] - 2026-09-02

### Changed
- Integrate hardened unbundle controls and candidate self-round-trip verification

## [0.1.6.67-dev] - 2026-09-01

### Changed
- Complete set-valued selectors and harden bundle/unbundle verification

## [0.1.6.66-dev] - 2026-08-31

### Changed
- Restore =~ aliases and fix duplicate = matches in version list

## [0.1.6.65-dev] - 2026-08-31

### Changed
- Strict SemVer match fix + fast bundle

## [0.1.6.64-dev] - 2026-08-31

### Changed
- Strict SemVer compliance for bare version patterns (v2)

## [0.1.6.63-dev] - 2026-08-31

### Changed
- Strict SemVer compliance for bare version patterns and repair versions.py

## [0.1.6.62-dev] - 2026-08-31

### Changed
- Enhanced semantic version matching logic.

## [0.1.6.61-dev] - 2026-08-30

### Changed
- Reformatted

## [0.1.6.60-dev] - 2026-08-30

### Changed
- Allow bare -v to modify --version-list verbosity, support --version-list=full/short, and add CLI flag tests

## [0.1.6.59-dev] - 2026-08-30

### Changed
- Fix --version-list --verbose order-independence for full hash display; wire dispatch.py verbose pass-through

## [0.1.6.58-dev] - 2026-08-30

### Changed
- test bump

## [0.1.6.57-dev] - 2026-08-30

### Changed
- Refuse unbundled diff outside checkouts, support 12-char hashes, UTC timestamps, rollback restoration, and documentation updates

## [0.1.6.56-dev] - 2026-08-30

### Changed
- Share single version-space entry and eliminate mod suffix when unbundled matches baseline, support safe unbundle upgrades and unbundle.py overwrite protection

## [0.1.6.55-dev] - 2026-08-30

### Changed
- Synchronize README.md status matrix and update test command references to tests

## [0.1.6.54-dev] - 2026-08-29

### Changed
- Reformatted

## [0.1.6.53-dev] - 2026-08-30

### Changed
- Ignore .git directory and .gitignore matching entries in filename linter and bundler

## [0.1.6.52-dev] - 2026-08-29

### Changed
- Reformatted

## [0.1.6.51-dev] - 2026-08-30

### Changed
- Enforce stream invariants, fix root resolution, changelog formatting, and version bump parsing

## [0.1.6.50-dev] - 2026-08-30

### Changed
- Enforce stream invariants, C base64 decoding, safe unbundle guards, and changelog boundary formatting

## [0.1.6.49-dev] - 2026-08-29

### Changed
- Reformatted

## [0.1.6.48-dev] - 2026-08-29

### Changed
- Maintenance release and baseline synchronization.

## [0.1.6.45-dev] - 2026-08-29

### Changed
- Enforce strict position/semver layer determination, reading invariants, serializer readback validation, and destination safety

## [0.1.6.44-dev] - 2026-08-29

### Changed
- Enforce strict position/semver layer determination, reading invariants, serializer readback validation, and destination safety

## [0.1.6.43-dev] - 2026-08-29

### Changed
- Enforce strict duplicate version reading/writing invariants, safe_unbundle destination verification, and 64-char hash table rendering

## [0.1.6.42-dev] - 2026-08-29

### Changed
- Align with Developer Directive & Implementation Specification v8.6: implement two-tier DWIM argument scanner, primary default selection, shadow-alt branching, and subparser synchronization

## [0.1.6.41-dev] - 2026-08-29

### Changed
- Align with Developer Directive & Implementation Specification v8.6: robust standalone in-memory BundleFinder bootstrap for Tier 1 universal scanner

## [0.1.6.40-dev] - 2026-08-29

### Changed
- Align with Developer Directive & Implementation Specification v8.6: implement two-tier DWIM argument scanner, primary default selection, shadow-alt branching, and polymorphic flag state machine

## [0.1.6.39-dev] - 2026-08-29

### Changed
- Align with Developer Directive & Implementation Specification v8.6: fix dotfile preservation, primary default selection, shadow-alt branching, and two-tier DWIM argument scanner

## [0.1.6.38-dev] - 2026-08-29

### Changed
- Align with Developer Directive & Implementation Specification v8.6: fix dotfile preservation, primary default selection, shadow-alt branching, and two-tier DWIM argument scanner

## [0.1.6.16-dev] - 2026-08-28

### Changed
- Complete v7.4 implementation and CLI isolation fixes

## [0.1.6.15-dev] - 2026-08-28

### Changed
- Complete v7.4 VersionSpace and portability implementation

## [0.1.6.14-dev] - 2026-08-28

### Changed
- Implement v7.4 VersionSpace semantics and portability rules

## [0.1.6.13-dev] - 2026-08-28

### Changed
- fix VersionSpace baseline semantics

## [0.1.6.13-dev] - 2026-08-28

### Changed
- Implement v7.4 multi-stream packaging and dispatch.

## [0.1.6.12-dev] - 2026-08-28

### Changed
- Implement multi-stream version reconciliation, self-contained dispatch, and packaging invariants per v7.4 specification.

## [0.1.6.11-dev] - 2026-08-27

### Changed
- Complete implementation of multi-stream version reconciliation, self-contained applet dispatch, and packaging invariants per Implementation Specification (v4).
- Retroactively normalize development revision history to 4th-digit semantic revision scheme.
- Enforce standalone bundle self-containment and lazy CLI version evaluation.

## [0.1.6.10-dev] - 2026-08-27 [retroactive version number repair]

### Changed
- Maintenance release and baseline synchronization.

## [0.1.6.9-dev] - 2026-08-27 [retroactive version number repair]

### Changed
- Maintenance release and baseline synchronization.

## [0.1.6.8-dev] - 2026-08-27 [retroactive version number repair]

### Changed
- Universalize CLI dispatch, argv0 semantics, and startup behavior.

## [0.1.6.7-dev] - 2026-08-27 [retroactive version number repair]

### Changed
- Finalize universal CLI dispatch and argv0 semantics.

## [0.1.6.6-dev] - 2026-08-27 [retroactive version number repair]

### Changed
- Fix universal dispatch aliases and apply argv0 routing consistently across CLI entry points.

## [0.1.6.5-dev] - 2026-08-27 [retroactive version number repair]

### Changed
- Universalize CLI dispatch and argv0 handling across all entry points.

## [0.1.6.4-dev] - 2026-08-27 [retroactive version number repair]

### Changed
- Universalize CLI dispatch and argv0 handling.

## [0.1.6.3-dev] - 2026-08-26

### Changed
- Add lazy CLI version evaluation, single-pass bundle asset extraction, and mtime-fingerprinted integrity hash caching.

## [0.1.6.2-dev] - 2026-08-26

### Changed
- Add streaming WAV audio inspection parser and auto-detection heuristics.

## [0.1.6.1-dev] - 2026-08-25

### Changed
- Refactor T88 and PC-88 cassette demodulation pipelines.

## [0.1.6.0-dev] - 2026-08-23

### Changed
- Initial multi-stream version reconciliation baseline.
