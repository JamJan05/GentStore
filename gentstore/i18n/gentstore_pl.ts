<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="pl_PL">
<context>
    <name>AddOverlayDialog</name>
    <message>
        <location filename="../ui/widgets/add_overlay_dialog.py" line="125" />
        <source>Add a repository by hand</source>
        <translation>Dodaj repozytorium ręcznie</translation>
    </message>
    <message>
        <location filename="../ui/widgets/add_overlay_dialog.py" line="127" />
        <source>Nobody has vouched for this repository.

Building a package runs its ebuild as root. Adding a repository means trusting whoever writes those ebuilds with your machine — not just now, but at every future sync. Add one only if you know who is behind it.</source>
        <translation>Za to repozytorium nikt nie ręczy.

Budowanie pakietu uruchamia jego ebuild jako root. Dodanie repozytorium oznacza powierzenie maszyny temu, kto pisze te ebuildy — nie tylko teraz, ale przy każdej kolejnej synchronizacji. Dodawaj tylko, jeśli wiesz, kto za tym stoi.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/add_overlay_dialog.py" line="134" />
        <source>Name</source>
        <translation>Nazwa</translation>
    </message>
    <message>
        <location filename="../ui/widgets/add_overlay_dialog.py" line="135" />
        <source>Sync type</source>
        <translation>Typ synchronizacji</translation>
    </message>
    <message>
        <location filename="../ui/widgets/add_overlay_dialog.py" line="136" />
        <source>URL</source>
        <translation>Adres URL</translation>
    </message>
    <message>
        <location filename="../ui/widgets/add_overlay_dialog.py" line="139" />
        <source>Add</source>
        <translation>Dodaj</translation>
    </message>
    <message>
        <location filename="../ui/widgets/add_overlay_dialog.py" line="143" />
        <source>Cancel</source>
        <translation>Anuluj</translation>
    </message>
</context><context>
    <name>BlockNotice</name>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="210" />
        <source>Not marked stable yet</source>
        <translation>Jeszcze nieoznaczona jako stabilna</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="211" />
        <source>Never tested on this architecture</source>
        <translation>Nietestowana na tej architekturze</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="212" />
        <source>Marked as not working here</source>
        <translation>Oznaczona jako niedziałająca tutaj</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="213" />
        <source>Masked by a developer</source>
        <translation>Zamaskowana przez dewelopera</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="214" />
        <source>Licence not accepted</source>
        <translation>Licencja nieakceptowana</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="215" />
        <source>Portage will not install this version</source>
        <translation>Portage nie zainstaluje tej wersji</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="216" />
        <source>Could not be checked</source>
        <translation>Nie udało się sprawdzić</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="221" />
        <source>The version works, but nobody has declared it stable for {keyword} yet. Running testing versions of individual packages is ordinary practice on Gentoo; the line below tells Portage that this one is fine by you.</source>
        <translation>Wersja działa, ale nikt jej jeszcze nie oznaczył jako stabilnej dla {keyword}. Trzymanie pojedynczych pakietów w wersji testowej to na Gentoo normalna praktyka; linia poniżej mówi Portage, że akurat na tę się zgadzasz.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="227" />
        <source>This version carries no keyword for any architecture — which is also how every live ebuild looks, because it is built straight from the project's source repository and changes without warning. Expect to have to fix things yourself.</source>
        <translation>Ta wersja nie ma keywordu dla żadnej architektury — tak samo wygląda każdy ebuild live, bo buduje się prosto z repozytorium projektu i zmienia bez ostrzeżenia. Licz się z tym, że coś trzeba będzie naprawić samemu.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="234" />
        <source>The ebuild states that this version does not work on this architecture. A line in package.accept_keywords would stop Portage refusing, but it would not make the package build.</source>
        <translation>Ebuild wprost mówi, że ta wersja nie działa na tej architekturze. Linia w package.accept_keywords uciszy Portage, ale nie sprawi, że pakiet się zbuduje.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="240" />
        <source>Somebody decided this version should not be installed and wrote down why. Read that first: masks are usually about security holes, data loss or a package on its way out of the repository.</source>
        <translation>Ktoś uznał, że tej wersji nie należy instalować, i napisał dlaczego. Przeczytaj to najpierw: maski dotyczą zwykle dziur bezpieczeństwa, utraty danych albo pakietu, który wypada z repozytorium.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="246" />
        <source>ACCEPT_LICENSE in make.conf is currently {accepted}, which does not cover every licence this package carries. Read the ones below and decide for this package alone.</source>
        <translation>ACCEPT_LICENSE w make.conf to obecnie {accepted}, co nie obejmuje wszystkich licencji tego pakietu. Przeczytaj poniższe i zdecyduj dla tego jednego pakietu.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="252" />
        <source>Portage could not say whether this version installs, so Gentstore is not going to guess. Nothing here is necessarily wrong with the package — the check itself failed. Run emerge --pretend for this version to see Portage's own answer; the log has the details.</source>
        <translation>Portage nie odpowiedziało, czy ta wersja się zainstaluje, więc GentStore nie zgaduje. Niekoniecznie coś jest nie tak z samym pakietem — to sprawdzenie się nie powiodło. Uruchom emerge --pretend dla tej wersji, żeby zobaczyć odpowiedź Portage; szczegóły są w logu.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="258" />
        <source>Portage gave this reason and Gentstore has nothing to add to it.</source>
        <translation>Portage podał taki powód, a Gentstore nie ma nic do dodania.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="264" />
        <source>empty</source>
        <translation>puste</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="270" />
        <source>Unmask anyway…</source>
        <translation>Odmaskuj mimo to…</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="272" />
        <source>Read the licence…</source>
        <translation>Przeczytaj licencję…</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="274" />
        <source>Accept any keyword…</source>
        <translation>Zaakceptuj dowolny keyword…</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="275" />
        <source>Accept {keyword}…</source>
        <translation>Zaakceptuj {keyword}…</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="279" />
        <source>** accepts this version whatever its keywords say, now and after every sync.</source>
        <translation>** akceptuje tę wersję niezależnie od jej keywordów — teraz i po każdej synchronizacji.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="283" />
        <source>Not recommended: the ebuild says it does not work on this architecture.</source>
        <translation>Niezalecane: ebuild mówi, że to nie działa na tej architekturze.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="286" />
        <source>Not recommended: read the note above before going ahead.</source>
        <translation>Niezalecane: przeczytaj notatkę powyżej, zanim to zrobisz.</translation>
    </message>
</context><context>
    <name>CfgFilesPage</name>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="314" />
        <source>Replace {target} with the version {package} brought?

The file you have now is copied to /etc/config-archive first.</source>
        <translation>Zastąpić {target} wersją, którą przyniósł {package}?

Plik, który masz teraz, zostanie najpierw skopiowany do /etc/config-archive.</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="318" />
        <source>Keep {target} as it is and discard the new version?

{candidate} is deleted. Nothing else changes.</source>
        <translation>Zostawić {target} bez zmian i odrzucić nową wersję?

{candidate} zostanie usunięty. Nic więcej się nie zmieni.</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="322" />
        <source>Save what is in the editor as {target}?

The file you have now is copied to /etc/config-archive first, and {candidate} is deleted.</source>
        <translation>Zapisać to, co w edytorze, jako {target}?

Plik, który masz teraz, zostanie najpierw skopiowany do /etc/config-archive, a {candidate} usunięty.</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="333" />
        <source>Configuration file</source>
        <translation>Plik konfiguracyjny</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="380" />
        <source>Cancelled — nothing was changed.</source>
        <translation>Anulowano — nic nie zostało zmienione.</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="384" />
        <source>Nothing was changed: {error}</source>
        <translation>Nic nie zostało zmienione: {error}</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="399" />
        <source>Kept your version of {target}.</source>
        <translation>Zostawiono Twoją wersję {target}.</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="401" />
        <source>Saved the merged version as {target}.</source>
        <translation>Zapisano scaloną wersję jako {target}.</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="403" />
        <source>Replaced {target} with the new version.</source>
        <translation>Zastąpiono {target} nową wersją.</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="406" />
        <source>The previous version is at {path}.</source>
        <translation>Poprzednia wersja jest w {path}.</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="428" />
        <source>yours: {target}
new:   {candidate}</source>
        <translation>Twój:  {target}
nowy:  {candidate}</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="433" />
        <source>Back to the difference</source>
        <translation>Wróć do różnicy</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="433" />
        <source>Merge by hand…</source>
        <translation>Scal ręcznie…</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="439" />
        <source>Waiting for a decision</source>
        <translation>Czeka na decyzję</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="441" />
        <source>Portage never overwrites a configuration file you have edited. It writes the new version beside it and leaves both, which is what these are.</source>
        <translation>Portage nigdy nie nadpisuje pliku konfiguracyjnego, który edytowałeś. Zapisuje nową wersję obok i zostawia obie — to właśnie te.</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="447" />
        <source>Nothing is waiting. Every configuration file is as you left it.</source>
        <translation>Nic nie czeka. Każdy plik konfiguracyjny jest taki, jak go zostawiłeś.</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="449" />
        <source>Keep mine</source>
        <translation>Zostaw mój</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="450" />
        <source>Take the new one</source>
        <translation>Weź nowy</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="451" />
        <source>Save what I merged</source>
        <translation>Zapisz scalone</translation>
    </message>
