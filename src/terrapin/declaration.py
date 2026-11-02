"""What this version declares beside its roles (W8.1, W4.1): from contract
v25 the whole of what it says about itself -- its catalogue (declared.py),
its settings (settings.py), its pages with the levels each serves and the
tools their typed routes make, on a port fixed here, and its
documentation, the Markdown in `docs/` (`/plugin/docs` in its image), which
a deployment admin reads on its Documentation tab before launching it.
"""

from __future__ import annotations

import meridian

from .declared import CATALOGUE
from .page import TITLE, pages
from .settings import DECLARED

#: The port its pages are served on, on loopback, where its sidecar forwards.
PORT = 8000

DECLARATION = meridian.Declaration(
    settings=DECLARED,
    catalogue=CATALOGUE,
    interface=meridian.Interface(port=PORT, title=TITLE, pages=pages),
    documentation="docs",
)
