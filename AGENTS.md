# FiioControlPy

This is a native Windows Python application for the FiiO BT11. The web mirror
is a separate sibling project named FiioControl; do not add Python app code there.

- Use **uv** for dependencies and Python execution. Keep `uv.lock` updated.
- Keep ordinary device control native; firmware flashing currently delegates
  to FiiO's official updater.
- Preserve both desktop entry points: quick connect and the settings panel.
- Run `uv run python -m unittest discover -s scripts -p 'test_bt11*.py'` for
  protocol or GUI changes.
- Hardware reads are available through `bt11-control.py --diagnose` and
  `connect-bt11.py --status`. Hardware changes must stay within the user's task.
- Do not run pairing removal, reset, automatic pairing or flashing as routine tests.
- Serialize USB operations using the shared Windows mutex. Preserve UI responsiveness
  and restore the previous pairing mode after discovery.
- Validate lengths, setting ranges and addresses before USB writes.
- Avoid committing `.venv`, caches, local diagnostics or mirrored web assets.
