"""Sphinx configuration."""

project = "edutap.heidi_api"
author = "eduTAP"

extensions = ["myst_parser", "sphinx.ext.autodoc", "sphinx.ext.napoleon"]

myst_enable_extensions = ["colon_fence", "deflist"]

html_theme = "alabaster"
exclude_patterns = ["_build", "superpowers/**"]