</context><context>
    <name>Command</name>
    <message>
        <location filename="../runner/command.py" line="266" />
        <source>The command could not be started.</source>
        <translation>Nie udało się uruchomić polecenia.</translation>
    </message>
    <message>
        <location filename="../runner/command.py" line="275" />
        <source>Stopped at your request.</source>
        <translation>Przerwane na Twoje żądanie.</translation>
    </message>
    <message>
        <location filename="../runner/command.py" line="277" />
        <source>The command was terminated by a signal.</source>
        <translation>Polecenie zostało zakończone sygnałem.</translation>
    </message>
</context><context>
    <name>DiffView</name>
    <message>
        <location filename="../ui/widgets/diff_view.py" line="112" />
        <source>the file you have</source>
        <translation>plik, który masz</translation>
    </message>
    <message>
        <location filename="../ui/widgets/diff_view.py" line="113" />
        <source>the version the package brought</source>
        <translation>wersja przyniesiona przez pakiet</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/widgets/diff_view.py" line="118" />
        <source>%n more line(s) not shown</source>
        <translation>
            <numerusform>nie pokazano jeszcze %n linii</numerusform>
            <numerusform>nie pokazano jeszcze %n linii</numerusform>
            <numerusform>nie pokazano jeszcze %n linii</numerusform>
        </translation>
    </message>
</context><context>
    <name>ElogPage</name>
    <message>
        <location filename="../ui/pages/elog.py" line="321" />
        <source>error</source>
        <translation>błąd</translation>
    </message>
    <message>
        <location filename="../ui/pages/elog.py" line="322" />
        <source>warning</source>
        <translation>ostrzeżenie</translation>
    </message>
    <message>
        <location filename="../ui/pages/elog.py" line="323" />
        <source>quality notice</source>
        <translation>uwaga jakościowa</translation>
    </message>
    <message>
        <location filename="../ui/pages/elog.py" line="324" />
        <source>note</source>
        <translation>notatka</translation>
    </message>
    <message>
        <location filename="../ui/pages/elog.py" line="325" />
        <source>information</source>
        <translation>informacja</translation>
    </message>
    <message>
        <location filename="../ui/pages/elog.py" line="329" />
        <source>package or text</source>
        <translation>pakiet albo treść</translation>
    </message>
    <message>
        <location filename="../ui/pages/elog.py" line="331" />
        <source>all</source>
        <translation>wszystkie</translation>
    </message>
    <message>
        <location filename="../ui/pages/elog.py" line="339" />
        <source>No messages yet. They appear here after a package is installed.</source>
        <translation>Nie ma jeszcze wiadomości. Pojawiają się tutaj po zainstalowaniu pakietu.</translation>
    </message>
    <message>
        <location filename="../ui/pages/elog.py" line="341" />
        <source>Nothing matches the filter.</source>
        <translation>Nic nie pasuje do filtra.</translation>
    </message>
</context><context>
    <name>LicenceDialog</name>
    <message>
        <location filename="../ui/widgets/licence_dialog.py" line="103" />
        <source>Licence {name}</source>
        <translation>Licencja {name}</translation>
    </message>
    <message>
        <location filename="../ui/widgets/licence_dialog.py" line="106" />
        <source>in no licence group</source>
        <translation>w żadnej grupie licencji</translation>
    </message>
    <message>
        <location filename="../ui/widgets/licence_dialog.py" line="110" />
        <source>No repository ships the text of this licence.

That is not unusual for licences that only exist as a reference to something published elsewhere, but it does mean nobody can read it here. Look it up before accepting.</source>
        <translation>Żadne repozytorium nie dostarcza tekstu tej licencji.

To nic nadzwyczajnego przy licencjach, które istnieją tylko jako odesłanie do czegoś opublikowanego gdzie indziej, ale oznacza, że nie da się jej tutaj przeczytać. Sprawdź ją, zanim zaakceptujesz.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/licence_dialog.py" line="118" />
        <source>Accepting adds one line to /etc/portage/package.license for {package} only. It does not change ACCEPT_LICENSE and it does not accept the rest of the licence group.</source>
        <translation>Akceptacja dopisuje jedną linię do /etc/portage/package.license wyłącznie dla {package}. Nie zmienia ACCEPT_LICENSE i nie akceptuje reszty grupy licencji.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/licence_dialog.py" line="126" />
        <source>Accept for this package</source>
        <translation>Zaakceptuj dla tego pakietu</translation>
    </message>
    <message>
        <location filename="../ui/widgets/licence_dialog.py" line="129" />
        <source>Cancel</source>
        <translation>Anuluj</translation>
    </message>
</context><context>
    <name>LogView</name>
    <message>
        <location filename="../ui/widgets/log_view.py" line="159" />
        <source>running…</source>
        <translation>w trakcie…</translation>
    </message>
    <message>
        <location filename="../ui/widgets/log_view.py" line="221" />
        <source>Stop</source>
        <translation>Przerwij</translation>
    </message>
    <message>
        <location filename="../ui/widgets/log_view.py" line="223" />
        <source>Sends the same interrupt Ctrl+C does, so Portage can tidy up.</source>
        <translation>Wysyła to samo przerwanie co Ctrl+C, żeby Portage zdążył posprzątać.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/log_view.py" line="225" />
        <source>Hide</source>
        <translation>Ukryj</translation>
    </message>
</context><context>
    <name>MainWindow</name>
    <message>
        <location filename="../ui/main_window.py" line="323" />
        <source>Showing packages from all repositories.</source>
        <translation>Pokazywane są pakiety ze wszystkich repozytoriów.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="326" />
        <source>Overlay packages are hidden in the interface only.</source>
        <translation>Pakiety z overlayów są ukryte tylko w interfejsie.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="330" />
        <source>Masking happens per overlay on the Repositories screen — nothing has been written yet.</source>
        <translation>Maskowanie ustawia się osobno dla każdego overlaya na ekranie Repozytoria — na razie nic nie zostało zapisane.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="347" />
        <source>Finished.</source>
        <translation>Zakończono.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="349" />
        <source>Exit code {code}.</source>
        <translation>Kod wyjścia {code}.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="359" />
        <source>Cannot run this</source>
        <translation>Nie można tego uruchomić</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="431" />
        <location filename="../ui/main_window.py" line="426" />
        <location filename="../ui/main_window.py" line="417" />
        <location filename="../ui/main_window.py" line="390" />
        <source>Restore backup</source>
        <translation>Przywróć kopię zapasową</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="391" />
        <source>There are no backups of /etc/portage yet.</source>
        <translation>Nie ma jeszcze żadnej kopii /etc/portage.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="418" />
        <source>/etc/portage was restored from {path}.</source>
        <translation>Przywrócono /etc/portage z {path}.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="450" />
        <source>The installed {names} is from an older version. Run `sudo make install-system` — until then, writing to /etc may be refused.</source>
        <translation>Zainstalowany {names} pochodzi ze starszej wersji. Uruchom `sudo make install-system` — do tego czasu zapis do /etc może być odrzucany.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="476" />
        <source>Running as root</source>
        <translation>Uruchomiono jako root</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="477" />
        <source>Gentstore is running as root. It does not need to be: it asks for privileges only for the individual operations that require them.

Running a graphical application as root puts your whole desktop session at its mercy. Please close it and start it as your normal user.</source>
        <translation>Gentstore działa jako root. Nie musi: o uprawnienia prosi osobno, tylko przy tych operacjach, które ich naprawdę wymagają.

Uruchamianie aplikacji graficznej jako root oddaje jej całą sesję pulpitu. Zamknij ją i uruchom ze swojego zwykłego konta.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="584" />
        <location filename="../ui/main_window.py" line="496" />
        <source>About {app}</source>
        <translation>O programie {app}</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="497" />
        <source>{app} {version}

A graphical front-end for Portage on Gentoo Linux.
Licensed under the GNU GPL, version 2 or (at your option) any later version.</source>
        <translation>{app} {version}

