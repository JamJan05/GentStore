# Recorded `emerge` output

The input to `gentstore/core/emerge_parse.py` and
`gentstore/core/install_plan.py` is the text `emerge` prints, and there is no
API behind it. So these are real runs, recorded on a Gentoo system rather than
written by hand: a fixture typed from memory tests the memory.

Each was produced with the command line `gentstore/runner/emerge.py` builds:

```sh
LC_ALL=C.UTF-8 emerge --ignore-default-opts --color=n --nospinner \
    --pretend --verbose --autounmask --autounmask-license=y <atoms>
```

| File | What it is |
|---|---|
| `pretend-autounmask-hyprland.txt` | A package needing fourteen keyword lines, alongside a blocker Portage reported after giving up backtracking early. The case the grouped write exists for. |
| `pretend-conflict.txt` | A slot conflict with nothing to write — two versions of one package in one slot. Nothing to apply, and no line in `/etc/portage` settles it. |
| `pretend-clean.txt` | A run with nothing to say, which is what opens the install gate. |
| `pretend-block-satisfied.txt` | A run carrying `[blocks b ]` — a block Portage worked out for itself, `Conflict: 1 block (all satisfied)` — alongside one keyword to accept. The run that proved a listed block is not automatically a problem. |
| `pretend-world-skipped.txt` | An ordinary `@world` update that succeeded and printed `!!!` lines anyway, saying which updates it left out. The run that proved `!!!` is not a test for anything. Recorded with `--update --deep --newuse --changed-use @world` rather than the command above. |
| `pretend-required-use.txt` | A dependency whose own `REQUIRED_USE` forbids the very flags something asks of it. Portage proposes a line for `package.use` **and** refuses in the same breath — applying the line and looking again produces the identical output. |
| `pretend-missing-use.txt` | A dependency on a USE flag none of the candidate versions has any more. Four versions listed, the missing flag named against each. |
| `pretend-no-ebuild.txt` | An atom nothing provides — the reading is nearly always a repository that is not enabled. Notable for carrying no `!!!` line at all. |
| `pretend-masked.txt` | A dependency masked in a way `--autounmask` will not lift, here by its EAPI. |

## The four refusals, and the repository they were recorded against

`emerge` has one function for "I cannot satisfy this dependency"
(`_emerge/depgraph.py`: `_show_unsatisfied_dep`) and four branches inside it, one per
fixture above. Getting all four out of a healthy system is not a matter of picking
awkward packages: with `--autounmask` on, Portage answers most refusals with a line to
write instead of a refusal.

So they were recorded against a scratch repository of four one-line ebuilds, each
with an `RDEPEND` that cannot be met — a flag that no longer exists, a USE
combination the dependency's own `REQUIRED_USE` forbids, an atom nothing provides, an
EAPI this Portage does not support. The repository was passed in the environment,
`PORTAGE_REPOSITORIES=…`, so nothing about the machine was changed and every run is
still `emerge --pretend` reading the real tree.

The point of doing it that way rather than by naming an awkward atom on the command
line is the last two lines of each file:

```
(dependency required by "app-misc/gs-demo-missing-use-1::scratch" [ebuild])
(dependency required by "app-misc/gs-demo-missing-use" [argument])
```

That is how a user meets a refusal — about a package they have never heard of, pulled
in by the one they asked for. A refusal about the atom they typed is the easy case and
the rare one.

`tools/refusal-demo.sh` builds that repository again, either to re-record these files or
to put the four refusals in front of the running window. It changes nothing on the
machine and needs no root.

## One edit, and what it was

The Hyprland run and the `@world` run are the two that have been touched. Portage explains a
blocker by listing every package that depends on the one in question, with its
full `USE` flags — for an installed system that is a detailed inventory of the
machine, and this repository is public. The lines naming **already installed**
packages have been removed and replaced with a marker saying how many went; the
lines describing the merge being planned are untouched, as is everything the
parser reads: the merge list, the totals, the blocker row, the keyword block and
the note about backtracking.

Nothing else has been edited, and nothing has been reformatted. If you record a
replacement, keep it that way — the value of these files is that they are what
`emerge` really printed.
