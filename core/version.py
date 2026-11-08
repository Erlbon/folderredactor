"""
Single source of truth for the app version/release label. Fed by bump_version.py (redactor_common's
core/version_bump.py), which reads the real system clock: never hand-edit APP_VERSION.
"""

APP_NAME = "The \u2132older Redactor"  # "\u2132" = Ⅎ, TURNED CAPITAL F (Letterlike Symbols), the first letter turned like Ʌideo
APP_VERSION = "2026-11-08#01"
RELEASE_LABEL = "v0.1"
APP_REPO_URL = "https://github.com/erlbon/folderredactor"