Graficzna nakładka na Portage dla Gentoo Linux.
Udostępniany na licencji GNU GPL w wersji 2 lub, według twojego wyboru, dowolnej późniejszej.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="509" />
        <source>Log file</source>
        <translation>Plik logu</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="510" />
        <source>Messages are written to:
{path}</source>
        <translation>Komunikaty trafiają do:
{path}</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="551" />
        <source>&amp;File</source>
        <translation>&amp;Plik</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="552" />
        <source>Settings…</source>
        <translation>Ustawienia…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="553" />
        <source>Quit</source>
        <translation>Zakończ</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="555" />
        <source>&amp;Repositories</source>
        <translation>&amp;Repozytoria</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="556" />
        <source>Synchronise all repositories</source>
        <translation>Synchronizuj wszystkie repozytoria</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="557" />
        <source>Manage overlays</source>
        <translation>Zarządzaj overlayami</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="559" />
        <source>&amp;Package</source>
        <translation>P&amp;akiet</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="560" />
        <source>Search…</source>
        <translation>Szukaj…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="621" />
        <location filename="../ui/main_window.py" line="561" />
        <source>Update @world</source>
        <translation>Aktualizuj @world</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="563" />
        <source>&amp;System</source>
        <translation>&amp;System</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="564" />
        <source>Portage settings</source>
        <translation>Ustawienia Portage</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="565" />
        <source>Profile</source>
        <translation>Profil</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="566" />
        <source>Configuration files</source>
        <translation>Pliki konfiguracyjne</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="567" />
        <source>elog messages</source>
        <translation>Wiadomości elog</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="569" />
        <source>&amp;View</source>
        <translation>&amp;Widok</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="570" />
        <source>Go to</source>
        <translation>Przejdź do</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="574" />
        <source>Language</source>
        <translation>Język</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="576" />
        <source>System default</source>
        <translation>Domyślny systemu</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="580" />
        <source>Interface size</source>
        <translation>Rozmiar interfejsu</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="600" />
        <location filename="../ui/main_window.py" line="581" />
        <source>Command log</source>
        <translation>Log poleceń</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="583" />
        <source>&amp;Help</source>
        <translation>P&amp;omoc</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="585" />
        <source>Where is the log file?</source>
        <translation>Gdzie jest plik logu?</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="620" />
        <source>Synchronise</source>
        <translation>Synchronizuj</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="622" />
        <source>Overlays</source>
        <translation>Overlaye</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="623" />
        <source>Log</source>
        <translation>Log</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="628" />
        <source>never synchronised</source>
        <translation>brak synchronizacji</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="629" />
        <source>sync: {when}</source>
        <translation>sync: {when}</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="635" />
        <source>@world: unknown</source>
        <translation>@world: nieznane</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/main_window.py" line="636" />
        <source>@world: %n entry(s)</source>
        <translation>
            <numerusform>@world: %n wpis</numerusform>
            <numerusform>@world: %n wpisy</numerusform>
            <numerusform>@world: %n wpisów</numerusform>
        </translation>
    </message>
</context><context>
    <name>MakeConfPage</name>
    <message>
        <location filename="../ui/pages/makeconf.py" line="363" />
        <source>Changed one line in {path}:
{line}</source>
        <translation>Zmieniono jedną linię w {path}:
{line}</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="370" />
        <source>Cancelled — nothing was written.</source>
        <translation>Anulowano — nic nie zostało zapisane.</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="373" />
        <source>Nothing was written: {error}</source>
        <translation>Nic nie zostało zapisane: {error}</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="386" />
        <source>How many compiler jobs run at once.</source>
        <translation>Ile zadań kompilatora działa naraz.</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="387" />
        <source>Options added to every emerge command.</source>
        <translation>Opcje dodawane do każdego wywołania emerge.</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="388" />
        <source>USE flags for the whole system, on top of what the profile sets.</source>
        <translation>Flagi USE dla całego systemu, ponad to, co ustawia profil.</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="391" />
        <source>Which keywords count as installable. ~amd64 here puts the whole system on testing versions; a line per package is nearly always the better idea.</source>
        <translation>Które keywordy uznajemy za instalowalne. ~amd64 tutaj przestawia cały system na wersje testowe; linia na pakiet jest prawie zawsze lepszym pomysłem.</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="395" />
        <source>Which licences may be installed without asking.</source>
        <translation>Które licencje można instalować bez pytania.</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="396" />
        <source>Which graphics drivers get built.</source>
        <translation>Które sterowniki graficzne są budowane.</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="397" />
        <source>Instruction sets this processor has.</source>
        <translation>Zestawy instrukcji tego procesora.</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="398" />
        <source>How Portage itself behaves while building.</source>
        <translation>Jak zachowuje się sam Portage przy budowaniu.</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="399" />
        <source>Which translations get installed.</source>
        <translation>Które tłumaczenia są instalowane.</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="404" />
        <source>one job per core</source>
        <translation>jedno zadanie na rdzeń</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="405" />
        <source>one job per core would need more memory than this machine has; roughly 2 GiB per job is the usual rule</source>
        <translation>jedno zadanie na rdzeń wymagałoby więcej pamięci, niż ta maszyna ma; przyjmuje się mniej więcej 2 GiB na zadanie</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="409" />
        <source>as cpuid2cpuflags reports it</source>
        <translation>tak, jak podaje cpuid2cpuflags</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="416" />
        <source>Changing a value here replaces one line and leaves the rest of the file exactly as it is — comments, ordering and all. The difference is shown before anything is written.</source>
        <translation>Zmiana wartości podmienia jedną linię i zostawia resztę pliku dokładnie taką, jaka jest — z komentarzami i kolejnością. Różnica jest pokazywana, zanim cokolwiek zostanie zapisane.</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="424" />
        <source>now</source>
        <translation>teraz</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="424" />
        <source>after this change</source>
        <translation>po tej zmianie</translation>
    </message>
</context><context>
    <name>MasksPage</name>
    <message>
        <location filename="../ui/pages/masks.py" line="307" />
        <source>No entries.</source>
        <translation>Brak wpisów.</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="346" />
        <source>Reading every ebuild's LICENSE…</source>
        <translation>Czytam LICENSE każdego ebuilda…</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="353" />
        <source>Nothing here changes its licence with a flag.</source>
        <translation>Nic tutaj nie zmienia swojej licencji przez flagę.</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="376" />
        <source>Turning {flag} on also means accepting {licences}</source>
        <translation>Włączenie {flag} oznacza też zaakceptowanie {licences}</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="379" />
        <source>Turning {flag} off also means accepting {licences}</source>
        <translation>Wyłączenie {flag} oznacza też zaakceptowanie {licences}</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="416" />
        <source>Removed the line from {path}.</source>
        <translation>Usunięto linię z pliku {path}.</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="423" />
        <source>Cancelled — nothing was written.</source>
        <translation>Anulowano — nic nie zostało zapisane.</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="426" />
        <source>Nothing was written: {error}</source>
        <translation>Nic nie zostało zapisane: {error}</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="439" />
        <source>Versions accepted despite not being marked stable for this architecture.</source>
        <translation>Wersje zaakceptowane mimo braku oznaczenia jako stabilne dla tej architektury.</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="442" />
        <source>Versions installed despite a developer having masked them.</source>
        <translation>Wersje instalowane mimo maski założonej przez dewelopera.</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="443" />
        <source>Licences accepted for one package rather than system-wide.</source>
        <translation>Licencje zaakceptowane dla jednego pakietu, a nie dla całego systemu.</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="444" />
        <source>Versions you have blocked yourself.</source>
        <translation>Wersje zablokowane przez Ciebie.</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="455" />
        <source>Licences that depend on a USE flag</source>
        <translation>Licencje zależne od flagi USE</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="457" />
        <source>Not a file — worked out. These packages carry a licence you have not accepted, hidden behind a flag that is currently off. Nothing is wrong with them today; turn the flag on and the install stops.</source>
        <translation>To nie plik — to wynik obliczenia. Te pakiety niosą licencję, której nie zaakceptowałeś, schowaną za flagą, która jest teraz wyłączona. Dziś nic im nie brakuje; włącz flagę, a instalacja się zatrzyma.</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="470" />
        <source>empty</source>
        <translation>puste</translation>
    </message>
</context><context>
    <name>NewsEntry</name>
    <message>
        <location filename="../ui/widgets/news_list.py" line="92" />
        <source>Collapse</source>
        <translation>Zwiń</translation>
    </message>
    <message>
        <location filename="../ui/widgets/news_list.py" line="92" />
        <source>Read</source>
        <translation>Czytaj</translation>
    </message>
    <message>
        <location filename="../ui/widgets/news_list.py" line="96" />
        <source>unread</source>
        <translation>nieprzeczytane</translation>
    </message>
    <message>
        <location filename="../ui/widgets/news_list.py" line="100" />
        <source>concerns you because of: {reason}</source>
        <translation>dotyczy Cię przez: {reason}</translation>
    </message>
    <message>
        <location filename="../ui/widgets/news_list.py" line="105" />
        <source>posted to everyone</source>
        <translation>dla wszystkich</translation>
    </message>
