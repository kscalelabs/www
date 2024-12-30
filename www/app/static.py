"""Defines common utilities for static pages."""

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="www/templates")
