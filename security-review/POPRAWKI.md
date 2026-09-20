# Co trzeba poprawić — lista do odhaczenia

Ta sama treść co w [RAPORT.md](RAPORT.md), ale ułożona według plików, żeby dało się po niej
pracować. Uzasadnienia, scenariusze ataku i dowody są w raporcie — tutaj jest tylko „gdzie" i „co".

**Stan: GS-01, GS-02, GS-03, GS-04, GS-06 i GS-09 są naprawione** — czyli wszystkie o wadze Wysokiej na gałęzi `fix/helper-content-validation`. Zmienione
pliki: `gentstore/helper/gentstore_helper.py`, `gentstore/ui/pages/cfgfiles.py` (musi teraz
wysyłać `expect` przy scalaniu), `tests/test_helper.py` (+18 testów),
`tests/test_cfgfiles.py`, `Docs/04-privileges.md` (reguły 1a, 1a′, 7, 9), `CHANGELOG.md`.
Reszta listy czeka — nic z niej nie zostało zastosowane.

---

## Kolejność

| # | Znalezisko | Waga | Plik | Szacunek |
|---|---|---|---|---|
| ✅ | [GS-01](RAPORT.md#gs-01--write_file-sprawdza-ścieżkę-ale-nie-treść--plik-w-reposconf-może-przedefiniować-sync-uri-repozytorium-gentoo) — `write_file` nie sprawdza treści | Wysoka | `gentstore/helper/gentstore_helper.py` | ~40 linii + 2 testy |
| ✅ | [GS-02](RAPORT.md#gs-02--cfg_apply-z-decisionmerge-zapisuje-dowolną-treść-i-nie-wymaga-expect) — `cfg_apply merge` bez `expect` | Wysoka | `gentstore/helper/gentstore_helper.py` | 3 linie + 1 test |
| ✅ | [GS-03](RAPORT.md#gs-03--katalog-w-którym-leży-plik-_cfg-nigdy-nie-jest-pytany-o-to-kto-może-w-nim-pisać) — katalog `._cfg` niesprawdzany | Średnia | `gentstore/helper/gentstore_helper.py` | 5 linii + 1 test |
| ✅ | [GS-06](RAPORT.md#gs-06--features-i-makeopts-mieszczą-w-dozwolonym-zestawie-znaków-wyłączenie-sandboksa) — `FEATURES="-sandbox"` przechodzi | Wysoka | `gentstore_helper.py` + `core/makeconf.py` | ~35 linii + 2 testy |
| ✅ | [GS-09](RAPORT.md#gs-09--eselect-repository-add-przyjmuje-file-i-nazwę-kolidującą-z-gentoo) — `file://` i nazwa `gentoo` | Wysoka | `gentstore_launcher.py` + `core/overlays.py` | 6 linii + 2 testy |
| ✅ | [GS-04](RAPORT.md#gs-04--emerge---unmerge-kategoria-przechodzi-przez-tabelę) — `--unmerge sys-apps/*` | Wysoka | `gentstore/helper/gentstore_launcher.py` | ~12 linii + 1 test |
| 7 | [GS-05](RAPORT.md#gs-05--wzorzec-match-w-replace_line-to-regex-z-żądania-uruchamiany-w-procesie-roota) — regex z żądania | Średnia | `gentstore_helper.py` + `core/makeconf.py` + `core/confedit.py` | ~25 linii, zmiana protokołu |
| 8 | [GS-07](RAPORT.md#gs-07--podgląd--zapis-qlabel-w-trybie-autotext-zjada-linię-zaczynającą-się-od-) + [GS-08](RAPORT.md#gs-08--tekst-z-ebuilda-metadataxml-i-katalogu-overlayów-jest-renderowany-jako-html) — `setTextFormat` | Średnia | `gentstore/ui/**` | ~20 jednoliniowych zmian |
| 9 | [GS-10](RAPORT.md#gs-10--treść-linii-w-package-nie-jest-sprawdzana-wcale-r-przechodzi-tam-gdzie-n-nie) — `\r` i NUL w linii | Średnia | `gentstore/helper/gentstore_helper.py` | ~15 linii + 2 testy |
| 10 | [GS-12](RAPORT.md#gs-12--helper-nie-odpowiada-json-em-na-zagnieżdżony-json-i-czyta-stdin-bez-ograniczenia) — `RecursionError`, brak limitu stdin | Niska | `gentstore/helper/gentstore_helper.py` | ~10 linii + 2 testy |
| 11 | [GS-11](RAPORT.md#gs-11--glsa-check--f-instaluje-pakiety-jako-root-bez-potwierdzenia-i-bez-podglądu) — `glsa-check -f` bez pytania | Niska | `gentstore/ui/pages/update.py` | ~20 linii |
| 12 | [GS-13](RAPORT.md#gs-13--coreoverlayspy-czyta-repositoriesxml-bez-limitu-rozmiaru) — brak limitu na `repositories.xml` | Niska | `gentstore/core/overlays.py` | 6 linii + 1 test |
| 13 | [GS-14](RAPORT.md#gs-14--allow_inactive--auth_admin--sesja-zdalna-może-uwierzytelnić) — `allow_inactive` | Info | `data/org.gentoo.gentstore.policy` | 2 linie, do decyzji |
| 14 | [GS-15](RAPORT.md#gs-15--_tampering_risk-nie-sprawdza-właściciela), [GS-16](RAPORT.md#gs-16--cache-indeksu-i-katalog-overlayów-decydują-o-tożsamości-pokazywanego-pakietu) — docstringi obiecują więcej, niż dają | Info | `runner/privilege.py`, `core/index_cache.py` | komentarze |
| 15 | [GS-18](RAPORT.md#gs-18--łańcuch-dostaw-drobiazgi-w-ci-i-w-skryptach-pakujących) — CI i skrypty pakujące | Info | `.github/workflows/`, `packaging/` | drobiazgi |

---

## `gentstore/helper/gentstore_helper.py`

- [x] **GS-01** — `op_write_file` (`:944`): dopisać `_check_repo_file(path, content)` przed
      `_check_expectation`. Walidować: dokładnie jedna sekcja, o nazwie równej `path.stem`, brak
      `[DEFAULT]`, klucze z zamkniętej listy, `location` pod `/var/db/repos/`.
- [x] **GS-01** — `_require_owned` (`:543`): dołożyć limit głębokości
      (`len(relative.parts) > 2` → odmowa), dziś nie ma żadnego.
- [x] **GS-02** — `op_cfg_apply` (`:1006`): dla `decision == "merge"` wywołać
      `_check_expectation(target, request)` **bezwarunkowo**, nie tylko gdy `"expect" in request`.
- [x] **GS-03** — `op_cfg_apply` (`:985`): po sprawdzeniu `_CFG_PREFIX` dołożyć
      `if not _only_root_can_write(candidate.parent): raise HelperError("unsafe_directory", …)`.
      Przy okazji poprawić docstringi `_only_root_can_write` i `protected_roots`, które dziś
      obiecują dokładnie to sprawdzenie.
- [x] **GS-06** — nowa `_check_make_conf_value(name, value)` wołana na końcu
      `_check_make_conf_line` (`:540`): dla `FEATURES` lista dozwolonych tokenów, dla `MAKEOPTS`
      wyłącznie opcje zrównoleglenia. Kopia listy w `core/makeconf.py` + test porównujący.
- [ ] **GS-05** — `op_replace_line` (`:896`): zamienić pole `match` (regex) na parę
      `match_kind` + `match_literal`; wzorzec buduje helper przez `re.escape`. Zaktualizować
      `core/makeconf.py:298` i `core/confedit.py:249,289`. `match` zostawić na jedno wydanie jako
      odrzucane z `bad_pattern`, żeby starszy interfejs dostał zrozumiałą odmowę.
- [ ] **GS-10** — wydzielić `_one_line(raw, where="")`: odmawiać na NUL i na każdym znaku, który
      `str.splitlines()` uznaje za koniec linii (`\r`, `\v`, `\f`, `\x1c`, U+2028, U+0085).
      Użyć w `op_append_line`, `_batch_entries`, `op_replace_line`, `op_remove_line`.
- [ ] **GS-10b** — `_read`/`_joined` (`:603`, `:616`): zachowywać oryginalne zakończenia linii
      albo odmawiać na pliku zawierającym `\r`. Dziś `replace_line` po cichu konwertuje CRLF→LF
      w całym pliku, wbrew `Docs §4` („byte for byte").
- [ ] **GS-12** — `main` (`:1154`): `stdin.read(STDIN_MAX + 1)` + odmowa `too_large`;
      dołożyć `except RecursionError` do sita wyjątków.

## `gentstore/helper/gentstore_launcher.py`

- [x] **GS-04** — nowy znacznik `EXACT_ATOMS` (atom bez `*`) i obsługa w `_matches` (`:343`);
      użyć w wierszu `unmerge()` (`:306`). Podgląd (`unmerge_pretend`, `:304`) zostaje przy
      `ATOMS` — nic nie usuwa.
- [x] **GS-09** — `_URI` (`:157`): usunąć `file` z listy schematów.
- [x] **GS-09** — nowy `_is_new_repository` + znacznik `NEW_REPOSITORY`: `gentoo` i `DEFAULT`
      odrzucane **tylko** w wierszu `repository add`. `_is_repository` zostaje bez zmian, bo
      `emaint sync -r gentoo` i `eselect repository disable gentoo` to zwykłe operacje.
- [ ] *(opcjonalnie)* `resolve` (`:101`): sprawdzać, że znaleziony program należy do roota i nie
      jest zapisywalny dla grupy/innych — dziś `SEARCH_PATH` jest stałe, więc to tylko hartowanie.

## `gentstore/core/`

- [x] **GS-09** — `overlays.py:247` (`_SCHEME`): usunąć `file`, żeby okno nie włączało przycisku
      dla czegoś, czego launcher odmówi. Test
      `test_the_overlay_dialog_and_the_launcher_agree_on_url_schemes` sam wychwyci rozjazd.
- [x] **GS-09** — `overlays.py` (`is_valid_name`): odrzucać `gentoo`.
- [ ] **GS-13** — `overlays.py:183` (`parse`): limit rozmiaru, jak `METADATA_MAX_BYTES`
      w `useflags.py:360`.
- [ ] **GS-05** — `makeconf.py:298` i `confedit.py:249,289`: przejść na nowe pola żądania.
- [x] **GS-06** — `makeconf.py`: kopia listy dozwolonych tokenów `FEATURES`/`MAKEOPTS`.
- [ ] **GS-16** — `index_cache.py:28-38`: poprawić komentarz — odcisk chroni przed
      *nieświeżością*, nie przed *podmianą* przez tego samego użytkownika.

## `gentstore/ui/`

- [x] **GS-02** — `pages/cfgfiles.py` (`_decide`): wysyłać `expect` przy `decision="merge"`,
      a gdy celu nie da się odczytać — odmówić z wyjaśnieniem zamiast wysyłać żądanie, którego
      helper i tak nie przyjmie.
- [ ] **GS-07/GS-08** — dodać pomocnik `plain_label()` w `ui/widgets/__init__.py` i użyć go
      (albo dopisać `setTextFormat(Qt.TextFormat.PlainText)`) wszędzie, gdzie do `QLabel` trafia
      tekst spoza `self.tr()`. Miejsca, które sprawdziłem:
  - [ ] `widgets/write_preview.py:73` (`_path`), `:79` (`_line`), `:102` (`_report`)
  - [ ] `widgets/required_changes.py:535` (linia wpisu), `:604` (`_preview_body`),
        `:576` (`_conflict`), `:293` (`_report`)
  - [ ] `widgets/block_notice.py:339` — `setToolTip(fix.line)`; podpowiedzi Qt też są rich-textem
  - [ ] `pages/search.py:287,593` — `DESCRIPTION` z ebuilda
  - [ ] `widgets/use_flag_row.py:94,262` — opis flagi z `metadata.xml`
  - [ ] `pages/repos.py:187,890` — opis repozytorium z `repositories.xml`
  - [ ] `widgets/news_list.py:57` — tytuł newsa GLEP 42
  - [ ] `pages/cfgfiles.py:78,426` — nazwa pliku konfiguracyjnego
  - [ ] **przejrzeć resztę** — powyższa lista pochodzi z `grep` po `QLabel(`/`setText(`
        i **nie jest kompletna**; dziś `setTextFormat` nie pada w `gentstore/ui/` ani razu
- [ ] **GS-11** — `pages/update.py:385-389`: pokazać listę przed `glsa-check -f`, albo
      `QMessageBox.question` z identyfikatorami z `glsa-check -l affected`, które już są w pamięci.

## `data/` i `packaging/`

- [ ] **GS-14** — `org.gentoo.gentstore.policy:43,57`: rozważyć `allow_any`/`allow_inactive` = `no`.
      Do decyzji z użytkownikami — na maszynie zarządzanej przez SSH to odcina aplikację.
- [ ] **GS-18** — `packaging/make-overlay.sh:51`: ograniczyć `GENTSTORE_REF` do
      `^[A-Za-z0-9._/-]+$`, zanim trafi do `RAW_BASE`.
- [ ] **GS-18** — `.github/workflows/release.yml:100`: przenieść
      `${{ github.event.inputs.dry_run }}` do `env:`, tak jak robi to `website-version.yml`.
- [ ] **GS-18** — przypiąć akcje do SHA zamiast do tagów (`actions/checkout@v5`,
      `actions/setup-python@v5`) w workflowach z `permissions: contents: write`.
- [ ] **GS-18** — przypiąć wersje w `tests.yml:63` (`pip install …`) i obraz
      `gentoo/portage:latest` w `tests-gentoo.yml:39`.

## `tests/`

Szkice są przy każdym znalezisku w raporcie. Braki zebrane:

- [x] `test_helper.py` — `write_file` a treść pliku `repos.conf` (GS-01) — 7 testów
- [x] `test_helper.py` — `cfg_apply merge` wymaga `expect` (GS-02) — 4 testy.
      `test_cfg_apply_without_an_expectation_still_works` okazał się już dotyczyć wyłącznie
      `decision="accept"`, więc został bez zmian; poprawki wymagał natomiast
      `tests/test_cfgfiles.py::test_merging_writes_what_the_user_ended_up_with`.
- [ ] `test_helper.py` — katalog kandydata `._cfg` a `_only_root_can_write` (GS-03)
- [x] `test_helper.py` — `FEATURES`/`MAKEOPTS` (GS-06) — 27 testów po obu stronach szwu
- [ ] `test_helper.py` — „jedna linia" wobec `\r`, U+2028 i NUL (GS-10)
- [ ] `test_helper.py` — `replace_line` zostawia resztę pliku bajt w bajt (GS-10b)
- [ ] `test_helper.py` — zagnieżdżony JSON i limit stdin (GS-12)
- [x] `test_runner.py` — `--unmerge sys-apps/*` odrzucone, podgląd nadal dozwolony (GS-04)
- [x] `test_runner.py` — `file://` i nazwa `gentoo` odrzucone (GS-09)
- [ ] **nowy** `test_preview_integrity.py` — podgląd pokazuje dokładnie te bajty, które zostaną
      zapisane, i każdy `QLabel` niosący dane ma jawny `textFormat` (GS-07, GS-08)

---

## Jak odtworzyć dowody

```
python3 security-review/poc/poc_helper.py      # GS-01, GS-05, GS-06, GS-10, GS-12
python3 security-review/poc/poc_launcher.py    # GS-04, GS-09
python3 security-review/poc/poc_cfg.py         # GS-02, GS-03
```

Wszystkie trzy działają na katalogu tymczasowym z podmienioną stałą `CONFIG_ROOT` — tak jak
`tests/test_helper.py`. Nie wołają `pkexec` ani `sudo`, nie uruchamiają `emerge`, `eselect` ani
`emaint` i nie dotykają `/etc`.