</context><context>
    <name>OfficialOnlyControl</name>
    <message>
        <location filename="../ui/widgets/official_toggle.py" line="110" />
        <source>off</source>
        <translation>wył.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/official_toggle.py" line="111" />
        <source>hide in GUI</source>
        <translation>ukryj w GUI</translation>
    </message>
    <message>
        <location filename="../ui/widgets/official_toggle.py" line="111" />
        <source>mask in Portage</source>
        <translation>maskuj w Portage</translation>
    </message>
    <message>
        <location filename="../ui/widgets/official_toggle.py" line="114" />
        <source>Only ::gentoo</source>
        <translation>Tylko ::gentoo</translation>
    </message>
    <message>
        <location filename="../ui/widgets/official_toggle.py" line="115" />
        <source>a) hide in GUI</source>
        <translation>a) ukryj w GUI</translation>
    </message>
    <message>
        <location filename="../ui/widgets/official_toggle.py" line="116" />
        <source>b) mask in Portage</source>
        <translation>b) maskuj w Portage</translation>
    </message>
</context><context>
    <name>PackageDelegate</name>
    <message>
        <location filename="../ui/widgets/package_list.py" line="221" />
        <source>blocked</source>
        <translation>zablokowany</translation>
    </message>
    <message>
        <location filename="../ui/widgets/package_list.py" line="223" />
        <source>update available</source>
        <translation>jest aktualizacja</translation>
    </message>
    <message>
        <location filename="../ui/widgets/package_list.py" line="225" />
        <source>installed</source>
        <translation>zainstalowany</translation>
    </message>
</context><context>
    <name>Pages</name>
    <message>
        <location filename="../ui/pages/registry.py" line="67" />
        <source>Search &amp; install</source>
        <translation>Szukaj i instaluj</translation>
    </message>
    <message>
        <location filename="../ui/pages/registry.py" line="68" />
        <source>System update</source>
        <translation>Aktualizacja systemu</translation>
    </message>
    <message>
        <location filename="../ui/pages/registry.py" line="69" />
        <source>Repositories</source>
        <translation>Repozytoria</translation>
    </message>
    <message>
        <location filename="../ui/pages/registry.py" line="70" />
        <source>Masks &amp; licences</source>
        <translation>Maski i licencje</translation>
    </message>
    <message>
        <location filename="../ui/pages/registry.py" line="71" />
        <source>Configuration files</source>
        <translation>Pliki konfiguracyjne</translation>
    </message>
    <message>
        <location filename="../ui/pages/registry.py" line="72" />
        <source>make.conf</source>
        <translation>make.conf</translation>
    </message>
    <message>
        <location filename="../ui/pages/registry.py" line="73" />
        <source>elog messages</source>
        <translation>Wiadomości elog</translation>
    </message>
    <message>
        <location filename="../ui/pages/registry.py" line="74" />
        <source>@world set</source>
        <translation>Zestaw @world</translation>
    </message>
    <message>
        <location filename="../ui/pages/registry.py" line="75" />
        <source>Profile</source>
        <translation>Profil</translation>
    </message>
</context><context>
    <name>PlaceholderPage</name>
    <message>
        <location filename="../ui/pages/placeholder.py" line="68" />
        <source>This screen is built in session {session}.</source>
        <translation>Ten ekran powstaje w sesji {session}.</translation>
    </message>
</context><context>
    <name>ProfilePage</name>
    <message>
        <location filename="../ui/pages/profile.py" line="210" />
        <source>Change the profile</source>
        <translation>Zmiana profilu</translation>
    </message>
    <message>
        <location filename="../ui/pages/profile.py" line="211" />
        <source>Switch from
  {old}
to
  {new}?

This changes the default USE flags, which packages are masked and what counts as part of the system. Afterwards the machine has to be rebuilt to match:

  emerge --ask --verbose --update --deep --newuse @world

That is a long build, and it is not optional. This will run:

  eselect profile set {index}</source>
        <translation>Przełączyć z
  {old}
na
  {new}?

To zmienia domyślne flagi USE, to, które pakiety są zamaskowane, i to, co należy do zestawu systemowego. Potem trzeba przebudować maszynę, żeby się zgadzała:

  emerge --ask --verbose --update --deep --newuse @world

To długie budowanie i nie jest opcjonalne. Zostanie uruchomione:

  eselect profile set {index}</translation>
    </message>
    <message>
        <location filename="../ui/pages/profile.py" line="241" />
        <source>reading the profile list…</source>
        <translation>wczytywanie listy profili…</translation>
    </message>
    <message>
        <location filename="../ui/pages/profile.py" line="244" />
        <source>The profile is the closest thing Gentoo has to a choice of distribution. It sets the default USE flags, masks packages and decides what belongs to the system set. Changing it is not a setting — it is a decision followed by a full rebuild of everything installed.</source>
        <translation>Profil to najbliższa rzecz, jaką Gentoo ma do wyboru dystrybucji. Ustawia domyślne flagi USE, maskuje pakiety i decyduje, co należy do zestawu systemowego. Jego zmiana to nie ustawienie — to decyzja, po której następuje przebudowanie wszystkiego, co zainstalowane.</translation>
    </message>
    <message>
        <location filename="../ui/pages/profile.py" line="251" />
        <source>filter, e.g. plasma or hardened</source>
        <translation>filtr, np. plasma albo hardened</translation>
    </message>
    <message>
        <location filename="../ui/pages/profile.py" line="252" />
        <source>Refresh</source>
        <translation>Odśwież</translation>
    </message>
</context><context>
    <name>ReposPage</name>
    <message>
        <location filename="../ui/pages/repos.py" line="410" />
        <source>No catalogue yet. Press Refresh to fetch Gentoo's list of repositories.</source>
        <translation>Nie ma jeszcze katalogu. Naciśnij „Odśwież”, żeby pobrać listę repozytoriów Gentoo.</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="426" />
        <source>Nothing matches “{query}”.</source>
        <translation>Nic nie pasuje do „{query}”.</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="444" />
        <source>Showing {shown} of {total}. Type to narrow the list.</source>
        <translation>Widocznych {shown} z {total}. Wpisz coś, żeby zawęzić listę.</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="483" />
        <source>This will run:

eselect repository enable {name}
emaint sync -r {name}

Source: {uri}</source>
        <translation>Zostanie uruchomione:

eselect repository enable {name}
emaint sync -r {name}

Źródło: {uri}</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="488" />
        <source>This repository is not run by Gentoo. Its ebuilds will run as root while building packages.</source>
        <translation>Tego repozytorium nie prowadzi Gentoo. Jego ebuildy będą się wykonywać jako root podczas budowania pakietów.</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="492" />
        <source>Enable repository</source>
        <translation>Włączenie repozytorium</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="529" />
        <location filename="../ui/pages/repos.py" line="509" />
        <source>Remove repository</source>
        <translation>Usunięcie repozytorium</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="510" />
        <source>The main repository cannot be removed.</source>
        <translation>Głównego repozytorium nie da się usunąć.</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="515" />
        <source>This will run:

eselect repository remove -f {name}</source>
        <translation>Zostanie uruchomione:

eselect repository remove -f {name}</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/repos.py" line="519" />
        <source>%n installed package(s) came from this repository. They stay on the system but lose their ebuild, so nothing will update or rebuild them again:</source>
        <translation>
            <numerusform>%n zainstalowany pakiet pochodzi z tego repozytorium. Zostanie w systemie, ale straci swój ebuild, więc nic go już nie zaktualizuje ani nie przebuduje:</numerusform>
            <numerusform>%n zainstalowane pakiety pochodzą z tego repozytorium. Zostaną w systemie, ale stracą swoje ebuildy, więc nic ich już nie zaktualizuje ani nie przebuduje:</numerusform>
            <numerusform>%n zainstalowanych pakietów pochodzi z tego repozytorium. Zostaną w systemie, ale stracą swoje ebuildy, więc nic ich już nie zaktualizuje ani nie przebuduje:</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="553" />
        <source>Hide repository from Portage</source>
        <translation>Ukrycie repozytorium przed Portage</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/repos.py" line="554" />
        <source>%n installed package(s) came from ::{name}. Masking it means Portage stops offering updates for them — they are not removed, and nothing else changes.</source>
        <translation>
            <numerusform>%n zainstalowany pakiet pochodzi z ::{name}. Zamaskowanie oznacza, że Portage przestanie proponować dla niego aktualizacje — nie zostanie usunięty i nic więcej się nie zmieni.</numerusform>
            <numerusform>%n zainstalowane pakiety pochodzą z ::{name}. Zamaskowanie oznacza, że Portage przestanie proponować dla nich aktualizacje — nie zostaną usunięte i nic więcej się nie zmieni.</numerusform>
            <numerusform>%n zainstalowanych pakietów pochodzi z ::{name}. Zamaskowanie oznacza, że Portage przestanie proponować dla nich aktualizacje — nie zostaną usunięte i nic więcej się nie zmieni.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="591" />
        <source>Written to {path}.</source>
        <translation>Zapisano do {path}.</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="597" />
        <source>Cancelled — nothing was written.</source>
        <translation>Anulowano — nic nie zostało zapisane.</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="600" />
        <source>Nothing was written: {error}</source>
        <translation>Nic nie zostało zapisane: {error}</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="640" />
        <source>Defined by the profile, not by repos.conf.</source>
        <translation>Zdefiniowane przez profil, nie przez repos.conf.</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="648" />
        <source>Show in Portage again</source>
        <translation>Pokaż znów w Portage</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="648" />
        <source>Hide from Portage</source>
        <translation>Ukryj przed Portage</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="655" />
        <source>Configured</source>
        <translation>Skonfigurowane</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="656" />
        <source>Synchronise all</source>
        <translation>Synchronizuj wszystkie</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="658" />
        <source>All repositories</source>
        <translation>Wszystkie repozytoria</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="659" />
        <source>name or keyword, e.g. steam</source>
        <translation>nazwa lub słowo kluczowe, np. steam</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="660" />
        <source>Refresh</source>
        <translation>Odśwież</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="662" />
        <source>Add by hand…</source>
        <translation>Dodaj ręcznie…</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="663" />
        <source>Synchronise</source>
        <translation>Synchronizuj</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="664" />
        <source>Remove…</source>
        <translation>Usuń…</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/repos.py" line="666" />
        <source>%n known</source>
        <translation>
            <numerusform>%n znane</numerusform>
            <numerusform>%n znane</numerusform>
            <numerusform>%n znanych</numerusform>
        </translation>
    </message>
