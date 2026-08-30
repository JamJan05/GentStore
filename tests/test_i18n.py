"""Guards on the translation catalogues.

The application is bilingual by design, and the way that quietly breaks is not a
wrong translation but a *missing* one: ``lupdate`` fails to find a string, marks
the old entry ``vanished``, ``lrelease`` drops it, and half the window falls back
to English. That happened once already — ``QT_TRANSLATE_NOOP(CONTEXT, …)`` with a
variable in the context slot is invisible to ``lupdate`` — and these tests are
what would have caught it.
"""

from __future__ import annotations

import ast
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from gentstore.ui.pages.registry import CONTEXT, PAGES

SOURCE_DIR = Path(__file__).resolve().parent.parent / "gentstore"

CATALOGUES = sorted((Path(__file__).resolve().parent.parent / "gentstore" / "i18n").glob("*.ts"))


def entries(path: Path) -> list[tuple[str, str, ET.Element]]:
    """Every message as ``(context, source, translation element)``."""
    result = []
    for context in ET.parse(path).getroot():
        name = context.findtext("name") or ""
        for message in context.findall("message"):
            translation = message.find("translation")
            if translation is not None:
                result.append((name, message.findtext("source") or "", translation))
    return result


def test_there_are_catalogues_at_all() -> None:
    assert {path.stem for path in CATALOGUES} == {"gentstore_pl", "gentstore_en"}


@pytest.mark.parametrize("path", CATALOGUES, ids=lambda p: p.stem)
def test_no_message_is_unfinished_or_vanished(path: Path) -> None:
    flagged = [
        f"{context}/{source!r}: {element.get('type')}"
        for context, source, element in entries(path)
        if element.get("type")
    ]
    assert not flagged, (
        "run `python tools/i18n.py update`, translate these, then `compile`:\n"
        + "\n".join(flagged)
    )


@pytest.mark.parametrize("path", CATALOGUES, ids=lambda p: p.stem)
def test_every_message_has_text(path: Path) -> None:
    empty = [
        f"{context}/{source!r}"
        for context, source, element in entries(path)
        if not (element.text or "").strip() and not element.findall("numerusform")
    ]
    assert not empty


@pytest.mark.parametrize("path", CATALOGUES, ids=lambda p: p.stem)
def test_the_page_titles_are_in_the_catalogue(path: Path) -> None:
    """The sidebar reads these; losing them leaves the navigation in English."""
    found = {source for context, source, _ in entries(path) if context == CONTEXT}
    missing = {spec.title_source for spec in PAGES} - found
    assert not missing, f"page titles missing from the {CONTEXT} context: {sorted(missing)}"


@pytest.mark.parametrize("path", CATALOGUES, ids=lambda p: p.stem)
def test_no_message_appears_twice_in_a_context(path: Path) -> None:
    """Two entries for one string means two extractors were mixed.

    pylupdate6 and lupdate write incompatible catalogues; refreshing with the
    other one marks every existing message ``vanished`` and adds a fresh
    ``unfinished`` twin. ``tools/i18n.py`` pins the extractor for that reason,
    and this is the check that the pin held.
    """
    seen: dict[tuple[str, str], int] = {}
    for context, source, _element in entries(path):
        seen[(context, source)] = seen.get((context, source), 0) + 1
    duplicated = [key for key, count in seen.items() if count > 1]
    assert not duplicated, f"duplicated messages: {duplicated}"


@pytest.mark.parametrize("path", CATALOGUES, ids=lambda p: p.stem)
def test_every_message_with_a_count_is_a_plural_form(path: Path) -> None:
    """``%n`` in a message means Qt has to choose an ending, so it must be numerus.

    The extractor decides that from the *shape of the call*, not from the text:
    ``self.tr("%n new", "", count)`` is a plural, the same call nested inside a
    dict literal came out as an ordinary string. A message containing ``%n``
    that is not marked numerus has exactly one form and gets Polish endings
    wrong for two thirds of all values.
    """
    flat = [
        f"{context}/{source!r}"
        for context, source, element in entries(path)
        if "%n" in source and not element.findall("numerusform")
    ]
    assert not flat, "these carry %n but have no plural forms:\n" + "\n".join(flat)


