# Changelog

All notable changes to graphulator are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.9.1] - 2026-04-27
### Added
- Help → About dialog in both Graphulator and Paragraphulator, showing
  the app logo, version, Qt/PySide6/Python versions, copyright, and
  project URL.
- `graphulator/_resources.py` with a `resource_path()` helper for
  locating bundled assets across dev, pip-installed, and PyInstaller
  frozen builds.

### Changed
- Runtime PNG icons moved from `misc/` to `src/graphulator/assets/` and
  declared as package data so they ship with the wheel; PyInstaller
  specs updated to bundle them into frozen builds. (`.icns`/`.ico`
  app-bundle icons remain in `misc/` — they're build-time only.)
- Icon lookups in both `main()` entry points now go through
  `resource_path()` instead of walking up from `__file__`, fixing the
  silent "no icon" case under `pip install`.

## [0.9.0] - 2026-04-21
### Added
- Initial public release.