</context><context>
    <name>RequiredChanges</name>
    <message>
        <location filename="../ui/widgets/required_changes.py" line="182" />
        <source>Nothing is wrong with the package you asked for. Something it needs is built without a feature it requires, and Portage will not guess whether rebuilding it is acceptable to you. Each line below turns one feature on for one package.</source>
        <translation>Z pakietem, o który prosiłeś, wszystko jest w porządku. Coś, czego on potrzebuje, jest zbudowane bez wymaganej funkcji, a Portage nie zgaduje, czy zgadzasz się na przebudowanie tego. Każda linia poniżej włącza jedną funkcję w jednym pakiecie.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/required_changes.py" line="188" />
        <source>Portage stopped before building anything because it needs these lines in your configuration first. Each one is shown with the package that asked for it.</source>
        <translation>Portage zatrzymało się przed zbudowaniem czegokolwiek, bo najpierw potrzebuje tych linii w Twojej konfiguracji. Przy każdej widać pakiet, który o nią poprosił.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/required_changes.py" line="206" />
        <source>Asked for by {package}</source>
        <translation>Wymaga tego {package}</translation>
    </message>
    <message>
        <location filename="../ui/widgets/required_changes.py" line="235" />
        <source>Add this line…</source>
        <translation>Dodaj tę linię…</translation>
    </message>
    <message>
        <location filename="../ui/widgets/required_changes.py" line="251" />
        <source>Emerge needs a change first</source>
        <translation>Emerge potrzebuje najpierw zmiany</translation>
    </message>
</context><context>
    <name>RestoreDialog</name>
    <message>
        <location filename="../ui/widgets/restore_dialog.py" line="160" />
        <source>Restore /etc/portage</source>
        <translation>Przywracanie /etc/portage</translation>
    </message>
    <message>
        <location filename="../ui/widgets/restore_dialog.py" line="162" />
        <source>Restoring replaces {path} with the copy you pick. The state you have now is backed up first, so this can itself be undone.</source>
        <translation>Przywrócenie zastąpi {path} wybraną kopią. Stan, który masz teraz, zostanie najpierw odłożony na bok, więc i to da się cofnąć.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/restore_dialog.py" line="167" />
        <source>Backups</source>
        <translation>Kopie</translation>
    </message>
    <message>
        <location filename="../ui/widgets/restore_dialog.py" line="168" />
        <source>What would change</source>
        <translation>Co się zmieni</translation>
    </message>
    <message>
        <location filename="../ui/widgets/restore_dialog.py" line="169" />
        <source>now</source>
        <translation>teraz</translation>
    </message>
    <message>
        <location filename="../ui/widgets/restore_dialog.py" line="169" />
        <source>the backup</source>
        <translation>kopia</translation>
    </message>
    <message>
        <location filename="../ui/widgets/restore_dialog.py" line="172" />
        <source>There are no backups yet.</source>
        <translation>Nie ma jeszcze żadnej kopii.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/restore_dialog.py" line="175" />
        <source>This backup matches what you have now — nothing would change.</source>
        <translation>Ta kopia zgadza się z tym, co masz teraz — nic by się nie zmieniło.</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/widgets/restore_dialog.py" line="184" />
        <source>%n file(s) restored</source>
        <translation>
            <numerusform>%n plik przywrócony</numerusform>
            <numerusform>%n pliki przywrócone</numerusform>
            <numerusform>%n plików przywróconych</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/widgets/restore_dialog.py" line="185" />
        <source>%n deleted</source>
        <translation>
            <numerusform>%n usunięty</numerusform>
            <numerusform>%n usunięte</numerusform>
            <numerusform>%n usuniętych</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/widgets/restore_dialog.py" line="186" />
        <source>%n replaced</source>
        <translation>
            <numerusform>%n podmieniony</numerusform>
            <numerusform>%n podmienione</numerusform>
            <numerusform>%n podmienionych</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/widgets/restore_dialog.py" line="193" />
        <source>Restore</source>
        <translation>Przywróć</translation>
    </message>
    <message>
        <location filename="../ui/widgets/restore_dialog.py" line="198" />
        <source>Cancel</source>
        <translation>Anuluj</translation>
    </message>
</context><context>
    <name>SearchPage</name>
    <message>
        <location filename="../ui/pages/search.py" line="385" />
        <source>unavailable</source>
        <translation>niedostępne</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="387" />
        <source>Portage could not be read: {error}</source>
        <translation>Nie udało się odczytać Portage: {error}</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="990" />
        <location filename="../ui/pages/search.py" line="402" />
        <source>all</source>
        <translation>wszystkie</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="567" />
        <source>installed: {versions}</source>
        <translation>zainstalowana: {versions}</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="570" />
        <source>not installed</source>
        <translation>nie zainstalowany</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="572" />
        <source>no description</source>
        <translation>brak opisu</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="592" />
        <source>download: {size}</source>
        <translation>pobranie: {size}</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="627" />
        <source>installed</source>
        <translation>zainstalowana</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="629" />
        <source>live</source>
        <translation>live</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="631" />
        <source>blocked</source>
        <translation>zablokowana</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="633" />
        <source>unchecked</source>
        <translation>niesprawdzona</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="635" />
        <source>testing</source>
        <translation>testowa</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="637" />
        <source>stable</source>
        <translation>stabilna</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="658" />
        <source>Pretend</source>
        <translation>Pretend</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="660" />
        <source>Uninstall</source>
        <translation>Odinstaluj</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="715" />
        <location filename="../ui/pages/search.py" line="660" />
        <source>Add to @world</source>
        <translation>Dodaj do @world</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="662" />
        <source>Update</source>
        <translation>Zaktualizuj</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="662" />
        <source>Install</source>
        <translation>Zainstaluj</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="705" />
        <source>Update package</source>
        <translation>Aktualizacja pakietu</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="705" />
        <source>Install package</source>
        <translation>Instalacja pakietu</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="730" />
        <source>Uninstall package</source>
        <translation>Odinstalowanie pakietu</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="731" />
        <source>The log above lists what would be removed.

Remove {package} now?

{command}</source>
        <translation>Log powyżej pokazuje, co zostanie usunięte.

Usunąć teraz {package}?

{command}</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="745" />
        <source>This will run:

{command}</source>
        <translation>Zostanie uruchomione:

{command}</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="871" />
        <source>Cancelled — nothing was written.</source>
        <translation>Anulowano — nic nie zostało zapisane.</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="874" />
        <source>Nothing was written: {error}</source>
        <translation>Nic nie zostało zapisane: {error}</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="884" />
        <source>No change was needed: {detail}</source>
        <translation>Zmiana nie była potrzebna: {detail}</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="888" />
        <source>Removed the line from {path}.</source>
        <translation>Usunięto linię z pliku {path}.</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="890" />
        <source>Replaced one line in {path} with:
{line}</source>
        <translation>Podmieniono jedną linię w pliku {path} na:
{line}</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="893" />
        <source>Added to {path}:
{line}</source>
        <translation>Dopisano do pliku {path}:
{line}</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="953" />
        <source>loading…</source>
        <translation>wczytywanie…</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/search.py" line="955" />
        <source>%n package(s)</source>
        <translation>
            <numerusform>%n pakiet</numerusform>
            <numerusform>%n pakiety</numerusform>
            <numerusform>%n pakietów</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/search.py" line="957" />
        <source>%n result(s)</source>
        <translation>
            <numerusform>%n wynik</numerusform>
            <numerusform>%n wyniki</numerusform>
            <numerusform>%n wyników</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/search.py" line="961" />
        <source>%n package(s) outside ::gentoo hidden. Overlays keep syncing.</source>
        <translation>
            <numerusform>Ukryto %n pakiet spoza ::gentoo. Overlaye nadal się synchronizują.</numerusform>
            <numerusform>Ukryto %n pakiety spoza ::gentoo. Overlaye nadal się synchronizują.</numerusform>
            <numerusform>Ukryto %n pakietów spoza ::gentoo. Overlaye nadal się synchronizują.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="970" />
        <source>Nothing matches the query.</source>
        <translation>Nic nie pasuje do zapytania.</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="996" />
        <location filename="../ui/pages/search.py" line="972" />
        <source>Type a name, a category or a word from the description.</source>
        <translation>Wpisz nazwę, kategorię albo słowo z opisu.</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="978" />
        <source>name, category or description</source>
        <translation>nazwa, kategoria lub opis</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="986" />
        <source>VERSION</source>
        <translation>WERSJA</translation>
    </message>
</context><context>
    <name>SettingsDialog</name>
    <message>
        <location filename="../ui/settings_dialog.py" line="159" />
        <source>sudo needs a terminal or SUDO_ASKPASS to ask for the password; without one, privileged operations will not run.</source>
        <translation>sudo potrzebuje terminala albo SUDO_ASKPASS, żeby zapytać o hasło; bez tego operacje uprzywilejowane się nie wykonają.</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="164" />
        <source>pkexec asks in a window and names what it is being asked for.</source>
        <translation>pkexec pyta w okienku i nazywa, o co jest proszony.</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="165" />
        <source>pkexec when it is available, sudo otherwise.</source>
        <translation>pkexec, jeśli jest dostępny, w przeciwnym razie sudo.</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="169" />
        <source>Everything is compiled from source, which is the Gentoo default.</source>
        <translation>Wszystko jest kompilowane ze źródeł — tak Gentoo działa domyślnie.</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="170" />
        <source>none configured</source>
        <translation>żaden nieskonfigurowany</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="171" />
        <source>A prebuilt package is used only when its USE flags and dependencies match this system exactly, so nothing about *what* gets installed changes — only how it arrives. Binary hosts: {hosts}.</source>
        <translation>Gotowy pakiet zostanie użyty tylko wtedy, gdy jego flagi USE i zależności dokładnie pasują do tego systemu — więc nie zmienia się to, *co* zostanie zainstalowane, a jedynie sposób, w jaki przychodzi. Repozytoria binarne: {hosts}.</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="178" />
        <source>Settings</source>
        <translation>Ustawienia</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="179" />
        <source>Language</source>
        <translation>Język</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="180" />
        <source>System default</source>
        <translation>Domyślny systemu</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="184" />
        <source>Interface size</source>
        <translation>Rozmiar interfejsu</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="185" />
        <source>Becoming root</source>
        <translation>Podnoszenie uprawnień</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="186" />
        <source>automatic</source>
        <translation>automatycznie</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="190" />
        <source>Use binary packages</source>
        <translation>Pakiety binarne</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="191" />
        <source>pass --getbinpkg when installing</source>
        <translation>przekazuj --getbinpkg przy instalacji</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="193" />
        <source>Backup form</source>
        <translation>Postać kopii</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="194" />
        <source>a directory in /etc</source>
        <translation>katalog w /etc</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="195" />
        <source>one .tar.gz archive</source>
        <translation>jedno archiwum .tar.gz</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="196" />
        <source>Backups kept</source>
        <translation>Trzymanych kopii</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="202" />
        <source>Save</source>
        <translation>Zapisz</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="206" />
        <source>Cancel</source>
        <translation>Anuluj</translation>
    </message>
</context><context>
    <name>Sidebar</name>
    <message>
        <location filename="../ui/widgets/sidebar.py" line="144" />
        <source>Management</source>
        <translation>Zarządzanie</translation>
    </message>
    <message>
        <location filename="../ui/widgets/sidebar.py" line="145" />
        <source>Backup</source>
        <translation>Kopia zapasowa</translation>
    </message>
    <message>
        <location filename="../ui/widgets/sidebar.py" line="146" />
        <source>none yet</source>
        <translation>jeszcze brak</translation>
    </message>
    <message>
        <location filename="../ui/widgets/sidebar.py" line="147" />
        <source>Restore…</source>
        <translation>Przywróć…</translation>
    </message>
</context><context>
    <name>UpdatePage</name>
    <message>
        <location filename="../ui/pages/update.py" line="546" />
        <source>Update the system</source>
        <translation>Aktualizacja systemu</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="547" />
        <source>Nothing has been previewed yet. Run step 3 first to see what would change.

Run the update anyway?</source>
        <translation>Nic jeszcze nie zostało obliczone. Uruchom najpierw krok 3, żeby zobaczyć, co się zmieni.