def test_polish_plurals_have_three_forms() -> None:
    """Polish distinguishes one / few / many, so ``%n`` needs three forms."""
    path = next(p for p in CATALOGUES if p.stem.endswith("_pl"))
    wrong = [
        f"{context}/{source!r}: {len(element.findall('numerusform'))} form(s)"
        for context, source, element in entries(path)
        if element.findall("numerusform") and len(element.findall("numerusform")) != 3
    ]
    assert not wrong


def test_translatable_strings_are_always_marked_with_self_tr() -> None:
    """``window.tr("…")`` is silently skipped by the extractor.

    ``tr()`` is a method on QObject and its context is the class it is called
    *in*. The extractor reads the source as text: it recognises ``self.tr(…)``
    and nothing else. A call on another object compiles, runs and returns the
    untranslated string forever — which is how a "Running as root" dialog
    ended up being English in both languages until it was moved onto the
    window it belongs to.
    """
    offenders = []
    for source in sorted(SOURCE_DIR.rglob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            if not isinstance(function, ast.Attribute) or function.attr != "tr":
                continue
            if not node.args or not isinstance(node.args[0], ast.Constant):
                continue
            receiver = function.value
            if isinstance(receiver, ast.Name) and receiver.id == "self":
                continue
            where = f"{source.relative_to(SOURCE_DIR)}:{node.lineno}"
            offenders.append(f"{where}: {ast.unparse(function)}(…)")
    assert not offenders, "translatable text must go through self.tr():\n" + "\n".join(offenders)


#: Methods whose argument ends up in front of somebody.
_USER_VISIBLE = frozenset(
    {
        "setText",
        "setToolTip",
        "setWindowTitle",
        "setPlaceholderText",
        "setStatusTip",
        "showMessage",
        "setItemText",
    }
)


def _is_translated(node: ast.AST) -> bool:
    """Whether an argument came from ``tr()`` or is being formatted from it."""
    if isinstance(node, ast.Call):
        function = node.func
        if isinstance(function, ast.Attribute) and function.attr in ("tr", "format"):
            return True
        # untranslated() is the deliberate opposite: text that must read the
        # same in every language. Saying so in the code is what makes the
        # difference reviewable (gentstore/ui/i18n.py).
        if isinstance(function, ast.Name) and function.id == "untranslated":
            return True
        return any(_is_translated(argument) for argument in node.args)
    if isinstance(node, ast.JoinedStr):  # an f-string; its pieces are checked below
        return True
    if isinstance(node, ast.BinOp):
        return _is_translated(node.left) or _is_translated(node.right)
    return False


def test_user_visible_text_goes_through_tr() -> None:
    """A literal handed straight to setText() can never be translated.

    The catalogue only ever contains what ``tr()`` wrapped, so a bare string
    here is a sentence that stays English in Polish for ever — and nothing
    about the code looks wrong. Anything that is genuinely not translatable
    (an atom, a path, a command) is passed as a variable or an f-string, which
    is exactly the distinction this test uses.
    """
    offenders = []
    for source in sorted(SOURCE_DIR.rglob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            if not isinstance(function, ast.Attribute) or function.attr not in _USER_VISIBLE:
                continue
            for argument in node.args:
                if not isinstance(argument, ast.Constant) or not isinstance(argument.value, str):
                    continue
                if not argument.value.strip():
                    continue  # clearing a label
                if _is_translated(argument):
                    continue
                offenders.append(
                    f"{source.relative_to(SOURCE_DIR)}:{node.lineno}: "
                    f"{function.attr}({argument.value!r})"
                )
    assert not offenders, "user-visible text must go through tr():\n" + "\n".join(offenders)


#: The interface speaks Polish; the source does not. Everything a person reads
#: is written in English and translated, so a Polish word in a .py file is
#: either a string that escaped the catalogue or a comment in the wrong place.
_POLISH = "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"


def test_the_source_is_written_in_english() -> None:
    offenders = []
    for source in sorted(SOURCE_DIR.rglob("*.py")):
        for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            found = [character for character in line if character in _POLISH]
            if found:
                offenders.append(f"{source.relative_to(SOURCE_DIR)}:{number}: {line.strip()}")
    assert not offenders, (
        "Polish belongs in gentstore_pl.ts, not in the source:\n" + "\n".join(offenders)
    )
