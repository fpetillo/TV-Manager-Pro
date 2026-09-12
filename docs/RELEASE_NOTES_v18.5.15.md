## 18.5.15 — CI pytest dependency alignment

### Fix
- Added `requirements-test.txt` with `pytest==8.4.2`.
- Updated CI workflow to install from `requirements-test.txt`.
- Resolves GitHub Actions failures where unittest discovery imports test modules that reference `pytest`.

### Why this was failing
- CI runs `python -m unittest discover -s tests -v`.
- Several test modules import `pytest` at module scope (for fixtures/context managers), so missing pytest caused import-time failures before tests executed.

### Validation
- `PYTHONPATH=. python3 -m unittest discover -s tests -v` passed: 130/130.
- CI workflow was updated to install `requirements-test.txt`; a remote GitHub Actions rerun was not executed from this sandbox session.
