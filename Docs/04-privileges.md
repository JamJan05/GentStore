# 04 — Privileges, writing to `/etc/portage`, backups

The application manages the system, so this is the document about how **not to do the user any
harm**.

## 1. The model

```
  the GUI process (an ordinary user)
        │
        ├── reading: the portage API, /etc/portage, /var/db/repos, /var/log/portage   ← no root
        │
        ├── system commands ──────► pkexec ──► gentstore-launcher ──► emerge / eselect / …
        │                                       │                     (stdin: /dev/null)
        │            "abort" on stdin ──────────┘
        │                                       └─ output streamed to the GUI
        │
        └── writing files ────────► pkexec ──► gentstore-helper  (JSON on stdin)
                                               │
                                               ├─ path validation
                                               ├─ backup
                                               ├─ atomic write
                                               └─ a JSON report on stdout
```

So there are **two** privileged programs, both in `/usr/libexec/gentstore/`, both invoked only
through `pkexec`. The reason we do not simply run commands with `pkexec emerge …` is in §7.

**The GUI process is never root.** There is no “run the whole application under sudo” mode — if
somebody starts it that way, they get a warning at startup (running Qt as root is bad practice,
and it is not needed anyway).

## 2. The privileged helper

`gentstore/helper/gentstore_helper.py`, installed as `/usr/libexec/gentstore/gentstore-helper`.
This is the **only** place in the whole project that writes anything outside the home directory.

It accepts one operation as JSON on stdin and returns JSON on stdout. A closed set of
operations:

| Operation | Meaning |
|---|---|
| `append_line` | append a line to a file (if an identical one is already there — do nothing and report it) |
| `replace_line` | replace **one** line matching a pattern (e.g. `USE=` in `make.conf`) |
| `remove_line` | remove a line matching verbatim |
| `write_file` | write a whole file — only for files the application created itself (`repos.conf/<repo>`) |
| `delete_file` | delete a file the application created |
| `backup` | make a copy of `/etc/portage` |
| `restore` | restore a copy |
| `cfg_apply` | settle a `._cfg0000_*` file: apply the new one / keep the old one / write the merged one |

Hard rules inside the helper, enforced regardless of what the GUI sent:

1. After `realpath()`, the destination path has to fall within `/etc/portage` (or be a `._cfg`
   file in a directory Portage actually reported). Anything else → refused.
2. It refuses to follow symbolic links that lead outside the permitted area.
3. Atomic writes: a temporary file in the same directory → `fsync` → `os.replace`. A file is
   never left damaged halfway through a write.
4. The owner and permissions of an existing file are preserved; new files are `0644 root:root`.
5. A backup is made **before** the first modification in a given session (see §5).
6. The response contains the exact path and the exact content written — the GUI does not guess,
   it displays what the helper really did.
7. `write_file` and `delete_file` require an `expect` field — the exact current content of the
   file, or `null` (“this file should not exist yet”). If it does not match, the helper refuses:
   somebody edited the file in the meantime and their version wins. `cfg_apply` honours the same
   field when it is given one — it does not require it, because an older interface does not send
   it, but a request that carries it gets a stronger guarantee.
8. The permitted directory (`/etc/portage`) is a **constant in the code** — not an argument and
   not an environment variable. The caller composes argv, and with `sudo` partly the environment
   too; either would be a way to redirect a write elsewhere. Tests replace the constant after
   importing the module, which the installed program cannot do.
9. **`cfg_apply` is the only operation that reaches outside `/etc/portage`** — because that is
   where Portage leaves `._cfg` files. Its reach is bounded by three conditions at once: the
   name has to match `._cfgNNNN_`, the file has to lie in a directory Portage protects, and the
   destination file is derived from the name rather than from the request. The helper reads the
   list of protected directories **by itself** from `make.globals`, `make.conf` and
   `/etc/env.d/` — files that belong to root — and not from what arrived on stdin. The parser is
   deliberately primitive: it recognises only `CONFIG_PROTECT=` as a standalone assignment,
   because anything cleverer would be a way to widen the reach.

The helper imports neither PyQt nor anything from `gentstore.ui`. It is meant to be small,
readable and reviewable end to end by a distrustful user — because that is exactly what Gentoo
users are.

## 2a. The command launcher

`gentstore/helper/gentstore_launcher.py` → `/usr/libexec/gentstore/gentstore-launcher`. It runs
**one** Portage command as root, passes its output on, and can stop it. It does three things
`pkexec emerge …` does not:

1. **It limits what can be run** — and not just *which program*, but *which command*. A closed
   list of program names (`emerge`, `emaint`, `eselect`, `glsa-check`), looked up in a fixed set
   of directories and **not** in `PATH` — because in the `sudo` fallback part of the environment
   comes from the caller.

   The second half matters more: **the arguments are checked too**. `emerge` with arbitrary
   options is root under another name (`--config` runs a package's configuration script,
   `--root` moves the whole operation somewhere else), and the authentication dialog promised
   “installing and updating packages”. So the launcher knows exactly the commands
   `runner/emerge.py` and `runner/eselect.py` build:

   - `emerge` — a closed set of options compared **verbatim** (`--color=n` is allowed,
     `--color=y` is not: the value attached to an option is a place to hide something), and
     every remaining argument has to have the shape of an atom (`category/package`,
     `=cat/pkg-1.2`) or of a set (`@world`). Names ending in `.ebuild`, `.tbz2`, `.gpkg` or
     `.xpak` are rejected — `emerge` reads those as a file to merge, not as a package to look
     up;
   - `emaint`, `eselect` — a table of complete command templates (`repository add <name> <type>
     <url>`, `profile set <number>` and so on), matched token by token;
   - `glsa-check` — `-l` or `-f`, and after that nothing but GLSA numbers or the word
     `affected`.

   Why this is not overkill: polkit remembers the answer for a few minutes
   (`auth_admin_keep`, §3), so within that window **any other process running as that user** can
   reach this program without a dialog of its own. What it finds there must not be worth more
   than the dialog said.

   `dispatch-conf` and `etc-update` **have gone from the list**. They are interactive, they
   start an editor, and Gentstore settles `._cfg` files through `cfg_apply` in the helper —
   nothing in the interface asks for them, so their presence only widened the reach.
2. **It can be interrupted** — see §7.
3. **It keeps the child away from the control channel** — the child process gets `/dev/null` on
   stdin, so it can neither eat the “abort” message nor hang waiting for an answer nobody can
   give.

It also sets `PYTHONUNBUFFERED=1`. `emerge` is a Python program, and writing to a pipe it would
buffer its output in kilobyte blocks — the log in the window would sit still and then jump,
instead of scrolling the way it does in a terminal.

### The two halves are versioned together

The interface and the privileged programs change together, but are installed separately
(`sudo make install-system`). An installed helper older than the interface refuses operations
that this version considers entirely ordinary — and it does so with a message that is true but
incomprehensible (`outside_root` for a file that may perfectly well be touched).

So `runner/privilege.installed_status()` compares the installed copy against the source, the
window mentions the mismatch at startup, and every helper refusal then gets a note with the real
reason. This does not replace reinstalling — it is there so that nobody spends half an hour
diagnosing the wrong problem.

## 3. Polkit

`data/org.gentoo.gentstore.policy` declares two actions:

| Action | The description in the authentication dialog | Default |
|---|---|---|
| `org.gentoo.gentstore.modify-config` | “Changing the Portage configuration” | `auth_admin_keep` |
| `org.gentoo.gentstore.run-emerge` | “Installing and updating packages” | `auth_admin_keep` |

`auth_admin_keep` means: ask for a password, but remember it for a while — otherwise a six-step
update cycle would ask six times.

The message of the `modify-config` action mentions **both** `/etc/portage` **and** `/etc`.
Settling `._cfg` files belongs to that action, and Portage leaves those wherever
`CONFIG_PROTECT` points — by default in `/etc`. A dialog that said only “/etc/portage” would be
asking for consent to less than it grants.

**The fallback without polkit:** if `pkexec` does not exist, `runner/privilege.py` falls back to
`sudo`. That then needs a terminal or `SUDO_ASKPASS`; when there is neither, the application
says plainly what is missing instead of quietly failing.

### Copies from the source tree do not reach root by themselves

In a clone of the repository both privileged programs are files **an ordinary user can write**,
and the fallback invocation used to hand one of them to `pkexec` as an argument to `python3`.
pkexec checks whether *python3* belongs to root; about the script it is given it has nothing to
say. Anything able to write into the clone — a second account with access, an editor plugin, a
dependency installed with `-e` — would therefore be one authentication away from root, and the
dialog would show a generic “run a program as another user”, because polkit has no action
registered for that path.

