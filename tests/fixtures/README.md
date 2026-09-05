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

## One edit, and what it was

The Hyprland run is the only one that has been touched. Portage explains a
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
