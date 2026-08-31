# GentStore — graphical frontend for Portage
# Copyright (C) 2026  JamJan05
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Parsing and checking ``REQUIRED_USE``.

``REQUIRED_USE`` is the ebuild's statement of which combinations of USE flags
make sense. Portage can already answer "is this combination legal" with a single
boolean, and that is exactly the answer that is no use in an interface: somebody
who has just ticked a box needs to know *which* rule they broke and what would
satisfy it. So the expression is parsed here into a small tree that can be
evaluated one requirement at a time.

The grammar, from the package manager specification:

===================  ==========================================================
``flag``             the flag must be enabled
``!flag``            the flag must be disabled
``( … )``            all of the enclosed requirements
``|| ( … )``         at least one of them
``^^ ( … )``         exactly one of them
``?? ( … )``         at most one of them
``flag? ( … )``      the enclosed requirements apply only when ``flag`` is on
``!flag? ( … )``     …only when it is off
===================  ==========================================================

Groups nest, so the parser is recursive; everything else is a flat scan.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from dataclasses import dataclass


class RequiredUseError(ValueError):
    """The expression could not be parsed."""


class Node(ABC):
    """One requirement, or a group of them."""

    @abstractmethod
    def is_satisfied(self, use: frozenset[str]) -> bool:
        """Whether *use* — the set of enabled flags — meets this requirement."""

    @abstractmethod
    def render(self) -> str:
        """The requirement written the way the ebuild writes it."""

    def applies(self, use: frozenset[str]) -> bool:
        """Whether this requirement has anything to say about *use* at all.

        A conditional whose condition is off is neither met nor broken, and
        showing it as either would be misleading.
        """
        return True

    @abstractmethod
    def flags(self) -> frozenset[str]:
        """Every flag named anywhere inside, including in conditions."""


@dataclass(frozen=True, slots=True)
class Flag(Node):
    """A bare ``flag`` or ``!flag``."""

    name: str
    negated: bool = False

    def is_satisfied(self, use: frozenset[str]) -> bool:
        return (self.name not in use) if self.negated else (self.name in use)

    def render(self) -> str:
        return f"!{self.name}" if self.negated else self.name

    def flags(self) -> frozenset[str]:
        return frozenset({self.name})


@dataclass(frozen=True, slots=True)
class Group(Node):
    """A group of requirements with a rule about how many must hold."""

    #: ``all``, ``any`` (``||``), ``exactly-one`` (``^^``) or ``at-most-one`` (``??``).
    kind: str
    children: tuple[Node, ...]

    _OPERATORS = {"all": "", "any": "|| ", "exactly-one": "^^ ", "at-most-one": "?? "}

    def is_satisfied(self, use: frozenset[str]) -> bool:
        met = sum(1 for child in self.children if child.is_satisfied(use))
        if self.kind == "all":
            return met == len(self.children)
        if self.kind == "any":
            return met >= 1
        if self.kind == "exactly-one":
            return met == 1
        return met <= 1  # at-most-one

    def inner(self) -> str:
        """The children, space-separated, without this group's own brackets."""
        return " ".join(child.render() for child in self.children)

    def render(self) -> str:
        if self.kind == "all":
            # An implicit group of one is just that one requirement; writing
            # `( vulkan )` back would be noise the ebuild never had.
            return self.inner() if len(self.children) == 1 else f"( {self.inner()} )"
        return f"{self._OPERATORS[self.kind]}( {self.inner()} )"

    def flags(self) -> frozenset[str]:
        return frozenset().union(*(child.flags() for child in self.children)) if self.children \
            else frozenset()

    def satisfied_children(self, use: frozenset[str]) -> tuple[Node, ...]:
        """The children that currently hold — what the interface highlights."""
        return tuple(child for child in self.children if child.is_satisfied(use))


