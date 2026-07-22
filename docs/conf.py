"""Sphinx configuration for the closecity Python documentation."""

import importlib.metadata
import os

project = "closecity"
author = "Nathaniel Henry"
copyright = "2026, Henry Spatial Analysis"  # noqa: A001
try:
    release = importlib.metadata.version("closecity")
except importlib.metadata.PackageNotFoundError:
    release = "1.0.0"
version = release

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
    "myst_nb",
]

# The getting-started and tutorial pages are executable notebooks. Run them when a
# key is present (on the docs site), and show the code without running it otherwise.
nb_execution_mode = "auto" if os.environ.get("CLOSECITY_KEY") else "off"
nb_execution_timeout = 180
nb_execution_raise_on_error = True

# When the notebooks are not executed (no key), myst-nb cannot infer a highlight
# language for the code cells and warns once per cell. The cells still render with
# python highlighting from the code-cell directive, so silence that one warning.
suppress_warnings = ["myst-nb.lexer"]

autodoc_mock_imports = ["httpx"]
autodoc_member_order = "bysource"
# The SDK docstrings are plain reStructuredText prose with single-backtick
# references; render those as inline code.
default_role = "literal"

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "geopandas": ("https://geopandas.org/en/stable/", None),
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- HTML output (Furo) ------------------------------------------------------

html_theme = "furo"
html_title = f"closecity {release}"
html_logo = "_static/close-logo.png"
html_favicon = "_static/favicon.ico"
html_static_path = ["_static"]
html_css_files = ["custom.css"]

html_theme_options = {
    "source_repository": "https://github.com/henryspatialanalysis/closecity-python/",
    "source_branch": "main",
    "source_directory": "docs/",
    "light_css_variables": {
        "color-brand-primary": "#202a5b",
        "color-brand-content": "#d95a10",
    },
    "dark_css_variables": {
        "color-brand-primary": "#9aa6d6",
        "color-brand-content": "#f5854a",
    },
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/henryspatialanalysis/closecity-python",
            "html": (
                '<svg stroke="currentColor" fill="currentColor" '
                'viewBox="0 0 16 16"><path fill-rule="evenodd" d="M8 0C3.58 0 0 '
                "3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 "
                "0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-"
                ".82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 "
                "1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 "
                "0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 "
                "2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 "
                "2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 "
                "3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 "
                '2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>'
                "</svg>"
            ),
            "class": "",
        },
    ],
}