Uruchomić aktualizację mimo to?</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="569" />
        <source>Remove unused packages</source>
        <translation>Usunięcie nieużywanych pakietów</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/update.py" line="570" />
        <source>%n package(s) are no longer needed by anything installed:</source>
        <translation>
            <numerusform>%n pakiet nie jest już potrzebny niczemu, co masz zainstalowane:</numerusform>
            <numerusform>%n pakiety nie są już potrzebne niczemu, co masz zainstalowane:</numerusform>
            <numerusform>%n pakietów nie jest już potrzebnych niczemu, co masz zainstalowane:</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="575" />
        <source>Remove them?</source>
        <translation>Usunąć je?</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="619" />
        <source>last synchronised {when}</source>
        <translation>ostatnia synchronizacja {when}</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="628" />
        <source>Synchronise repositories</source>
        <translation>Synchronizacja repozytoriów</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="629" />
        <source>Read the news</source>
        <translation>Przeczytaj wiadomości</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="630" />
        <source>See what would change</source>
        <translation>Zobacz, co się zmieni</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="631" />
        <source>Update @world</source>
        <translation>Zaktualizuj @world</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="632" />
        <source>Remove what is no longer needed</source>
        <translation>Usuń to, co niepotrzebne</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="633" />
        <source>Configuration files</source>
        <translation>Pliki konfiguracyjne</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="634" />
        <source>Security advisories</source>
        <translation>Ostrzeżenia bezpieczeństwa</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="639" />
        <source>Fetches the current state of every configured repository. Nothing is installed or changed — after this, Portage simply knows what exists.</source>
        <translation>Pobiera bieżący stan każdego skonfigurowanego repozytorium. Nic nie zostaje zainstalowane ani zmienione — po tym kroku Portage po prostu wie, co istnieje.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="643" />
        <source>Repositories ship notes when an update needs a hand. Only the ones that concern this system are listed, and each says why it does.</source>
        <translation>Repozytoria dołączają notatki, gdy aktualizacja wymaga interwencji. Na liście są tylko te, które dotyczą tego systemu, i przy każdej napisane jest dlaczego.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="647" />
        <source>Asks Portage what it would do, without doing any of it. The table below is the same list emerge prints, sorted into columns.</source>
        <translation>Pyta Portage, co by zrobił, nie robiąc niczego. Tabela poniżej to ta sama lista, którą wypisuje emerge, rozłożona na kolumny.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="651" />
        <source>Builds and installs everything from the preview. The log at the bottom of the window shows the output as it happens and can stop it at any point — the same interrupt Ctrl+C sends, so Portage can tidy up.</source>
        <translation>Buduje i instaluje wszystko z podglądu. Log na dole okna pokazuje wyjście na bieżąco i pozwala przerwać w dowolnym momencie — tym samym przerwaniem, które wysyła Ctrl+C, żeby Portage zdążył posprzątać.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="656" />
        <source>Finds packages nothing depends on any more. The list is always shown before anything is removed. Afterwards, @preserved-rebuild rebuilds whatever was still using a library that has just gone.</source>
        <translation>Znajduje pakiety, od których nic już nie zależy. Lista jest zawsze pokazywana, zanim cokolwiek zniknie. Potem @preserved-rebuild przebudowuje to, co korzystało z biblioteki, która właśnie odeszła.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="661" />
        <source>Updates leave new versions of configuration files beside the old ones rather than overwriting them. Deciding between the two is the last step.</source>
        <translation>Aktualizacje zostawiają nowe wersje plików konfiguracyjnych obok starych, zamiast je nadpisywać. Rozstrzygnięcie między nimi to ostatni krok.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="665" />
        <source>Compares what is installed against Gentoo's security advisories.</source>
        <translation>Porównuje to, co zainstalowane, z ostrzeżeniami bezpieczeństwa Gentoo.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="672" />
        <source>Two packages block each other. Usually one of them has to be removed first, or a newer version accepted.</source>
        <translation>Dwa pakiety blokują się nawzajem. Zwykle trzeba najpierw usunąć jeden albo zaakceptować nowszą wersję.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="676" />
        <source>Two versions of the same package are wanted in one slot. Something asked for a specific version — the lines above say which.</source>
        <translation>Dwie wersje tego samego pakietu trafiają do jednego slotu. Coś zażądało konkretnej wersji — linie powyżej mówią której.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="680" />
        <source>A USE flag has to change first. The Search screen can write it, with the line shown before it is saved.</source>
        <translation>Najpierw musi się zmienić flaga USE. Ekran „Szukaj i instaluj” potrafi to zapisać, pokazując linię przed zapisem.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="684" />
        <source>A version has to be accepted first. Open it on the Search screen: the block frame there writes the keyword line.</source>
        <translation>Najpierw trzeba zaakceptować wersję. Otwórz ją na ekranie „Szukaj i instaluj” — ramka blokady dopisze linię z keywordem.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="688" />
        <source>A masked version is needed. Read why it was masked first.</source>
        <translation>Potrzebna jest zamaskowana wersja. Przeczytaj najpierw, dlaczego ją zamaskowano.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="689" />
        <source>A licence has to be accepted first. The Search screen shows its full text.</source>
        <translation>Najpierw trzeba zaakceptować licencję. Ekran „Szukaj i instaluj” pokazuje jej pełny tekst.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="692" />
        <source>The USE flags asked for are not a combination the package allows.</source>
        <translation>Żądany zestaw flag USE to kombinacja, której pakiet nie dopuszcza.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="695" />
        <source>Something depends on a package no repository provides. An overlay may be missing.</source>
        <translation>Coś zależy od pakietu, którego nie dostarcza żadne repozytorium. Może brakować overlaya.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="699" />
        <source>The disk filled up.</source>
        <translation>Skończyło się miejsce na dysku.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="703" />
        <source>Failed: {package}</source>
        <translation>Niepowodzenie: {package}</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="707" />
        <source>Full log: {path}</source>
        <translation>Pełny log: {path}</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="718" />
        <source>Everything is up to date.</source>
        <translation>Wszystko jest aktualne.</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/update.py" line="719" />
        <source>%n package(s)</source>
        <translation>
            <numerusform>%n pakiet</numerusform>
            <numerusform>%n pakiety</numerusform>
            <numerusform>%n pakietów</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/update.py" line="729" />
        <source>%n to update</source>
        <translation>
            <numerusform>%n do aktualizacji</numerusform>
            <numerusform>%n do aktualizacji</numerusform>
            <numerusform>%n do aktualizacji</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/update.py" line="732" />
        <source>%n new</source>
        <translation>
            <numerusform>%n nowy</numerusform>
            <numerusform>%n nowe</numerusform>
            <numerusform>%n nowych</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/update.py" line="735" />
        <source>%n to rebuild</source>
        <translation>
            <numerusform>%n do przebudowy</numerusform>
            <numerusform>%n do przebudowy</numerusform>
            <numerusform>%n do przebudowy</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/update.py" line="738" />
        <source>%n to downgrade</source>
        <translation>
            <numerusform>%n do cofnięcia</numerusform>
            <numerusform>%n do cofnięcia</numerusform>
            <numerusform>%n do cofnięcia</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/update.py" line="740" />
        <source>%n binary</source>
        <translation>
            <numerusform>%n binarny</numerusform>
            <numerusform>%n binarne</numerusform>
            <numerusform>%n binarnych</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="742" />
        <source>download {size}</source>
        <translation>do pobrania {size}</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="753" />
        <source>Nothing to remove.</source>
        <translation>Nie ma czego usuwać.</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/update.py" line="754" />
        <source>%n package(s) could be removed.</source>
        <translation>
            <numerusform>Można usunąć %n pakiet.</numerusform>
            <numerusform>Można usunąć %n pakiety.</numerusform>
            <numerusform>Można usunąć %n pakietów.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="758" />
        <source>glsa-check is not installed. Install {package} to enable this check.</source>
        <translation>glsa-check nie jest zainstalowany. Zainstaluj {package}, żeby włączyć to sprawdzenie.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="765" />
        <source>This system is not affected by any known advisory.</source>
        <translation>Ten system nie jest objęty żadnym znanym ostrzeżeniem.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="772" />
        <source>Update</source>
        <translation>Aktualizacja</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="774" />
        <source>Six steps. Each one runs on its own, in any order, as often as you like.</source>
        <translation>Sześć kroków. Każdy uruchamia się osobno, w dowolnej kolejności, dowolną liczbę razy.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="783" />
        <source>Synchronise</source>
        <translation>Synchronizuj</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="785" />
        <source>Mark all as read</source>
        <translation>Oznacz wszystkie jako przeczytane</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="787" />
        <source>Nothing unread</source>
        <translation>Nic nieprzeczytanego</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="790" />
        <source>Calculate</source>
        <translation>Oblicz</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="794" />
        <source>Package</source>
        <translation>Pakiet</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="795" />
        <source>Version</source>
        <translation>Wersja</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="796" />
        <source>USE changes</source>
        <translation>Zmiany USE</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="797" />
        <source>Download</source>
        <translation>Pobranie</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="798" />
        <source>binary</source>
        <translation>binarny</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="801" />
        <source>Update now</source>
        <translation>Aktualizuj teraz</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="808" />
        <location filename="../ui/pages/update.py" line="802" />
        <source>Check</source>
        <translation>Sprawdź</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="804" />
        <source>Remove them…</source>
        <translation>Usuń je…</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="805" />
        <source>Rebuild what needs it</source>
        <translation>Przebuduj, co trzeba</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="807" />
        <source>Go to configuration files</source>
        <translation>Przejdź do plików konfiguracyjnych</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="811" />
        <source>Apply the fixes…</source>
        <translation>Zastosuj poprawki…</translation>
    </message>
</context><context>
    <name>UseFlagRow</name>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="169" />
        <source>Collapse</source>
        <translation>Zwiń</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="169" />
        <source>What does this change?</source>
        <translation>Co to zmienia?</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="174" />
        <source>ebuild default</source>
        <translation>domyślna w ebuildzie</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="175" />
        <source>profile</source>
        <translation>profil</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="176" />
        <source>make.conf</source>
        <translation>make.conf</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="177" />
        <source>per package</source>
        <translation>per pakiet</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="178" />
        <source>environment</source>
        <translation>środowisko</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="179" />
        <source>off by default</source>
        <translation>domyślnie wyłączona</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="185" />
        <source>locked on by the profile</source>
        <translation>wymuszona przez profil</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="187" />
        <source>locked on for this package</source>
        <translation>wymuszona dla tego pakietu</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="191" />
        <source>masked by the profile</source>
        <translation>zamaskowana przez profil</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="193" />
        <source>masked for this package</source>
        <translation>zamaskowana dla tego pakietu</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="196" />
        <source>changed by you</source>
        <translation>zmieniona przez Ciebie</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="198" />
        <source>named in REQUIRED_USE</source>
        <translation>występuje w REQUIRED_USE</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/widgets/use_flag_row.py" line="205" />
        <source>and %n more</source>
        <translation>
            <numerusform>i jeszcze %n</numerusform>
            <numerusform>i jeszcze %n</numerusform>
            <numerusform>i jeszcze %n</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="214" />
        <source>With {flag} on, this also installs: {atoms}</source>
        <translation>Z włączoną flagą {flag} doinstaluje też: {atoms}</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="220" />
        <source>{flag} adds no extra packages — it only changes how this one is built.</source>
        <translation>{flag} nie dokłada pakietów — zmienia tylko sposób budowania tego jednego.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="227" />
        <source>With {flag} off, it installs instead: {atoms}</source>
        <translation>Z wyłączoną flagą {flag} doinstaluje zamiast tego: {atoms}</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="235" />
        <source>These have to carry the same setting, so changing it may rebuild them: {atoms}</source>
        <translation>Te muszą mieć to samo ustawienie, więc zmiana może wymusić ich przebudowanie: {atoms}</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="244" />
        <source>description from metadata.xml</source>
        <translation>opis z metadata.xml</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="245" />
        <source>description from use.local.desc</source>
        <translation>opis z use.local.desc</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="246" />
        <source>description from use.desc</source>
        <translation>opis z use.desc</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="247" />
        <source>description from profiles/desc</source>
        <translation>opis z profiles/desc</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="248" />
        <source>no description in the repository</source>
        <translation>brak opisu w repozytorium</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="262" />
        <source>No description available.</source>
        <translation>Brak opisu.</translation>
    </message>
