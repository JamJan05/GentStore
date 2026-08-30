"""Stylesheet generation.

The whole theme is produced from :mod:`gentstore.ui.theme.tokens` so that a colour
or a font size only ever has to change in one place, and so that the font-scale
setting can rebuild the sheet at run time.

Widgets opt into a look through Qt dynamic properties rather than object names,
e.g. ``label.setProperty("role", "caption")`` or ``button.setProperty("variant",
"primary")``. After changing such a property at run time call
:func:`repolish` so Qt re-evaluates the selectors.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from . import tokens as t


def repolish(widget: QWidget) -> None:
    """Re-apply the stylesheet to *widget* after a dynamic property changed."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def build_qss(scale: float = 1.0) -> str:
    """Return the complete application stylesheet at the given font scale."""
    s = t.scaled
    ui = t.font_stack(t.UI_FONT_FAMILIES)
    mono = t.font_stack(t.MONO_FONT_FAMILIES)

    return f"""
/* ---------------------------------------------------------------- base --- */
/* Deliberately no `background` here: Qt does not paint a stylesheet background
   on plain QWidget subclasses, so setting it universally would only apply to
   stock widgets and leave the hand-painted ones (NavItem, chips) inconsistent.
   The window background comes from the palette instead. */
QWidget {{
    color: {t.TEXT};
    font-family: {ui};
    font-size: {s(t.FONT_BASE, scale)}px;
}}
QMainWindow, QDialog {{ background: {t.BG}; }}
QWidget:disabled {{ color: {t.NEUTRAL_700}; }}

/* --------------------------------------------------------------- chrome --- */
QFrame#sidebar {{
    background: {t.SURFACE};
    border: none;
    border-right: 1px solid {t.BORDER};
}}
QWidget#chromeInfo, QLabel#chromeInfo {{
    font-family: {mono};
    font-size: {s(t.FONT_TINY, scale)}px;
    color: {t.NEUTRAL_600};
}}

QToolTip {{
    background: {t.SURFACE};
    color: {t.TEXT};
    border: 1px solid {t.BORDER};
    border-radius: {t.RADIUS_SM}px;
    padding: {t.SPACE_2}px {t.SPACE_3}px;
    font-size: {s(t.FONT_SMALL, scale)}px;
}}

/* ------------------------------------------------------------ menu bar --- */
QMenuBar {{
    background: {t.SURFACE};
    border-bottom: 1px solid {t.BORDER};
    padding: 0 {t.SPACE_4}px;
    font-size: {s(t.FONT_TINY, scale)}px;
}}
QMenuBar::item {{
    background: transparent;
    color: {t.NEUTRAL_300};
    padding: {t.SPACE_2}px {t.SPACE_3}px;
    margin-right: {t.SPACE_3}px;
    border-radius: {t.RADIUS_SM}px;
}}
QMenuBar::item:selected {{ background: {t.NEUTRAL_900}; color: {t.TEXT}; }}
QMenuBar::item:pressed  {{ background: {t.ACCENT_900}; color: {t.TEXT}; }}

QMenu {{
    background: {t.SURFACE};
    border: 1px solid {t.BORDER};
    border-radius: {t.RADIUS_SM}px;
    padding: {t.SPACE_1}px;
    font-size: {s(t.FONT_BASE, scale)}px;
}}
QMenu::item {{
    padding: {t.SPACE_2}px {t.SPACE_6}px {t.SPACE_2}px {t.SPACE_4}px;
    border-radius: {t.RADIUS_SM}px;
    color: {t.NEUTRAL_300};
}}
QMenu::item:selected {{ background: {t.ACCENT_900}; color: {t.TEXT}; }}
QMenu::item:disabled {{ color: {t.NEUTRAL_700}; }}
QMenu::separator {{ height: 1px; background: {t.BORDER}; margin: {t.SPACE_1}px {t.SPACE_2}px; }}
QMenu::indicator {{ width: 13px; height: 13px; margin-left: {t.SPACE_2}px; }}

/* ------------------------------------------------------------- toolbar --- */
QToolBar {{
    background: {t.SURFACE};
    border: none;
    border-bottom: 1px solid {t.BORDER};
    padding: 0 {t.SPACE_3}px;
    spacing: {t.SPACE_2}px;
}}
QToolBar::separator {{
    background: {t.BORDER};
    width: 1px;
    margin: {t.SPACE_2}px {t.SPACE_3}px;
}}
QToolButton {{
    background: transparent;
    color: {t.NEUTRAL_300};
    border: none;
    border-radius: {t.RADIUS_SM}px;
    padding: {t.SPACE_2}px {t.SPACE_3}px;
    font-size: {s(t.FONT_TINY, scale)}px;
}}
QToolButton:hover {{ background: {t.NEUTRAL_900}; color: {t.TEXT}; }}
QToolButton:pressed {{ background: {t.ACCENT_900}; }}

/* ----------------------------------------------------------- statusbar --- */
QStatusBar {{
    background: {t.SURFACE};
    border-top: 1px solid {t.BORDER};
    color: {t.NEUTRAL_600};
    font-family: {mono};
    font-size: {s(t.FONT_MICRO, scale)}px;
}}
QStatusBar::item {{ border: none; }}
QSizeGrip {{ background: transparent; width: 0; height: 0; }}

/* ------------------------------------------------------------- buttons --- */
QPushButton {{
    background: {t.SURFACE};
    color: {t.NEUTRAL_300};
    border: 1px solid {t.BORDER};
    border-radius: {t.RADIUS_SM}px;
    padding: {t.SPACE_2}px {t.SPACE_4}px;
    font-size: {s(t.FONT_TINY, scale)}px;
}}
QPushButton:hover {{ background: {t.NEUTRAL_900}; color: {t.TEXT}; }}
QPushButton:disabled {{ color: {t.NEUTRAL_700}; border-color: {t.NEUTRAL_900}; }}

QPushButton[variant="primary"] {{
    background: {t.ACCENT};
    color: {t.BG};
    border-color: {t.ACCENT};
    font-weight: 600;
}}
QPushButton[variant="primary"]:hover {{ background: {t.ACCENT_400}; }}
QPushButton[variant="primary"]:disabled {{ background: {t.ACCENT_800}; color: {t.NEUTRAL_600}; }}

QPushButton[variant="ghost"] {{ background: transparent; border-color: transparent; }}
QPushButton[variant="ghost"]:hover {{ background: {t.NEUTRAL_900}; }}

QPushButton[variant="danger"] {{ border-color: {t.ERR}; color: {t.ERR}; }}
QPushButton[variant="danger"]:hover {{ background: {t.NEUTRAL_900}; }}

/* -------------------------------------------------------------- inputs --- */
QLineEdit, QPlainTextEdit, QTextEdit {{
    background: {t.SURFACE};
    border: 1px solid {t.BORDER};
    border-radius: {t.RADIUS_SM}px;
    padding: {t.SPACE_2}px {t.SPACE_3}px;
    selection-background-color: {t.ACCENT_800};
    selection-color: {t.TEXT};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border-color: {t.ACCENT_600}; }}
QLineEdit[role="search"] {{ background: {t.SURFACE}; font-size: {s(t.FONT_BASE, scale)}px; }}

QComboBox {{
    background: {t.SURFACE};
    border: 1px solid {t.BORDER};
    border-radius: {t.RADIUS_SM}px;
    padding: {t.SPACE_2}px {t.SPACE_3}px;
}}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background: {t.SURFACE};
    border: 1px solid {t.BORDER};
    selection-background-color: {t.ACCENT_900};
}}

QCheckBox {{ spacing: {t.SPACE_2}px; }}
QCheckBox::indicator {{
    width: 15px; height: 15px;
    border: 1px solid {t.NEUTRAL_700};
    border-radius: 3px;
    background: transparent;
}}
QCheckBox::indicator:checked {{ background: {t.ACCENT}; border-color: {t.ACCENT}; }}
QCheckBox::indicator:disabled {{ border-color: {t.NEUTRAL_800}; }}

/* ------------------------------------------------------ split screens --- */
/* The list pane keeps the page background so the details side, which is the
   same colour, reads as one surface split by a single rule. */
QFrame#listPane {{
    background: {t.BG};
    border: none;
    border-right: 1px solid {t.BORDER};
}}
QFrame#searchHeader {{
    background: {t.BG};
    border: none;
    border-bottom: 1px solid {t.BORDER};
}}
QFrame#searchBox {{
    background: {t.SURFACE};
    border: 1px solid {t.BORDER};
    border-radius: {t.RADIUS_SM}px;
}}
QFrame#searchBox:focus-within {{ border-color: {t.ACCENT_600}; }}
QLineEdit#searchInput {{
    background: transparent;
    border: none;
    padding: 0;
    font-size: {s(t.FONT_BASE, scale)}px;
    color: {t.TEXT};
}}
QListView#packageList {{
    background: {t.BG};
    border: none;
    padding: {t.SPACE_2}px 0;
}}
QScrollArea#detailPane, QWidget#detailContent {{ background: {t.BG}; }}

QLabel#packageAtom {{
    font-family: {mono};
    font-size: {s(t.FONT_H1_MONO, scale)}px;
    color: {t.TEXT};
}}
/* Dashed rather than solid: this is a note about what the interface is doing,
   not a warning about the system. */
QLabel#hiddenNote {{
    border: 1px dashed {t.ACCENT_700};
    border-radius: {t.RADIUS_SM}px;
    margin: {t.SPACE_3}px {t.SPACE_4}px;
    font-size: {s(t.FONT_SMALL, scale)}px;
    color: {t.ACCENT_300};
}}

/* ----------------------------------------------------------- the log --- */
QDockWidget {{
    color: {t.NEUTRAL_600};
    font-size: {s(t.FONT_MICRO, scale)}px;
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}}
QDockWidget::title {{
    background: {t.SURFACE};
    border-top: 1px solid {t.BORDER};
    padding: {t.SPACE_1}px {t.SPACE_4}px;
    text-align: left;
}}
QFrame#logView {{ background: {t.SURFACE}; border: none; }}
QLabel#logCommand {{
    font-family: {mono};
    font-size: {s(t.FONT_SMALL, scale)}px;
    color: {t.NEUTRAL_300};
}}
QPlainTextEdit#logOutput {{
    background: {t.BG};
    border: 1px solid {t.BORDER};
    border-radius: {t.RADIUS_SM}px;
    padding: {t.SPACE_2}px {t.SPACE_3}px;
    font-family: {mono};
    font-size: {s(t.FONT_SMALL, scale)}px;
    color: {t.NEUTRAL_300};
}}

/* ----------------------------------------------------------- USE flags --- */
QFrame#useFlagsPanel {{
    background: {t.SURFACE};
    border: 1px solid {t.BORDER};
    border-radius: {t.RADIUS_MD}px;
}}
QFrame#useFlagsHeader {{
    background: transparent;
    border: none;
    border-bottom: 1px solid {t.BORDER};
}}
QWidget#requirementsBlock {{ background: {t.BG}; }}
QLabel#requirementExpression {{
    font-family: {mono};
    font-size: {s(t.FONT_SMALL, scale)}px;
    color: {t.NEUTRAL_300};
}}
QLabel#requirementExpression[state="err"] {{ color: {t.ERR}; }}

QFrame#useFlagRow {{ background: transparent; border: none; }}
QFrame#useFlagRow:hover {{ background: {t.NEUTRAL_900}; }}
QLabel#useFlagName {{
    font-family: {mono};
    font-size: {s(t.FONT_BASE, scale)}px;
    font-weight: 600;
    color: {t.TEXT};
}}
/* A masked flag is shown, not hidden: "you cannot change this" is information.
   Dimming the name says so without a sentence. */
QFrame#useFlagRow[locked="yes"] QLabel#useFlagName {{ color: {t.NEUTRAL_600}; }}
QFrame#useFlagRow[changed="yes"] QLabel#useFlagName {{ color: {t.ACCENT_200}; }}
QLabel#useFlagOrigin {{
    font-family: {mono};
    font-size: {s(t.FONT_NANO, scale)}px;
    background: {t.NEUTRAL_900};
    color: {t.NEUTRAL_500};
    border-radius: {t.RADIUS_SM}px;
    padding: 1px {t.SPACE_2}px;
}}
QFrame#useFlagRow[changed="yes"] QLabel#useFlagOrigin {{
    background: {t.ACCENT_800};
    color: {t.ACCENT_200};
}}
QWidget#useFlagDetails {{ background: {t.BG}; }}

/* ------------------------------------------------ masks and licences --- */
/* A left edge in the semantic colour, the way the canvas marks anything the
   user has to make a decision about. Amber for the routine cases, red for the
   two that deserve a second thought. */
QFrame#blockNotice, QFrame#requiredChanges {{
    background: {t.SURFACE};
    border: 1px solid {t.BORDER};
    border-left: 2px solid {t.WARN};
    border-radius: {t.RADIUS_SM}px;
}}
QFrame#blockNotice[severity="high"] {{ border-left-color: {t.ERR}; }}
/* The maintainer's own words, laid out as they wrote them. */
QLabel#maskComment {{
    font-family: {mono};
    font-size: {s(t.FONT_SMALL, scale)}px;
    color: {t.NEUTRAL_300};
    background: {t.BG};
    border-radius: {t.RADIUS_SM}px;
    padding: {t.SPACE_3}px;
}}
QPlainTextEdit#licenceText {{
    background: {t.BG};
    border: 1px solid {t.BORDER};
    border-radius: {t.RADIUS_SM}px;
    padding: {t.SPACE_3}px;
    font-family: {mono};
    font-size: {s(t.FONT_SMALL, scale)}px;
    color: {t.NEUTRAL_300};
}}

QFrame#maskSection {{
    background: {t.SURFACE};
    border: 1px solid {t.BORDER};
    border-radius: {t.RADIUS_MD}px;
}}
QLabel#maskSectionTitle {{
    font-family: {mono};
    font-size: {s(t.FONT_MEDIUM, scale)}px;
    color: {t.TEXT};
}}
QFrame#maskEntry {{ background: transparent; border: none; }}
QFrame#maskEntry:hover {{ background: {t.NEUTRAL_900}; }}
QLabel#maskEntryAtom {{
    font-family: {mono};
    font-size: {s(t.FONT_SMALL, scale)}px;
    color: {t.NEUTRAL_200};
}}

/* ---------------------------------------------------- repositories --- */
QFrame#repoRow, QFrame#catalogueRow {{
    background: transparent;
    border: none;
    border-left: 2px solid transparent;
    border-bottom: 1px solid {t.NEUTRAL_900};
}}
QFrame#repoRow:hover, QFrame#catalogueRow:hover {{ background: {t.NEUTRAL_900}; }}
QFrame#repoRow[selected="yes"] {{
    background: {t.ACCENT_900};
    border-left-color: {t.ACCENT};
}}
QLabel#repoRowName {{
    font-family: {mono};
    font-size: {s(t.FONT_BASE, scale)}px;
    font-weight: 600;
    color: {t.NEUTRAL_200};
}}
/* Official and unofficial are told apart by colour, the same way repository
   badges are, so the distinction reads the same everywhere. */
QLabel#repoQuality {{
    font-family: {mono};
    font-size: {s(t.FONT_NANO, scale)}px;
    background: {t.ACCENT_800};
    color: {t.ACCENT_200};
    border-radius: {t.RADIUS_SM}px;
    padding: 1px {t.SPACE_2}px;
}}
QLabel#repoQuality[official="no"] {{
    background: {t.NEUTRAL_900};
    color: {t.WARN};
}}
QLabel#addOverlayWarning {{
    background: {t.BG};
    border: 1px solid {t.ERR};
    border-radius: {t.RADIUS_SM}px;
    padding: {t.SPACE_3}px;
    color: {t.NEUTRAL_300};
    font-size: {s(t.FONT_SMALL, scale)}px;
}}

/* ------------------------------------------------------- the update --- */
QFrame#stepRow {{
    background: transparent;
    border: none;
    border-left: 2px solid transparent;
    border-bottom: 1px solid {t.NEUTRAL_900};
}}
QFrame#stepRow:hover {{ background: {t.NEUTRAL_900}; }}
QFrame#stepRow[selected="yes"] {{
    background: {t.ACCENT_900};
    border-left-color: {t.ACCENT};
}}
QLabel#stepNumber {{
    font-family: {mono};
    font-size: {s(t.FONT_SMALL, scale)}px;
    color: {t.NEUTRAL_600};
}}
QLabel#stepTitle {{ font-size: {s(t.FONT_BASE, scale)}px; color: {t.NEUTRAL_200}; }}
/* A finished step keeps its tick but stops competing for attention. */
QFrame#stepRow[state="done"] QLabel#stepTitle,
QFrame#stepRow[state="clear"] QLabel#stepTitle {{ color: {t.NEUTRAL_500}; }}
QFrame#stepRow[state="failed"] QLabel#stepTitle {{ color: {t.ERR}; }}
QFrame#stepRow[state="running"] QLabel#stepTitle {{ color: {t.ACCENT_200}; }}

QTableView#previewTable {{
    background: {t.BG};
    alternate-background-color: {t.SURFACE};
    border: 1px solid {t.BORDER};
    border-radius: {t.RADIUS_SM}px;
    gridline-color: {t.NEUTRAL_900};
    font-family: {mono};
    font-size: {s(t.FONT_SMALL, scale)}px;
    color: {t.NEUTRAL_300};
}}
QTableView#previewTable::item {{ padding: {t.SPACE_1}px {t.SPACE_2}px; }}

QFrame#newsEntry {{
    background: transparent;
    border: none;
    border-left: 2px solid transparent;
    border-bottom: 1px solid {t.NEUTRAL_900};
}}
QFrame#newsEntry[unread="yes"] {{ border-left-color: {t.ACCENT}; }}
QLabel#newsTitle {{ font-size: {s(t.FONT_BASE, scale)}px; color: {t.NEUTRAL_200}; }}
QFrame#newsEntry[unread="no"] QLabel#newsTitle {{ color: {t.NEUTRAL_500}; }}
QLabel#newsBody {{
    font-family: {mono};
    font-size: {s(t.FONT_SMALL, scale)}px;
    color: {t.NEUTRAL_300};
    background: {t.BG};
    border-radius: {t.RADIUS_SM}px;
    padding: {t.SPACE_3}px;
}}

/* ------------------------------------------- configuration files --- */
QFrame#cfgRow {{
    background: transparent;
    border: none;
    border-left: 2px solid transparent;
    border-bottom: 1px solid {t.NEUTRAL_900};
}}
QFrame#cfgRow:hover {{ background: {t.NEUTRAL_900}; }}
QFrame#cfgRow[selected="yes"] {{
    background: {t.ACCENT_900};
    border-left-color: {t.ACCENT};
}}
QLabel#cfgName {{
    font-family: {mono};
    font-size: {s(t.FONT_BASE, scale)}px;
    font-weight: 600;
    color: {t.NEUTRAL_200};
}}
QFrame#diffView {{ background: transparent; border: none; }}
QPlainTextEdit#diffBody, QPlainTextEdit#mergeEditor {{
    background: {t.BG};
    border: 1px solid {t.BORDER};
    border-radius: {t.RADIUS_SM}px;
    padding: {t.SPACE_2}px {t.SPACE_3}px;
    font-family: {mono};
    font-size: {s(t.FONT_SMALL, scale)}px;
    color: {t.NEUTRAL_300};
}}
/* The editable one is marked: it is the only text field in the application
   whose contents become a system file. */
QPlainTextEdit#mergeEditor {{ border-color: {t.ACCENT_700}; }}

/* ------------------------------------------------ make.conf and profile --- */
QFrame#variableRow {{
    background: {t.SURFACE};
    border: 1px solid {t.BORDER};
    border-radius: {t.RADIUS_MD}px;
}}
QLabel#variableName {{
    font-family: {mono};
    font-size: {s(t.FONT_MEDIUM, scale)}px;
    font-weight: 600;
    color: {t.TEXT};
}}
QLineEdit#variableField {{
    background: {t.BG};
    font-family: {mono};
    font-size: {s(t.FONT_SMALL, scale)}px;
    color: {t.NEUTRAL_200};
}}

QFrame#profileRow {{
    background: transparent;
    border: none;
    border-left: 2px solid transparent;
    border-bottom: 1px solid {t.NEUTRAL_900};
}}
QFrame#profileRow:hover {{ background: {t.NEUTRAL_900}; }}
QFrame#profileRow[current="yes"] {{
    background: {t.ACCENT_900};
    border-left-color: {t.ACCENT};
}}
QLabel#profilePath {{
    font-family: {mono};
    font-size: {s(t.FONT_SMALL, scale)}px;
    color: {t.NEUTRAL_200};
}}

/* --------------------------------------------- elog and the world set --- */
QFrame#elogRow, QFrame#worldRow, QFrame#installedRow {{
    background: transparent;
    border: none;
    border-left: 2px solid transparent;
    border-bottom: 1px solid {t.NEUTRAL_900};
}}
QFrame#elogRow:hover, QFrame#worldRow:hover, QFrame#installedRow:hover {{
    background: {t.NEUTRAL_900};
}}
QFrame#elogRow[selected="yes"] {{
    background: {t.ACCENT_900};
    border-left-color: {t.ACCENT};
}}
/* The left edge carries the severity, so a page of messages can be skimmed
   without reading any of them. */
QFrame#elogRow[severity="error"] {{ border-left-color: {t.ERR}; }}
QFrame#elogRow[severity="warn"] {{ border-left-color: {t.WARN}; }}
QFrame#elogRow[severity="qa"] {{ border-left-color: {t.ACCENT_700}; }}
QLabel#elogPackage, QLabel#worldAtom, QLabel#installedName {{
    font-family: {mono};
    font-size: {s(t.FONT_SMALL, scale)}px;
    color: {t.NEUTRAL_200};
}}
QLabel#elogSeverity {{
    font-family: {mono};
    font-size: {s(t.FONT_NANO, scale)}px;
    color: {t.NEUTRAL_500};
}}
QLabel#elogSeverity[severity="error"] {{ color: {t.ERR}; }}
QLabel#elogSeverity[severity="warn"] {{ color: {t.WARN}; }}
QLabel#elogSeverity[severity="qa"] {{ color: {t.ACCENT_300}; }}
QPlainTextEdit#elogBody {{
    background: {t.BG};
    border: 1px solid {t.BORDER};
    border-radius: {t.RADIUS_SM}px;
    padding: {t.SPACE_3}px;
    font-family: {mono};
    font-size: {s(t.FONT_SMALL, scale)}px;
    color: {t.NEUTRAL_300};
}}
/* An entry that names a package which is not installed any more: the atom is
   still protecting something that has gone. */
QFrame#worldRow[satisfied="no"] QLabel#worldAtom {{ color: {t.WARN}; }}

/* -------------------------------------------------- the write preview --- */
QFrame#writePreview {{
    background: {t.BG};
    border: none;
    border-top: 1px solid {t.BORDER};
}}
QLabel#writePath {{
    font-family: {mono};
    font-size: {s(t.FONT_MICRO, scale)}px;
    color: {t.NEUTRAL_600};
}}
/* The line itself sits in a frame of its own: it is the one piece of text on
   the screen that is about to become a change to the system. */
QLabel#writeLine {{
    font-family: {mono};
    font-size: {s(t.FONT_SMALL, scale)}px;
    color: {t.TEXT};
    background: {t.SURFACE};
    border: 1px solid {t.BORDER};
    border-radius: {t.RADIUS_SM}px;
    padding: {t.SPACE_2}px {t.SPACE_3}px;
}}
QLabel#writeReport {{
    font-family: {mono};
    font-size: {s(t.FONT_SMALL, scale)}px;
    background: {t.SURFACE};
    border: 1px solid {t.BORDER};
    border-left: 2px solid {t.NEUTRAL_700};
    border-radius: {t.RADIUS_SM}px;
    padding: {t.SPACE_2}px {t.SPACE_3}px;
    color: {t.NEUTRAL_300};
}}
QLabel#writeReport[state="ok"] {{ border-left-color: {t.OK}; }}
QLabel#writeReport[state="err"] {{ border-left-color: {t.ERR}; }}

/* -------------------------------------------------------------- frames --- */
QFrame[role="card"] {{
    background: {t.SURFACE};
    border: 1px solid {t.BORDER};
    border-radius: {t.RADIUS_MD}px;
}}
QFrame[role="pane"] {{ background: {t.SURFACE}; border: none; }}
QFrame[role="hline"] {{ background: {t.BORDER}; border: none; max-height: 1px; }}
QFrame[role="vline"] {{ background: {t.BORDER}; border: none; max-width: 1px; }}

/* -------------------------------------------------------------- labels --- */
QLabel {{ background: transparent; }}
QLabel[role="heading"] {{
    font-size: {s(t.FONT_H1, scale)}px;
    color: {t.TEXT};
}}
QLabel[role="subheading"] {{
    font-size: {s(t.FONT_H2, scale)}px;
    color: {t.TEXT};
}}
QLabel[role="lead"] {{
    font-size: {s(t.FONT_MEDIUM, scale)}px;
    color: {t.NEUTRAL_300};
}}
QLabel[role="body"] {{
    font-size: {s(t.FONT_BASE, scale)}px;
    color: {t.NEUTRAL_400};
}}
QLabel[role="caption"] {{
    font-size: {s(t.FONT_SMALL, scale)}px;
    color: {t.NEUTRAL_600};
}}
QLabel[role="section"] {{
    font-size: {s(t.FONT_MICRO, scale)}px;
    color: {t.NEUTRAL_600};
}}
QLabel[role="mono"] {{
    font-family: {mono};
    font-size: {s(t.FONT_TINY, scale)}px;
    color: {t.NEUTRAL_600};
}}
QLabel[role="mono-strong"] {{
    font-family: {mono};
    font-size: {s(t.FONT_BASE, scale)}px;
    color: {t.TEXT};
}}
QLabel[role="mono-accent"] {{
    font-family: {mono};
    font-size: {s(t.FONT_SMALL, scale)}px;
    color: {t.ACCENT_300};
}}
QLabel[state="ok"] {{ color: {t.OK}; }}
QLabel[state="warn"] {{ color: {t.WARN}; }}
QLabel[state="err"] {{ color: {t.ERR}; }}

/* ------------------------------------------------------------ scrolling --- */
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

QScrollBar:vertical {{ background: transparent; width: 9px; margin: 0; }}
QScrollBar::handle:vertical {{
    background: {t.NEUTRAL_800};
    border-radius: 4px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: {t.NEUTRAL_700}; }}
QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 0; }}
QScrollBar::handle:horizontal {{
    background: {t.NEUTRAL_800};
    border-radius: 4px;
    min-width: 28px;
}}
QScrollBar::handle:horizontal:hover {{ background: {t.NEUTRAL_700}; }}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0; height: 0; background: none; border: none;
}}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

/* --------------------------------------------------------------- views --- */
QAbstractItemView {{
    background: {t.BG};
    border: 1px solid {t.BORDER};
    border-radius: {t.RADIUS_SM}px;
    outline: none;
    selection-background-color: {t.ACCENT_900};
    selection-color: {t.TEXT};
    alternate-background-color: {t.SURFACE};
}}
QHeaderView::section {{
    background: {t.SURFACE};
    color: {t.NEUTRAL_600};
    border: none;
    border-bottom: 1px solid {t.BORDER};
    padding: {t.SPACE_2}px {t.SPACE_3}px;
    font-size: {s(t.FONT_MICRO, scale)}px;
}}
QSplitter::handle {{ background: {t.BORDER}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

/* ------------------------------------------------------------ progress --- */
QProgressBar {{
    background: {t.NEUTRAL_900};
    border: none;
    border-radius: 2px;
    height: 4px;
    text-align: center;
}}
QProgressBar::chunk {{ background: {t.ACCENT}; border-radius: 2px; }}
"""