@dataclass(frozen=True, slots=True)
class Conditional(Node):
    """``flag? ( … )`` — requirements that only apply under a condition."""

    condition: Flag
    body: Group

    def applies(self, use: frozenset[str]) -> bool:
        return self.condition.is_satisfied(use)

    def is_satisfied(self, use: frozenset[str]) -> bool:
        return not self.applies(use) or self.body.is_satisfied(use)

    def render(self) -> str:
        # Always bracketed, however few requirements are inside: that is how
        # the ebuild writes it, and the point is that the user recognises it.
        return f"{self.condition.render()}? ( {self.body.inner()} )"

    def flags(self) -> frozenset[str]:
        return self.condition.flags() | self.body.flags()


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------


def _tokenise(text: str) -> list[str]:
    """Split on whitespace, with the brackets as tokens of their own."""
    return text.replace("(", " ( ").replace(")", " ) ").split()


def parse(text: str) -> tuple[Node, ...]:
    """Parse a ``REQUIRED_USE`` string into its top-level requirements.

    Raises :class:`RequiredUseError` on anything malformed. That is a real
    possibility with an overlay ebuild, and a broken expression must produce a
    visible complaint rather than a silently empty list of rules.
    """
    tokens = _tokenise(text)
    position = 0
    nodes: list[Node] = []
    while position < len(tokens):
        node, position = _parse_one(tokens, position)
        nodes.append(node)
    return tuple(nodes)


def _parse_one(tokens: list[str], position: int) -> tuple[Node, int]:
    token = tokens[position]

    if token == ")":
        raise RequiredUseError("unbalanced ')' in REQUIRED_USE")

    if token in ("||", "^^", "??"):
        kind = {"||": "any", "^^": "exactly-one", "??": "at-most-one"}[token]
        children, position = _parse_group(tokens, position + 1, token)
        return Group(kind, children), position

    if token == "(":
        children, position = _parse_group(tokens, position, "(")
        return Group("all", children), position

    if token.endswith("?"):
        condition = _flag(token[:-1])
        children, position = _parse_group(tokens, position + 1, token)
        return Conditional(condition, Group("all", children)), position

    return _flag(token), position + 1


def _parse_group(tokens: list[str], position: int, opener: str) -> tuple[tuple[Node, ...], int]:
    if position >= len(tokens) or tokens[position] != "(":
        raise RequiredUseError(f"expected '(' after {opener!r} in REQUIRED_USE")
    position += 1

    children: list[Node] = []
    while position < len(tokens) and tokens[position] != ")":
        child, position = _parse_one(tokens, position)
        children.append(child)
    if position >= len(tokens):
        raise RequiredUseError(f"unterminated group after {opener!r} in REQUIRED_USE")
    return tuple(children), position + 1


def _flag(token: str) -> Flag:
    if not token or token in ("(", ")"):
        raise RequiredUseError(f"expected a flag name, found {token!r}")
    if token.startswith("!"):
        return Flag(token[1:], negated=True)
    return Flag(token)


# ---------------------------------------------------------------------------
# evaluating
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Requirement:
    """One top-level rule, evaluated against a particular set of flags."""

    expression: str
    satisfied: bool
    #: ``False`` for a conditional whose condition is currently off — the rule
    #: is dormant rather than met, and the interface says so differently.
    applies: bool
    flags: frozenset[str]
    node: Node

    @property
    def is_broken(self) -> bool:
        return self.applies and not self.satisfied


def evaluate(nodes: Sequence[Node], use: Iterable[str]) -> tuple[Requirement, ...]:
    """Check every top-level requirement against the enabled flags."""
    enabled = frozenset(use)
    return tuple(
        Requirement(
            expression=node.render(),
            satisfied=node.is_satisfied(enabled),
            applies=node.applies(enabled),
            flags=node.flags(),
            node=node,
        )
        for node in nodes
    )


def check(text: str, use: Iterable[str]) -> tuple[Requirement, ...]:
    """Parse and evaluate in one go. Returns ``()`` for an empty expression."""
    if not text.strip():
        return ()
    return evaluate(parse(text), use)


def broken(requirements: Sequence[Requirement]) -> tuple[Requirement, ...]:
    return tuple(item for item in requirements if item.is_broken)