</context><context>
    <name>UseFlagsPanel</name>
    <message>
        <location filename="../ui/widgets/use_flags_panel.py" line="247" />
        <source>REQUIRED_USE is not satisfied. Portage would refuse this combination, so there is nothing worth writing yet.</source>
        <translation>REQUIRED_USE nie jest spełnione. Portage odrzuciłby taką kombinację, więc nie ma czego zapisywać.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flags_panel.py" line="284" />
        <source>does not apply</source>
        <translation>nie dotyczy</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flags_panel.py" line="285" />
        <source>not satisfied</source>
        <translation>niespełnione</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/widgets/use_flags_panel.py" line="295" />
        <source>%n flag(s) on</source>
        <translation>
            <numerusform>%n flaga włączona</numerusform>
            <numerusform>%n flagi włączone</numerusform>
            <numerusform>%n flag włączonych</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/widgets/use_flags_panel.py" line="297" />
        <source>%n changed</source>
        <translation>
            <numerusform>%n zmieniona</numerusform>
            <numerusform>%n zmienione</numerusform>
            <numerusform>%n zmienionych</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flags_panel.py" line="307" />
        <source>USE flags</source>
        <translation>Flagi USE</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flags_panel.py" line="308" />
        <source>REQUIRED_USE</source>
        <translation>REQUIRED_USE</translation>
    </message>
</context><context>
    <name>WorldPage</name>
    <message>
        <location filename="../ui/pages/world.py" line="292" />
        <source>Take out of @world</source>
        <translation>Usunięcie z @world</translation>
    </message>
    <message>
        <location filename="../ui/pages/world.py" line="293" />
        <source>Remove {atom} from @world?

This does not uninstall anything. It only stops the package being one you asked for, so the next --depclean will remove it if nothing else needs it.

This will run:

  emerge --deselect {atom}</source>
        <translation>Usunąć {atom} z @world?

To niczego nie odinstalowuje. Przestaje tylko traktować pakiet jako ten, o który prosiłeś — więc następny --depclean usunie go, jeśli nic innego go nie potrzebuje.

Zostanie uruchomione:

  emerge --deselect {atom}</translation>
    </message>
    <message>
        <location filename="../ui/pages/world.py" line="308" />
        <source>@world</source>
        <translation>@world</translation>
    </message>
    <message>
        <location filename="../ui/pages/world.py" line="310" />
        <source>The packages you asked for. Everything else installed is here because one of these needs it.</source>
        <translation>Pakiety, o które prosiłeś. Wszystko inne jest zainstalowane dlatego, że któryś z nich tego potrzebuje.</translation>
    </message>
    <message>
        <location filename="../ui/pages/world.py" line="315" />
        <source>Installed</source>
        <translation>Zainstalowane</translation>
    </message>
    <message>
        <location filename="../ui/pages/world.py" line="316" />
        <source>filter by name</source>
        <translation>filtruj po nazwie</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/world.py" line="321" />
        <source>%n package(s)</source>
        <translation>
            <numerusform>%n pakiet</numerusform>
            <numerusform>%n pakiety</numerusform>
            <numerusform>%n pakietów</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/world.py" line="323" />
        <source>showing the first %n</source>
        <translation>
            <numerusform>pokazano pierwszy %n</numerusform>
            <numerusform>pokazano pierwsze %n</numerusform>
            <numerusform>pokazano pierwszych %n</numerusform>
        </translation>
    </message>
</context><context>
    <name>WritePreview</name>
    <message>
        <location filename="../ui/widgets/write_preview.py" line="173" />
        <source>{file} is a directory, so the entry goes in a file of its own.</source>
        <translation>{file} jest katalogiem, więc wpis trafi do osobnego pliku.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/write_preview.py" line="176" />
        <source>This file already has an entry for it.</source>
        <translation>W tym pliku jest już taki wpis.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/write_preview.py" line="177" />
        <source>{file} is a single file; the line is added at the end.</source>
        <translation>{file} jest pojedynczym plikiem; linia zostanie dopisana na końcu.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/write_preview.py" line="180" />
        <source>Neither {file} nor a directory of that name exists yet. Gentoo recommends the directory form, so that is what will be created.</source>
        <translation>Nie ma jeszcze ani pliku {file}, ani katalogu o tej nazwie. Gentoo zaleca postać katalogu i taka powstanie.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/write_preview.py" line="188" />
        <source>One line is replaced:
− {old}
+ {new}</source>
        <translation>Podmieniona zostanie jedna linia:
− {old}
+ {new}</translation>
    </message>
    <message>
        <location filename="../ui/widgets/write_preview.py" line="192" />
        <source>One line is removed:
− {old}</source>
        <translation>Usunięta zostanie jedna linia:
− {old}</translation>
    </message>
    <message>
        <location filename="../ui/widgets/write_preview.py" line="193" />
        <source>One line is added. Everything else in the file is left alone.</source>
        <translation>Dopisana zostanie jedna linia. Reszta pliku zostaje bez zmian.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/write_preview.py" line="196" />
        <source>Will be written</source>
        <translation>Zostanie zapisane</translation>
    </message>
    <message>
        <location filename="../ui/widgets/write_preview.py" line="197" />
        <source>preview before saving</source>
        <translation>podgląd przed zapisem</translation>
    </message>
    <message>
        <location filename="../ui/widgets/write_preview.py" line="198" />
        <source>Discard changes</source>
        <translation>Wyczyść zmiany</translation>
    </message>
    <message>
        <location filename="../ui/widgets/write_preview.py" line="199" />
        <source>Saving…</source>
        <translation>Zapisywanie…</translation>
    </message>
    <message>
        <location filename="../ui/widgets/write_preview.py" line="199" />
        <source>Save</source>
        <translation>Zapisz</translation>
    </message>
</context><context>
    <name>_CatalogueRow</name>
    <message>
        <location filename="../ui/pages/repos.py" line="196" />
        <source>official</source>
        <translation>oficjalne</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="196" />
        <source>unofficial</source>
        <translation>nieoficjalne</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="199" />
        <source>already configured</source>
        <translation>już skonfigurowane</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="199" />
        <source>Enable</source>
        <translation>Włącz</translation>
    </message>
</context><context>
    <name>_ConditionalRow</name>
    <message>
        <location filename="../ui/pages/masks.py" line="142" />
        <source>Open this package</source>
        <translation>Otwórz ten pakiet</translation>
    </message>
</context><context>
    <name>_ConfiguredRow</name>
    <message>
        <location filename="../ui/pages/repos.py" line="132" />
        <source>main repository</source>
        <translation>repozytorium główne</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="132" />
        <source>overlay</source>
        <translation>overlay</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="134" />
        <source>hidden from Portage</source>
        <translation>ukryte przed Portage</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/repos.py" line="136" />
        <source>%n package(s)</source>
        <translation>
            <numerusform>%n pakiet</numerusform>
            <numerusform>%n pakiety</numerusform>
            <numerusform>%n pakietów</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="143" />
        <source>never synchronised</source>
        <translation>nigdy nie synchronizowane</translation>
    </message>
</context><context>
    <name>_EntryRow</name>
    <message>
        <location filename="../ui/pages/masks.py" line="122" />
        <source>Remove…</source>
        <translation>Usuń…</translation>
    </message>
</context><context>
    <name>_FileRow</name>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="111" />
        <source>new file</source>
        <translation>nowy plik</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="115" />
        <source>from {package}</source>
        <translation>od {package}</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="117" />
        <source>no package claims this file</source>
        <translation>żaden pakiet nie przyznaje się do tego pliku</translation>
    </message>
</context><context>
    <name>_ProfileRow</name>
    <message>
        <location filename="../ui/pages/profile.py" line="95" />
        <source>unmarked</source>
        <translation>bez oznaczenia</translation>
    </message>
    <message>
        <location filename="../ui/pages/profile.py" line="97" />
        <source>in use</source>
        <translation>w użyciu</translation>
    </message>
    <message>
        <location filename="../ui/pages/profile.py" line="97" />
        <source>Use this one…</source>
        <translation>Użyj tego…</translation>
    </message>
</context><context>
    <name>_VariableRow</name>
    <message>
        <location filename="../ui/pages/makeconf.py" line="142" />
        <source>not set in make.conf</source>
        <translation>nieustawione w make.conf</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="176" />
        <source>Portage uses: {value}</source>
        <translation>Portage używa: {value}</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="186" />
        <source>This assignment spans several lines; Gentstore will not rewrite it.</source>
        <translation>To przypisanie rozciąga się na kilka linii; Gentstore go nie przepisze.</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="198" />
        <source>A suggestion needs {package}; it is not installed.</source>
        <translation>Podpowiedź wymaga {package}; nie jest zainstalowany.</translation>
    </message>
</context><context>
    <name>_WorldRow</name>
    <message>
        <location filename="../ui/pages/world.py" line="115" />
        <source>not installed</source>
        <translation>nie zainstalowany</translation>
    </message>
    <message>
        <location filename="../ui/pages/world.py" line="117" />
        <source>Take out of @world…</source>
        <translation>Usuń z @world…</translation>
    </message>
</context></TS>