That is why this variant is **off by default**: without `sudo make install-system` the
privileged operations say what is missing, and the rest of the application works read-only. For
the development loop there is `GENTSTORE_DEV_HELPER=1` — and even then the file and every
directory above it must be unwritable by group and others (a sticky-bit directory such as `/tmp`
counts: you cannot replace somebody else's file in one).

## 4. The “never overwrite” principle

The files in `/etc/portage` belong to the user and often carry their comments. Therefore:

- **we append lines**, we do not rewrite files;
- when changing a variable in `make.conf` we replace **that one line**, leaving the rest of the
  file byte for byte (comments and blank lines included);
- if a line with identical content already exists — we do not duplicate it, we say so (“that
  entry is already there”);
- if a line exists for the same atom but with different content — we **ask** whether to replace
  it, showing both versions side by side;
- `write_file` is allowed only for files the application created itself
  (`/etc/portage/repos.conf/<name>.conf`), and only when their content matches what the
  application wrote there.

Deciding “file or directory” for `package.use`, `package.mask`, `package.accept_keywords`,
`package.unmask` and `package.license` is described in
[01-architecture.md §7](01-architecture.md).

## 5. Backups

Before the **first** modification in a given run of the application, a copy is made:

```
/etc/portage.bak-2026-08-26T0712/     # a copy of the directory, permissions preserved
```

- One copy per application session, not per change — otherwise the disk would fill with copies.
- The copy is made **in the same privileged call as the change** (the `ensure_backup` field in
  the request), not in a separate one. That means one password prompt instead of two and, more
  importantly, that the state “the change went in, the copy did not” cannot arise.
- We keep the last **10** copies and delete older ones (with a visible message).
- The sidebar always shows the name of the current copy and a **“Restore…”** link.
- Restoring shows a `diff` between the copy and the current state **before** it runs — restoring
  is a change to the system too, and falls under the same “nothing quietly” principle.
- Alternatively (an option in Settings) the copy can be a `tar.zst` in
  `/var/backups/gentstore/`, for people who do not want clutter in `/etc`.

## 6. Risky operations — always confirmed

A separate confirmation dialog, listing the consequences, for:

| Operation | What we show first |
|---|---|
| `emerge --depclean` | the full list of packages to be removed and why each is considered orphaned |
| `eselect repository remove -f` | how many installed packages come from that repo and what will happen to them |
| changing the profile | a warning that the set of default USE flags will change and that `emerge -avuDN @world` will be needed |
| adding an overlay from outside the list | that ebuilds from a foreign repository run with root privileges when building |
| masking a repo (`*/*::repo`) | which installed packages will stop receiving updates |
| adding an overlay from outside the catalogue | a separate dialog: ebuilds from a foreign source run as root on every build, now and after every sync |
| restoring an `/etc/portage` copy | the diff between the copy and the current state |

Uninstalling a single package also goes through `emerge -pv --unmerge` and shows the list before
anything disappears.

## 7. Interrupting

Every long-running command has an **“Interrupt”** button. The sequence: `SIGINT` to the process
group (just like `Ctrl+C` in a terminal — `emerge` then cleans up after itself), and only after
10 s without a reaction, `SIGTERM`. Never `SIGKILL` — killing `emerge` halfway through an
installation can leave an inconsistent package database.

**Who sends the signal is not a detail.** The GUI process runs as an ordinary user, and `emerge`
started through `pkexec` runs as root. The kernel will not let an unprivileged process send a
signal to a root process, so the GUI **is not able** to interrupt what it started itself. Hence
the launcher: the GUI writes the word `abort` to its stdin, and the signal then leaves from
inside the privileged process, where it is allowed. End of stream (`EOF`) counts the same as
`abort` — if the interface died, the build it started has no reason to carry on unattended.

Unprivileged commands (`emerge -pv`) are our own child processes and get the signal directly. We
start them in a separate session (`CreateNewSession`), so that the interrupt covers the whole
process tree and never ourselves.

## 8. What the application does not do

Written down explicitly, so there is no temptation:

- it does not modify ebuilds or anything in `/var/db/repos/`;
- it does not change anything in `/var/db/pkg/` (the installed package database) — that is
  Portage's exclusive domain;
- it does not send data anywhere; the only network traffic is `emerge`/`emaint`/`git` run by it
  and doing exactly what they do from a terminal;
- it does not add itself to autostart, nor any systemd/OpenRC services;
- it does not run `emerge --sync` without the user knowing — syncing is always a deliberate
  click.
