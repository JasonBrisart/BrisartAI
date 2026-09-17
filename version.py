"""
File: version.py

Purpose
-------
Single source of truth for BrisartAI's version string. Replaces the
former plain-text version.txt with a real, importable Python module,
so the version can be bumped by editing one Python assignment rather
than a bare text file.

Communication / relationships
------------------------------
- brisart_ai/version_info.py loads this file directly by path (via
  importlib.util) and reads its __version__ attribute. It is
  deliberately loaded by path rather than a plain `import version`,
  since this file lives at the project root, not inside the brisart_ai
  package, and brisart_ai must not depend on the project root being on
  sys.path.
- Every other consumer of the version string (ui/app.py's window
  title, ui/sidebar.py's version label, web/policy.py's outbound
  USER_AGENT) goes through brisart_ai/version_info.py, not this file
  directly -- this file has exactly one reader.

Settings / parameters
----------------------
- __version__ (str): the current release version. Bump this single
  value to change the version everywhere it's displayed (window title,
  sidebar, the outbound USER_AGENT string). No other file needs to be
  touched to release a new version number.

Edge cases
----------
- None -- this module has no logic, only the version string. If this
  file is ever missing, unreadable, or fails to import (a syntax error
  introduced by a bad manual edit, for instance),
  brisart_ai/version_info.py falls back to "0.0.0-unknown" rather than
  raising, so a broken version.py can never crash application startup.

Known limitations
-----------------
- Contains a single string assignment and nothing else; there is no
  logic to fail, and no runtime configuration.
- The value must be bumped by hand at release time; nothing derives or
  validates it automatically.

Examples
--------
    >>> import version
    >>> isinstance(version.__version__, str)
    True
"""
__version__ = "1.2.6"

