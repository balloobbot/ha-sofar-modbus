# Releasing

`CHANGELOG.md` is the source of truth for what a release contains. The GitHub
Release notes are derived from it, not written separately — that's what went
wrong for v0.3.13 and v0.3.14 (release notes were written directly via `gh
release create`, and the matching `CHANGELOG.md` entry never got added).
Follow this order every time so the two can't drift apart again:

1. Bump `version` in `custom_components/sofar_modbus/manifest.json`.
2. Add the matching section to `CHANGELOG.md`, **before** tagging:
   ```markdown
   ## [X.Y.Z] - YYYY-MM-DD

   ### Added / Changed / Fixed
   <!-- whichever apply -->
   - ...

   ### Verification
   - <what was actually run: test suites, ruff, mypy>
   ```
3. Commit both files together.
4. Tag and release, using the CHANGELOG section's `### Added`/`### Changed`/
   `### Fixed` bullets verbatim as the release notes — everything except
   `### Verification`, which is an internal engineering note, not
   user-facing. Tags are unprefixed (`X.Y.Z`, matching `manifest.json` and
   Core's own tag format) — versions before 0.3.15 were tagged `vX.Y.Z`:
   ```bash
   git tag X.Y.Z
   git push origin X.Y.Z
   gh release create X.Y.Z --title X.Y.Z --notes "<CHANGELOG section content minus ### Verification>"
   ```

See `CHANGELOG.md`'s header for the `MINOR`/`PATCH` versioning rule (while
the major version is `0`): a `MINOR` bump is new user-facing capability (a
new platform, new entities reachable from Home Assistant); a `PATCH` bump is
a fix with no new capability.
