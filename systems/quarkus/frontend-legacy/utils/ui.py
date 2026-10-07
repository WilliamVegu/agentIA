"""UI Component Library for AgentIA Streamlit application (Adapted from TalentIA)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import streamlit as st


def load_css(css_path: Optional[str | Path] = None) -> None:
    """Injects custom CSS stylesheet into the Streamlit app."""
    if css_path is None:
        css_path = Path(__file__).resolve().parent.parent / "assets" / "styles.css"
    else:
        css_path = Path(css_path)

    if css_path.exists():
        css_content = css_path.read_text(encoding="utf-8")
        st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    else:
        st.warning(f"CSS stylesheet not found at: {css_path}")


def render_header(
    title: str,
    subtitle: Optional[str] = None,
    badge: Optional[str] = None,
) -> None:
    """Renders the custom hero header banner with TalentIA gradient styling."""
    sub_html = f"<p>{subtitle}</p>" if subtitle else ""
    badge_html = f'<div class="header-badge">{badge}</div>' if badge else ""
    st.markdown(
        f"""
        <div class="app-header">
            <h1>{title}</h1>
            {sub_html}
            {badge_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def card_open(title: Optional[str] = None, icon: Optional[str] = None) -> str:
    """Returns or renders the opening HTML container for an .app-card."""
    title_html = ""
    if title:
        icon_str = f"<span>{icon}</span> " if icon else ""
        title_html = f'<div class="app-card-title">{icon_str}{title}</div>'

    html = f'<div class="app-card">{title_html}'
    st.markdown(html, unsafe_allow_html=True)
    return html


def card_close() -> str:
    """Returns or renders the closing HTML container for an .app-card."""
    html = "</div>"
    st.markdown(html, unsafe_allow_html=True)
    return html


def render_status_badge(label: str, type: str = "primary") -> str:
    """Returns styled HTML pill badge string. Types: primary, success, warning, danger, neutral."""
    type_class = f"app-pill-{type.lower()}"
    return f'<span class="app-pill {type_class}">{label}</span>'

