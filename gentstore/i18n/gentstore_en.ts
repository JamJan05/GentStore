<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="en_GB">
<context>
    <name>AddOverlayDialog</name>
    <message>
        <location filename="../ui/widgets/add_overlay_dialog.py" line="125" />
        <source>Add a repository by hand</source>
        <translation>Add a repository by hand</translation>
    </message>
    <message>
        <location filename="../ui/widgets/add_overlay_dialog.py" line="127" />
        <source>Nobody has vouched for this repository.

Building a package runs its ebuild as root. Adding a repository means trusting whoever writes those ebuilds with your machine — not just now, but at every future sync. Add one only if you know who is behind it.</source>
        <translation>Nobody has vouched for this repository.

Building a package runs its ebuild as root. Adding a repository means trusting whoever writes those ebuilds with your machine — not just now, but at every future sync. Add one only if you know who is behind it.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/add_overlay_dialog.py" line="134" />
        <source>Name</source>
        <translation>Name</translation>
    </message>
    <message>
        <location filename="../ui/widgets/add_overlay_dialog.py" line="135" />
        <source>Sync type</source>
        <translation>Sync type</translation>
    </message>
    <message>
        <location filename="../ui/widgets/add_overlay_dialog.py" line="136" />
        <source>URL</source>
        <translation>URL</translation>
    </message>
    <message>
        <location filename="../ui/widgets/add_overlay_dialog.py" line="139" />
        <source>Add</source>
        <translation>Add</translation>
    </message>
    <message>
        <location filename="../ui/widgets/add_overlay_dialog.py" line="143" />
        <source>Cancel</source>
        <translation>Cancel</translation>
    </message>
</context><context>
    <name>BlockNotice</name>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="210" />
        <source>Not marked stable yet</source>
        <translation>Not marked stable yet</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="211" />
        <source>Never tested on this architecture</source>
        <translation>Never tested on this architecture</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="212" />
        <source>Marked as not working here</source>
        <translation>Marked as not working here</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="213" />
        <source>Masked by a developer</source>
        <translation>Masked by a developer</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="214" />
        <source>Licence not accepted</source>
        <translation>Licence not accepted</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="215" />
        <source>Portage will not install this version</source>
        <translation>Portage will not install this version</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="216" />
        <source>Could not be checked</source>
        <translation>Could not be checked</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="221" />
        <source>The version works, but nobody has declared it stable for {keyword} yet. Running testing versions of individual packages is ordinary practice on Gentoo; the line below tells Portage that this one is fine by you.</source>
        <translation>The version works, but nobody has declared it stable for {keyword} yet. Running testing versions of individual packages is ordinary practice on Gentoo; the line below tells Portage that this one is fine by you.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="227" />
        <source>This version carries no keyword for any architecture — which is also how every live ebuild looks, because it is built straight from the project's source repository and changes without warning. Expect to have to fix things yourself.</source>
        <translation>This version carries no keyword for any architecture — which is also how every live ebuild looks, because it is built straight from the project's source repository and changes without warning. Expect to have to fix things yourself.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="234" />
        <source>The ebuild states that this version does not work on this architecture. A line in package.accept_keywords would stop Portage refusing, but it would not make the package build.</source>
        <translation>The ebuild states that this version does not work on this architecture. A line in package.accept_keywords would stop Portage refusing, but it would not make the package build.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="240" />
        <source>Somebody decided this version should not be installed and wrote down why. Read that first: masks are usually about security holes, data loss or a package on its way out of the repository.</source>
        <translation>Somebody decided this version should not be installed and wrote down why. Read that first: masks are usually about security holes, data loss or a package on its way out of the repository.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="246" />
        <source>ACCEPT_LICENSE in make.conf is currently {accepted}, which does not cover every licence this package carries. Read the ones below and decide for this package alone.</source>
        <translation>ACCEPT_LICENSE in make.conf is currently {accepted}, which does not cover every licence this package carries. Read the ones below and decide for this package alone.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="252" />
        <source>Portage could not say whether this version installs, so Gentstore is not going to guess. Nothing here is necessarily wrong with the package — the check itself failed. Run emerge --pretend for this version to see Portage's own answer; the log has the details.</source>
        <translation>Portage could not say whether this version installs, so Gentstore is not going to guess. Nothing here is necessarily wrong with the package — the check itself failed. Run emerge --pretend for this version to see Portage's own answer; the log has the details.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="258" />
        <source>Portage gave this reason and Gentstore has nothing to add to it.</source>
        <translation>Portage gave this reason and Gentstore has nothing to add to it.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="264" />
        <source>empty</source>
        <translation>empty</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="270" />
        <source>Unmask anyway…</source>
        <translation>Unmask anyway…</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="272" />
        <source>Read the licence…</source>
        <translation>Read the licence…</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="274" />
        <source>Accept any keyword…</source>
        <translation>Accept any keyword…</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="275" />
        <source>Accept {keyword}…</source>
        <translation>Accept {keyword}…</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="279" />
        <source>** accepts this version whatever its keywords say, now and after every sync.</source>
        <translation>** accepts this version whatever its keywords say, now and after every sync.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="283" />
        <source>Not recommended: the ebuild says it does not work on this architecture.</source>
        <translation>Not recommended: the ebuild says it does not work on this architecture.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/block_notice.py" line="286" />
        <source>Not recommended: read the note above before going ahead.</source>
        <translation>Not recommended: read the note above before going ahead.</translation>
    </message>
</context><context>
    <name>CfgFilesPage</name>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="314" />
        <source>Replace {target} with the version {package} brought?

The file you have now is copied to /etc/config-archive first.</source>
        <translation>Replace {target} with the version {package} brought?

The file you have now is copied to /etc/config-archive first.</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="318" />
        <source>Keep {target} as it is and discard the new version?

{candidate} is deleted. Nothing else changes.</source>
        <translation>Keep {target} as it is and discard the new version?

{candidate} is deleted. Nothing else changes.</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="322" />
        <source>Save what is in the editor as {target}?

The file you have now is copied to /etc/config-archive first, and {candidate} is deleted.</source>
        <translation>Save what is in the editor as {target}?

The file you have now is copied to /etc/config-archive first, and {candidate} is deleted.</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="333" />
        <source>Configuration file</source>
        <translation>Configuration file</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="380" />
        <source>Cancelled — nothing was changed.</source>
        <translation>Cancelled — nothing was changed.</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="384" />
        <source>Nothing was changed: {error}</source>
        <translation>Nothing was changed: {error}</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="399" />
        <source>Kept your version of {target}.</source>
        <translation>Kept your version of {target}.</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="401" />
        <source>Saved the merged version as {target}.</source>
        <translation>Saved the merged version as {target}.</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="403" />
        <source>Replaced {target} with the new version.</source>
        <translation>Replaced {target} with the new version.</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="406" />
        <source>The previous version is at {path}.</source>
        <translation>The previous version is at {path}.</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="428" />
        <source>yours: {target}
new:   {candidate}</source>
        <translation>yours: {target}
new:   {candidate}</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="433" />
        <source>Back to the difference</source>
        <translation>Back to the difference</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="433" />
        <source>Merge by hand…</source>
        <translation>Merge by hand…</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="439" />
        <source>Waiting for a decision</source>
        <translation>Waiting for a decision</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="441" />
        <source>Portage never overwrites a configuration file you have edited. It writes the new version beside it and leaves both, which is what these are.</source>
        <translation>Portage never overwrites a configuration file you have edited. It writes the new version beside it and leaves both, which is what these are.</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="447" />
        <source>Nothing is waiting. Every configuration file is as you left it.</source>
        <translation>Nothing is waiting. Every configuration file is as you left it.</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="449" />
        <source>Keep mine</source>
        <translation>Keep mine</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="450" />
        <source>Take the new one</source>
        <translation>Take the new one</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="451" />
        <source>Save what I merged</source>
        <translation>Save what I merged</translation>
    </message>
</context><context>
    <name>Command</name>
    <message>
        <location filename="../runner/command.py" line="264" />
        <source>The command could not be started.</source>
        <translation>The command could not be started.</translation>
    </message>
    <message>
        <location filename="../runner/command.py" line="273" />
        <source>Stopped at your request.</source>
        <translation>Stopped at your request.</translation>
    </message>
    <message>
        <location filename="../runner/command.py" line="275" />
        <source>The command was terminated by a signal.</source>
        <translation>The command was terminated by a signal.</translation>
    </message>
</context><context>
    <name>DiffView</name>
    <message>
        <location filename="../ui/widgets/diff_view.py" line="112" />
        <source>the file you have</source>
        <translation>the file you have</translation>
    </message>
    <message>
        <location filename="../ui/widgets/diff_view.py" line="113" />
        <source>the version the package brought</source>
        <translation>the version the package brought</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/widgets/diff_view.py" line="118" />
        <source>%n more line(s) not shown</source>
        <translation>
            <numerusform>%n more line not shown</numerusform>
            <numerusform>%n more lines not shown</numerusform>
        </translation>
    </message>
</context><context>
    <name>ElogPage</name>
    <message>
        <location filename="../ui/pages/elog.py" line="321" />
        <source>error</source>
        <translation>error</translation>
    </message>
    <message>
        <location filename="../ui/pages/elog.py" line="322" />
        <source>warning</source>
        <translation>warning</translation>
    </message>
    <message>
        <location filename="../ui/pages/elog.py" line="323" />
        <source>quality notice</source>
        <translation>quality notice</translation>
    </message>
    <message>
        <location filename="../ui/pages/elog.py" line="324" />
        <source>note</source>
        <translation>note</translation>
    </message>
    <message>
        <location filename="../ui/pages/elog.py" line="325" />
        <source>information</source>
        <translation>information</translation>
    </message>
    <message>
        <location filename="../ui/pages/elog.py" line="329" />
        <source>package or text</source>
        <translation>package or text</translation>
    </message>
    <message>
        <location filename="../ui/pages/elog.py" line="331" />
        <source>all</source>
        <translation>all</translation>
    </message>
    <message>
        <location filename="../ui/pages/elog.py" line="339" />
        <source>No messages yet. They appear here after a package is installed.</source>
        <translation>No messages yet. They appear here after a package is installed.</translation>
    </message>
    <message>
        <location filename="../ui/pages/elog.py" line="341" />
        <source>Nothing matches the filter.</source>
        <translation>Nothing matches the filter.</translation>
    </message>
</context><context>
    <name>LicenceDialog</name>
    <message>
        <location filename="../ui/widgets/licence_dialog.py" line="103" />
        <source>Licence {name}</source>
        <translation>Licence {name}</translation>
    </message>
    <message>
        <location filename="../ui/widgets/licence_dialog.py" line="106" />
        <source>in no licence group</source>
        <translation>in no licence group</translation>
    </message>
    <message>
        <location filename="../ui/widgets/licence_dialog.py" line="110" />
        <source>No repository ships the text of this licence.

That is not unusual for licences that only exist as a reference to something published elsewhere, but it does mean nobody can read it here. Look it up before accepting.</source>
        <translation>No repository ships the text of this licence.

That is not unusual for licences that only exist as a reference to something published elsewhere, but it does mean nobody can read it here. Look it up before accepting.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/licence_dialog.py" line="118" />
        <source>Accepting adds one line to /etc/portage/package.license for {package} only. It does not change ACCEPT_LICENSE and it does not accept the rest of the licence group.</source>
        <translation>Accepting adds one line to /etc/portage/package.license for {package} only. It does not change ACCEPT_LICENSE and it does not accept the rest of the licence group.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/licence_dialog.py" line="126" />
        <source>Accept for this package</source>
        <translation>Accept for this package</translation>
    </message>
    <message>
        <location filename="../ui/widgets/licence_dialog.py" line="129" />
        <source>Cancel</source>
        <translation>Cancel</translation>
    </message>
</context><context>
    <name>LogView</name>
    <message>
        <location filename="../ui/widgets/log_view.py" line="154" />
        <source>running…</source>
        <translation>running…</translation>
    </message>
    <message>
        <location filename="../ui/widgets/log_view.py" line="216" />
        <source>Stop</source>
        <translation>Stop</translation>
    </message>
    <message>
        <location filename="../ui/widgets/log_view.py" line="218" />
        <source>Sends the same interrupt Ctrl+C does, so Portage can tidy up.</source>
        <translation>Sends the same interrupt Ctrl+C does, so Portage can tidy up.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/log_view.py" line="220" />
        <source>Hide</source>
        <translation>Hide</translation>
    </message>
</context><context>
    <name>MainWindow</name>
    <message>
        <location filename="../ui/main_window.py" line="323" />
        <source>Showing packages from all repositories.</source>
        <translation>Showing packages from all repositories.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="326" />
        <source>Overlay packages are hidden in the interface only.</source>
        <translation>Overlay packages are hidden in the interface only.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="330" />
        <source>Masking happens per overlay on the Repositories screen — nothing has been written yet.</source>
        <translation>Masking happens per overlay on the Repositories screen — nothing has been written yet.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="347" />
        <source>Finished.</source>
        <translation>Finished.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="349" />
        <source>Exit code {code}.</source>
        <translation>Exit code {code}.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="359" />
        <source>Cannot run this</source>
        <translation>Cannot run this</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="431" />
        <location filename="../ui/main_window.py" line="426" />
        <location filename="../ui/main_window.py" line="417" />
        <location filename="../ui/main_window.py" line="390" />
        <source>Restore backup</source>
        <translation>Restore backup</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="391" />
        <source>There are no backups of /etc/portage yet.</source>
        <translation>There are no backups of /etc/portage yet.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="418" />
        <source>/etc/portage was restored from {path}.</source>
        <translation>/etc/portage was restored from {path}.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="450" />
        <source>The installed {names} is from an older version. Run `sudo make install-system` — until then, writing to /etc may be refused.</source>
        <translation>The installed {names} is from an older version. Run `sudo make install-system` — until then, writing to /etc may be refused.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="476" />
        <source>Running as root</source>
        <translation>Running as root</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="477" />
        <source>Gentstore is running as root. It does not need to be: it asks for privileges only for the individual operations that require them.

Running a graphical application as root puts your whole desktop session at its mercy. Please close it and start it as your normal user.</source>
        <translation>Gentstore is running as root. It does not need to be: it asks for privileges only for the individual operations that require them.

Running a graphical application as root puts your whole desktop session at its mercy. Please close it and start it as your normal user.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="584" />
        <location filename="../ui/main_window.py" line="496" />
        <source>About {app}</source>
        <translation>About {app}</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="497" />
        <source>{app} {version}

A graphical front-end for Portage on Gentoo Linux.
Licensed under the GNU GPL, version 2 or (at your option) any later version.</source>
        <translation>{app} {version}

A graphical front-end for Portage on Gentoo Linux.
Licensed under the GNU GPL, version 2 or (at your option) any later version.</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="509" />
        <source>Log file</source>
        <translation>Log file</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="510" />
        <source>Messages are written to:
{path}</source>
        <translation>Messages are written to:
{path}</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="551" />
        <source>&amp;File</source>
        <translation>&amp;File</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="552" />
        <source>Settings…</source>
        <translation>Settings…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="553" />
        <source>Quit</source>
        <translation>Quit</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="555" />
        <source>&amp;Repositories</source>
        <translation>&amp;Repositories</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="556" />
        <source>Synchronise all repositories</source>
        <translation>Synchronise all repositories</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="557" />
        <source>Manage overlays</source>
        <translation>Manage overlays</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="559" />
        <source>&amp;Package</source>
        <translation>&amp;Package</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="560" />
        <source>Search…</source>
        <translation>Search…</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="621" />
        <location filename="../ui/main_window.py" line="561" />
        <source>Update @world</source>
        <translation>Update @world</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="563" />
        <source>&amp;System</source>
        <translation>&amp;System</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="564" />
        <source>Portage settings</source>
        <translation>Portage settings</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="565" />
        <source>Profile</source>
        <translation>Profile</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="566" />
        <source>Configuration files</source>
        <translation>Configuration files</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="567" />
        <source>elog messages</source>
        <translation>elog messages</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="569" />
        <source>&amp;View</source>
        <translation>&amp;View</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="570" />
        <source>Go to</source>
        <translation>Go to</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="574" />
        <source>Language</source>
        <translation>Language</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="576" />
        <source>System default</source>
        <translation>System default</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="580" />
        <source>Interface size</source>
        <translation>Interface size</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="600" />
        <location filename="../ui/main_window.py" line="581" />
        <source>Command log</source>
        <translation>Command log</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="583" />
        <source>&amp;Help</source>
        <translation>&amp;Help</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="585" />
        <source>Where is the log file?</source>
        <translation>Where is the log file?</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="620" />
        <source>Synchronise</source>
        <translation>Synchronise</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="622" />
        <source>Overlays</source>
        <translation>Overlays</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="623" />
        <source>Log</source>
        <translation>Log</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="628" />
        <source>never synchronised</source>
        <translation>never synchronised</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="629" />
        <source>sync: {when}</source>
        <translation>sync: {when}</translation>
    </message>
    <message>
        <location filename="../ui/main_window.py" line="635" />
        <source>@world: unknown</source>
        <translation>@world: unknown</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/main_window.py" line="636" />
        <source>@world: %n entry(s)</source>
        <translation>
            <numerusform>@world: %n entry</numerusform>
            <numerusform>@world: %n entries</numerusform>
        </translation>
    </message>
</context><context>
    <name>MakeConfPage</name>
    <message>
        <location filename="../ui/pages/makeconf.py" line="363" />
        <source>Changed one line in {path}:
{line}</source>
        <translation>Changed one line in {path}:
{line}</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="370" />
        <source>Cancelled — nothing was written.</source>
        <translation>Cancelled — nothing was written.</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="373" />
        <source>Nothing was written: {error}</source>
        <translation>Nothing was written: {error}</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="386" />
        <source>How many compiler jobs run at once.</source>
        <translation>How many compiler jobs run at once.</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="387" />
        <source>Options added to every emerge command.</source>
        <translation>Options added to every emerge command.</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="388" />
        <source>USE flags for the whole system, on top of what the profile sets.</source>
        <translation>USE flags for the whole system, on top of what the profile sets.</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="391" />
        <source>Which keywords count as installable. ~amd64 here puts the whole system on testing versions; a line per package is nearly always the better idea.</source>
        <translation>Which keywords count as installable. ~amd64 here puts the whole system on testing versions; a line per package is nearly always the better idea.</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="395" />
        <source>Which licences may be installed without asking.</source>
        <translation>Which licences may be installed without asking.</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="396" />
        <source>Which graphics drivers get built.</source>
        <translation>Which graphics drivers get built.</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="397" />
        <source>Instruction sets this processor has.</source>
        <translation>Instruction sets this processor has.</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="398" />
        <source>How Portage itself behaves while building.</source>
        <translation>How Portage itself behaves while building.</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="399" />
        <source>Which translations get installed.</source>
        <translation>Which translations get installed.</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="404" />
        <source>one job per core</source>
        <translation>one job per core</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="405" />
        <source>one job per core would need more memory than this machine has; roughly 2 GiB per job is the usual rule</source>
        <translation>one job per core would need more memory than this machine has; roughly 2 GiB per job is the usual rule</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="409" />
        <source>as cpuid2cpuflags reports it</source>
        <translation>as cpuid2cpuflags reports it</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="416" />
        <source>Changing a value here replaces one line and leaves the rest of the file exactly as it is — comments, ordering and all. The difference is shown before anything is written.</source>
        <translation>Changing a value here replaces one line and leaves the rest of the file exactly as it is — comments, ordering and all. The difference is shown before anything is written.</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="424" />
        <source>now</source>
        <translation>now</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="424" />
        <source>after this change</source>
        <translation>after this change</translation>
    </message>
</context><context>
    <name>MasksPage</name>
    <message>
        <location filename="../ui/pages/masks.py" line="307" />
        <source>No entries.</source>
        <translation>No entries.</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="346" />
        <source>Reading every ebuild's LICENSE…</source>
        <translation>Reading every ebuild's LICENSE…</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="353" />
        <source>Nothing here changes its licence with a flag.</source>
        <translation>Nothing here changes its licence with a flag.</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="376" />
        <source>Turning {flag} on also means accepting {licences}</source>
        <translation>Turning {flag} on also means accepting {licences}</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="379" />
        <source>Turning {flag} off also means accepting {licences}</source>
        <translation>Turning {flag} off also means accepting {licences}</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="416" />
        <source>Removed the line from {path}.</source>
        <translation>Removed the line from {path}.</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="423" />
        <source>Cancelled — nothing was written.</source>
        <translation>Cancelled — nothing was written.</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="426" />
        <source>Nothing was written: {error}</source>
        <translation>Nothing was written: {error}</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="439" />
        <source>Versions accepted despite not being marked stable for this architecture.</source>
        <translation>Versions accepted despite not being marked stable for this architecture.</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="442" />
        <source>Versions installed despite a developer having masked them.</source>
        <translation>Versions installed despite a developer having masked them.</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="443" />
        <source>Licences accepted for one package rather than system-wide.</source>
        <translation>Licences accepted for one package rather than system-wide.</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="444" />
        <source>Versions you have blocked yourself.</source>
        <translation>Versions you have blocked yourself.</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="455" />
        <source>Licences that depend on a USE flag</source>
        <translation>Licences that depend on a USE flag</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="457" />
        <source>Not a file — worked out. These packages carry a licence you have not accepted, hidden behind a flag that is currently off. Nothing is wrong with them today; turn the flag on and the install stops.</source>
        <translation>Not a file — worked out. These packages carry a licence you have not accepted, hidden behind a flag that is currently off. Nothing is wrong with them today; turn the flag on and the install stops.</translation>
    </message>
    <message>
        <location filename="../ui/pages/masks.py" line="470" />
        <source>empty</source>
        <translation>empty</translation>
    </message>
</context><context>
    <name>NewsEntry</name>
    <message>
        <location filename="../ui/widgets/news_list.py" line="92" />
        <source>Collapse</source>
        <translation>Collapse</translation>
    </message>
    <message>
        <location filename="../ui/widgets/news_list.py" line="92" />
        <source>Read</source>
        <translation>Read</translation>
    </message>
    <message>
        <location filename="../ui/widgets/news_list.py" line="96" />
        <source>unread</source>
        <translation>unread</translation>
    </message>
    <message>
        <location filename="../ui/widgets/news_list.py" line="100" />
        <source>concerns you because of: {reason}</source>
        <translation>concerns you because of: {reason}</translation>
    </message>
    <message>
        <location filename="../ui/widgets/news_list.py" line="105" />
        <source>posted to everyone</source>
        <translation>posted to everyone</translation>
    </message>
</context><context>
    <name>OfficialOnlyControl</name>
    <message>
        <location filename="../ui/widgets/official_toggle.py" line="110" />
        <source>off</source>
        <translation>off</translation>
    </message>
    <message>
        <location filename="../ui/widgets/official_toggle.py" line="111" />
        <source>hide in GUI</source>
        <translation>hide in GUI</translation>
    </message>
    <message>
        <location filename="../ui/widgets/official_toggle.py" line="111" />
        <source>mask in Portage</source>
        <translation>mask in Portage</translation>
    </message>
    <message>
        <location filename="../ui/widgets/official_toggle.py" line="114" />
        <source>Only ::gentoo</source>
        <translation>Only ::gentoo</translation>
    </message>
    <message>
        <location filename="../ui/widgets/official_toggle.py" line="115" />
        <source>a) hide in GUI</source>
        <translation>a) hide in GUI</translation>
    </message>
    <message>
        <location filename="../ui/widgets/official_toggle.py" line="116" />
        <source>b) mask in Portage</source>
        <translation>b) mask in Portage</translation>
    </message>
</context><context>
    <name>PackageDelegate</name>
    <message>
        <location filename="../ui/widgets/package_list.py" line="221" />
        <source>blocked</source>
        <translation>blocked</translation>
    </message>
    <message>
        <location filename="../ui/widgets/package_list.py" line="223" />
        <source>update available</source>
        <translation>update available</translation>
    </message>
    <message>
        <location filename="../ui/widgets/package_list.py" line="225" />
        <source>installed</source>
        <translation>installed</translation>
    </message>
</context><context>
    <name>Pages</name>
    <message>
        <location filename="../ui/pages/registry.py" line="67" />
        <source>Search &amp; install</source>
        <translation>Search &amp; install</translation>
    </message>
    <message>
        <location filename="../ui/pages/registry.py" line="68" />
        <source>System update</source>
        <translation>System update</translation>
    </message>
    <message>
        <location filename="../ui/pages/registry.py" line="69" />
        <source>Repositories</source>
        <translation>Repositories</translation>
    </message>
    <message>
        <location filename="../ui/pages/registry.py" line="70" />
        <source>Masks &amp; licences</source>
        <translation>Masks &amp; licences</translation>
    </message>
    <message>
        <location filename="../ui/pages/registry.py" line="71" />
        <source>Configuration files</source>
        <translation>Configuration files</translation>
    </message>
    <message>
        <location filename="../ui/pages/registry.py" line="72" />
        <source>make.conf</source>
        <translation>make.conf</translation>
    </message>
    <message>
        <location filename="../ui/pages/registry.py" line="73" />
        <source>elog messages</source>
        <translation>elog messages</translation>
    </message>
    <message>
        <location filename="../ui/pages/registry.py" line="74" />
        <source>@world set</source>
        <translation>@world set</translation>
    </message>
    <message>
        <location filename="../ui/pages/registry.py" line="75" />
        <source>Profile</source>
        <translation>Profile</translation>
    </message>
</context><context>
    <name>PlaceholderPage</name>
    <message>
        <location filename="../ui/pages/placeholder.py" line="68" />
        <source>This screen is built in session {session}.</source>
        <translation>This screen is built in session {session}.</translation>
    </message>
</context><context>
    <name>ProfilePage</name>
    <message>
        <location filename="../ui/pages/profile.py" line="210" />
        <source>Change the profile</source>
        <translation>Change the profile</translation>
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
        <translation>Switch from
  {old}
to
  {new}?

This changes the default USE flags, which packages are masked and what counts as part of the system. Afterwards the machine has to be rebuilt to match:

  emerge --ask --verbose --update --deep --newuse @world

That is a long build, and it is not optional. This will run:

  eselect profile set {index}</translation>
    </message>
    <message>
        <location filename="../ui/pages/profile.py" line="241" />
        <source>reading the profile list…</source>
        <translation>reading the profile list…</translation>
    </message>
    <message>
        <location filename="../ui/pages/profile.py" line="244" />
        <source>The profile is the closest thing Gentoo has to a choice of distribution. It sets the default USE flags, masks packages and decides what belongs to the system set. Changing it is not a setting — it is a decision followed by a full rebuild of everything installed.</source>
        <translation>The profile is the closest thing Gentoo has to a choice of distribution. It sets the default USE flags, masks packages and decides what belongs to the system set. Changing it is not a setting — it is a decision followed by a full rebuild of everything installed.</translation>
    </message>
    <message>
        <location filename="../ui/pages/profile.py" line="251" />
        <source>filter, e.g. plasma or hardened</source>
        <translation>filter, e.g. plasma or hardened</translation>
    </message>
    <message>
        <location filename="../ui/pages/profile.py" line="252" />
        <source>Refresh</source>
        <translation>Refresh</translation>
    </message>
</context><context>
    <name>ReposPage</name>
    <message numerus="yes">
        <location filename="../ui/pages/repos.py" line="404" />
        <source>Type a name or a keyword to search %n repositories.</source>
        <translation>
            <numerusform>Type a name or a keyword to search %n repository.</numerusform>
            <numerusform>Type a name or a keyword to search %n repositories.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="407" />
        <source>No catalogue yet. Press Refresh to fetch Gentoo's list of repositories.</source>
        <translation>No catalogue yet. Press Refresh to fetch Gentoo's list of repositories.</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="446" />
        <source>This will run:

eselect repository enable {name}
emaint sync -r {name}

Source: {uri}</source>
        <translation>This will run:

eselect repository enable {name}
emaint sync -r {name}

Source: {uri}</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="451" />
        <source>This repository is not run by Gentoo. Its ebuilds will run as root while building packages.</source>
        <translation>This repository is not run by Gentoo. Its ebuilds will run as root while building packages.</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="455" />
        <source>Enable repository</source>
        <translation>Enable repository</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="492" />
        <location filename="../ui/pages/repos.py" line="472" />
        <source>Remove repository</source>
        <translation>Remove repository</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="473" />
        <source>The main repository cannot be removed.</source>
        <translation>The main repository cannot be removed.</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="478" />
        <source>This will run:

eselect repository remove -f {name}</source>
        <translation>This will run:

eselect repository remove -f {name}</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/repos.py" line="482" />
        <source>%n installed package(s) came from this repository. They stay on the system but lose their ebuild, so nothing will update or rebuild them again:</source>
        <translation>
            <numerusform>%n installed package came from this repository. It stays on the system but loses its ebuild, so nothing will update or rebuild it again:</numerusform>
            <numerusform>%n installed packages came from this repository. They stay on the system but lose their ebuild, so nothing will update or rebuild them again:</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="516" />
        <source>Hide repository from Portage</source>
        <translation>Hide repository from Portage</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/repos.py" line="517" />
        <source>%n installed package(s) came from ::{name}. Masking it means Portage stops offering updates for them — they are not removed, and nothing else changes.</source>
        <translation>
            <numerusform>%n installed package came from ::{name}. Masking it means Portage stops offering updates for it — it is not removed, and nothing else changes.</numerusform>
            <numerusform>%n installed packages came from ::{name}. Masking it means Portage stops offering updates for them — they are not removed, and nothing else changes.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="554" />
        <source>Written to {path}.</source>
        <translation>Written to {path}.</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="560" />
        <source>Cancelled — nothing was written.</source>
        <translation>Cancelled — nothing was written.</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="563" />
        <source>Nothing was written: {error}</source>
        <translation>Nothing was written: {error}</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="603" />
        <source>Defined by the profile, not by repos.conf.</source>
        <translation>Defined by the profile, not by repos.conf.</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="611" />
        <source>Show in Portage again</source>
        <translation>Show in Portage again</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="611" />
        <source>Hide from Portage</source>
        <translation>Hide from Portage</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="618" />
        <source>Configured</source>
        <translation>Configured</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="619" />
        <source>Synchronise all</source>
        <translation>Synchronise all</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="621" />
        <source>All repositories</source>
        <translation>All repositories</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="622" />
        <source>name or keyword, e.g. steam</source>
        <translation>name or keyword, e.g. steam</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="623" />
        <source>Refresh</source>
        <translation>Refresh</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="625" />
        <source>Add by hand…</source>
        <translation>Add by hand…</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="626" />
        <source>Synchronise</source>
        <translation>Synchronise</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="627" />
        <source>Remove…</source>
        <translation>Remove…</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/repos.py" line="629" />
        <source>%n known</source>
        <translation>
            <numerusform>%n known</numerusform>
            <numerusform>%n known</numerusform>
        </translation>
    </message>
</context><context>
    <name>RequiredChanges</name>
    <message>
        <location filename="../ui/widgets/required_changes.py" line="182" />
        <source>Nothing is wrong with the package you asked for. Something it needs is built without a feature it requires, and Portage will not guess whether rebuilding it is acceptable to you. Each line below turns one feature on for one package.</source>
        <translation>Nothing is wrong with the package you asked for. Something it needs is built without a feature it requires, and Portage will not guess whether rebuilding it is acceptable to you. Each line below turns one feature on for one package.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/required_changes.py" line="188" />
        <source>Portage stopped before building anything because it needs these lines in your configuration first. Each one is shown with the package that asked for it.</source>
        <translation>Portage stopped before building anything because it needs these lines in your configuration first. Each one is shown with the package that asked for it.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/required_changes.py" line="206" />
        <source>Asked for by {package}</source>
        <translation>Asked for by {package}</translation>
    </message>
    <message>
        <location filename="../ui/widgets/required_changes.py" line="235" />
        <source>Add this line…</source>
        <translation>Add this line…</translation>
    </message>
    <message>
        <location filename="../ui/widgets/required_changes.py" line="251" />
        <source>Emerge needs a change first</source>
        <translation>Emerge needs a change first</translation>
    </message>
</context><context>
    <name>RestoreDialog</name>
    <message>
        <location filename="../ui/widgets/restore_dialog.py" line="160" />
        <source>Restore /etc/portage</source>
        <translation>Restore /etc/portage</translation>
    </message>
    <message>
        <location filename="../ui/widgets/restore_dialog.py" line="162" />
        <source>Restoring replaces {path} with the copy you pick. The state you have now is backed up first, so this can itself be undone.</source>
        <translation>Restoring replaces {path} with the copy you pick. The state you have now is backed up first, so this can itself be undone.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/restore_dialog.py" line="167" />
        <source>Backups</source>
        <translation>Backups</translation>
    </message>
    <message>
        <location filename="../ui/widgets/restore_dialog.py" line="168" />
        <source>What would change</source>
        <translation>What would change</translation>
    </message>
    <message>
        <location filename="../ui/widgets/restore_dialog.py" line="169" />
        <source>now</source>
        <translation>now</translation>
    </message>
    <message>
        <location filename="../ui/widgets/restore_dialog.py" line="169" />
        <source>the backup</source>
        <translation>the backup</translation>
    </message>
    <message>
        <location filename="../ui/widgets/restore_dialog.py" line="172" />
        <source>There are no backups yet.</source>
        <translation>There are no backups yet.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/restore_dialog.py" line="175" />
        <source>This backup matches what you have now — nothing would change.</source>
        <translation>This backup matches what you have now — nothing would change.</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/widgets/restore_dialog.py" line="184" />
        <source>%n file(s) restored</source>
        <translation>
            <numerusform>%n file restored</numerusform>
            <numerusform>%n files restored</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/widgets/restore_dialog.py" line="185" />
        <source>%n deleted</source>
        <translation>
            <numerusform>%n deleted</numerusform>
            <numerusform>%n deleted</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/widgets/restore_dialog.py" line="186" />
        <source>%n replaced</source>
        <translation>
            <numerusform>%n replaced</numerusform>
            <numerusform>%n replaced</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/widgets/restore_dialog.py" line="193" />
        <source>Restore</source>
        <translation>Restore</translation>
    </message>
    <message>
        <location filename="../ui/widgets/restore_dialog.py" line="198" />
        <source>Cancel</source>
        <translation>Cancel</translation>
    </message>
</context><context>
    <name>SearchPage</name>
    <message>
        <location filename="../ui/pages/search.py" line="385" />
        <source>unavailable</source>
        <translation>unavailable</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="387" />
        <source>Portage could not be read: {error}</source>
        <translation>Portage could not be read: {error}</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="990" />
        <location filename="../ui/pages/search.py" line="402" />
        <source>all</source>
        <translation>all</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="567" />
        <source>installed: {versions}</source>
        <translation>installed: {versions}</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="570" />
        <source>not installed</source>
        <translation>not installed</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="572" />
        <source>no description</source>
        <translation>no description</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="592" />
        <source>download: {size}</source>
        <translation>download: {size}</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="627" />
        <source>installed</source>
        <translation>installed</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="629" />
        <source>live</source>
        <translation>live</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="631" />
        <source>blocked</source>
        <translation>blocked</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="633" />
        <source>unchecked</source>
        <translation>unchecked</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="635" />
        <source>testing</source>
        <translation>testing</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="637" />
        <source>stable</source>
        <translation>stable</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="658" />
        <source>Pretend</source>
        <translation>Pretend</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="660" />
        <source>Uninstall</source>
        <translation>Uninstall</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="715" />
        <location filename="../ui/pages/search.py" line="660" />
        <source>Add to @world</source>
        <translation>Add to @world</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="662" />
        <source>Update</source>
        <translation>Update</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="662" />
        <source>Install</source>
        <translation>Install</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="705" />
        <source>Update package</source>
        <translation>Update package</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="705" />
        <source>Install package</source>
        <translation>Install package</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="730" />
        <source>Uninstall package</source>
        <translation>Uninstall package</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="731" />
        <source>The log above lists what would be removed.

Remove {package} now?

{command}</source>
        <translation>The log above lists what would be removed.

Remove {package} now?

{command}</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="745" />
        <source>This will run:

{command}</source>
        <translation>This will run:

{command}</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="871" />
        <source>Cancelled — nothing was written.</source>
        <translation>Cancelled — nothing was written.</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="874" />
        <source>Nothing was written: {error}</source>
        <translation>Nothing was written: {error}</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="884" />
        <source>No change was needed: {detail}</source>
        <translation>No change was needed: {detail}</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="888" />
        <source>Removed the line from {path}.</source>
        <translation>Removed the line from {path}.</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="890" />
        <source>Replaced one line in {path} with:
{line}</source>
        <translation>Replaced one line in {path} with:
{line}</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="893" />
        <source>Added to {path}:
{line}</source>
        <translation>Added to {path}:
{line}</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="953" />
        <source>loading…</source>
        <translation>loading…</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/search.py" line="955" />
        <source>%n package(s)</source>
        <translation>
            <numerusform>%n package</numerusform>
            <numerusform>%n packages</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/search.py" line="957" />
        <source>%n result(s)</source>
        <translation>
            <numerusform>%n result</numerusform>
            <numerusform>%n results</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/search.py" line="961" />
        <source>%n package(s) outside ::gentoo hidden. Overlays keep syncing.</source>
        <translation>
            <numerusform>%n package outside ::gentoo hidden. Overlays keep syncing.</numerusform>
            <numerusform>%n packages outside ::gentoo hidden. Overlays keep syncing.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="970" />
        <source>Nothing matches the query.</source>
        <translation>Nothing matches the query.</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="996" />
        <location filename="../ui/pages/search.py" line="972" />
        <source>Type a name, a category or a word from the description.</source>
        <translation>Type a name, a category or a word from the description.</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="978" />
        <source>name, category or description</source>
        <translation>name, category or description</translation>
    </message>
    <message>
        <location filename="../ui/pages/search.py" line="986" />
        <source>VERSION</source>
        <translation>VERSION</translation>
    </message>
</context><context>
    <name>SettingsDialog</name>
    <message>
        <location filename="../ui/settings_dialog.py" line="159" />
        <source>sudo needs a terminal or SUDO_ASKPASS to ask for the password; without one, privileged operations will not run.</source>
        <translation>sudo needs a terminal or SUDO_ASKPASS to ask for the password; without one, privileged operations will not run.</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="164" />
        <source>pkexec asks in a window and names what it is being asked for.</source>
        <translation>pkexec asks in a window and names what it is being asked for.</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="165" />
        <source>pkexec when it is available, sudo otherwise.</source>
        <translation>pkexec when it is available, sudo otherwise.</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="169" />
        <source>Everything is compiled from source, which is the Gentoo default.</source>
        <translation>Everything is compiled from source, which is the Gentoo default.</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="170" />
        <source>none configured</source>
        <translation>none configured</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="171" />
        <source>A prebuilt package is used only when its USE flags and dependencies match this system exactly, so nothing about *what* gets installed changes — only how it arrives. Binary hosts: {hosts}.</source>
        <translation>A prebuilt package is used only when its USE flags and dependencies match this system exactly, so nothing about *what* gets installed changes — only how it arrives. Binary hosts: {hosts}.</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="178" />
        <source>Settings</source>
        <translation>Settings</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="179" />
        <source>Language</source>
        <translation>Language</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="180" />
        <source>System default</source>
        <translation>System default</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="184" />
        <source>Interface size</source>
        <translation>Interface size</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="185" />
        <source>Becoming root</source>
        <translation>Becoming root</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="186" />
        <source>automatic</source>
        <translation>automatic</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="190" />
        <source>Use binary packages</source>
        <translation>Use binary packages</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="191" />
        <source>pass --getbinpkg when installing</source>
        <translation>pass --getbinpkg when installing</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="193" />
        <source>Backup form</source>
        <translation>Backup form</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="194" />
        <source>a directory in /etc</source>
        <translation>a directory in /etc</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="195" />
        <source>one .tar.gz archive</source>
        <translation>one .tar.gz archive</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="196" />
        <source>Backups kept</source>
        <translation>Backups kept</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="202" />
        <source>Save</source>
        <translation>Save</translation>
    </message>
    <message>
        <location filename="../ui/settings_dialog.py" line="206" />
        <source>Cancel</source>
        <translation>Cancel</translation>
    </message>
</context><context>
    <name>Sidebar</name>
    <message>
        <location filename="../ui/widgets/sidebar.py" line="144" />
        <source>Management</source>
        <translation>Management</translation>
    </message>
    <message>
        <location filename="../ui/widgets/sidebar.py" line="145" />
        <source>Backup</source>
        <translation>Backup</translation>
    </message>
    <message>
        <location filename="../ui/widgets/sidebar.py" line="146" />
        <source>none yet</source>
        <translation>none yet</translation>
    </message>
    <message>
        <location filename="../ui/widgets/sidebar.py" line="147" />
        <source>Restore…</source>
        <translation>Restore…</translation>
    </message>
</context><context>
    <name>UpdatePage</name>
    <message>
        <location filename="../ui/pages/update.py" line="533" />
        <source>Update the system</source>
        <translation>Update the system</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="534" />
        <source>Nothing has been previewed yet. Run step 3 first to see what would change.

Run the update anyway?</source>
        <translation>Nothing has been previewed yet. Run step 3 first to see what would change.

Run the update anyway?</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="556" />
        <source>Remove unused packages</source>
        <translation>Remove unused packages</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/update.py" line="557" />
        <source>%n package(s) are no longer needed by anything installed:</source>
        <translation>
            <numerusform>%n package is no longer needed by anything installed:</numerusform>
            <numerusform>%n packages are no longer needed by anything installed:</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="562" />
        <source>Remove them?</source>
        <translation>Remove them?</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="606" />
        <source>last synchronised {when}</source>
        <translation>last synchronised {when}</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="615" />
        <source>Synchronise repositories</source>
        <translation>Synchronise repositories</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="616" />
        <source>Read the news</source>
        <translation>Read the news</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="617" />
        <source>See what would change</source>
        <translation>See what would change</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="618" />
        <source>Update @world</source>
        <translation>Update @world</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="619" />
        <source>Remove what is no longer needed</source>
        <translation>Remove what is no longer needed</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="620" />
        <source>Configuration files</source>
        <translation>Configuration files</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="621" />
        <source>Security advisories</source>
        <translation>Security advisories</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="626" />
        <source>Fetches the current state of every configured repository. Nothing is installed or changed — after this, Portage simply knows what exists.</source>
        <translation>Fetches the current state of every configured repository. Nothing is installed or changed — after this, Portage simply knows what exists.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="630" />
        <source>Repositories ship notes when an update needs a hand. Only the ones that concern this system are listed, and each says why it does.</source>
        <translation>Repositories ship notes when an update needs a hand. Only the ones that concern this system are listed, and each says why it does.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="634" />
        <source>Asks Portage what it would do, without doing any of it. The table below is the same list emerge prints, sorted into columns.</source>
        <translation>Asks Portage what it would do, without doing any of it. The table below is the same list emerge prints, sorted into columns.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="638" />
        <source>Builds and installs everything from the preview. The log at the bottom of the window shows the output as it happens and can stop it at any point — the same interrupt Ctrl+C sends, so Portage can tidy up.</source>
        <translation>Builds and installs everything from the preview. The log at the bottom of the window shows the output as it happens and can stop it at any point — the same interrupt Ctrl+C sends, so Portage can tidy up.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="643" />
        <source>Finds packages nothing depends on any more. The list is always shown before anything is removed. Afterwards, @preserved-rebuild rebuilds whatever was still using a library that has just gone.</source>
        <translation>Finds packages nothing depends on any more. The list is always shown before anything is removed. Afterwards, @preserved-rebuild rebuilds whatever was still using a library that has just gone.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="648" />
        <source>Updates leave new versions of configuration files beside the old ones rather than overwriting them. Deciding between the two is the last step.</source>
        <translation>Updates leave new versions of configuration files beside the old ones rather than overwriting them. Deciding between the two is the last step.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="652" />
        <source>Compares what is installed against Gentoo's security advisories.</source>
        <translation>Compares what is installed against Gentoo's security advisories.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="659" />
        <source>Two packages block each other. Usually one of them has to be removed first, or a newer version accepted.</source>
        <translation>Two packages block each other. Usually one of them has to be removed first, or a newer version accepted.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="663" />
        <source>Two versions of the same package are wanted in one slot. Something asked for a specific version — the lines above say which.</source>
        <translation>Two versions of the same package are wanted in one slot. Something asked for a specific version — the lines above say which.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="667" />
        <source>A USE flag has to change first. The Search screen can write it, with the line shown before it is saved.</source>
        <translation>A USE flag has to change first. The Search screen can write it, with the line shown before it is saved.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="671" />
        <source>A version has to be accepted first. Open it on the Search screen: the block frame there writes the keyword line.</source>
        <translation>A version has to be accepted first. Open it on the Search screen: the block frame there writes the keyword line.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="675" />
        <source>A masked version is needed. Read why it was masked first.</source>
        <translation>A masked version is needed. Read why it was masked first.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="676" />
        <source>A licence has to be accepted first. The Search screen shows its full text.</source>
        <translation>A licence has to be accepted first. The Search screen shows its full text.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="679" />
        <source>The USE flags asked for are not a combination the package allows.</source>
        <translation>The USE flags asked for are not a combination the package allows.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="682" />
        <source>Something depends on a package no repository provides. An overlay may be missing.</source>
        <translation>Something depends on a package no repository provides. An overlay may be missing.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="686" />
        <source>The disk filled up.</source>
        <translation>The disk filled up.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="690" />
        <source>Failed: {package}</source>
        <translation>Failed: {package}</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="694" />
        <source>Full log: {path}</source>
        <translation>Full log: {path}</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="705" />
        <source>Everything is up to date.</source>
        <translation>Everything is up to date.</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/update.py" line="706" />
        <source>%n package(s)</source>
        <translation>
            <numerusform>%n package</numerusform>
            <numerusform>%n packages</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/update.py" line="716" />
        <source>%n to update</source>
        <translation>
            <numerusform>%n to update</numerusform>
            <numerusform>%n to update</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/update.py" line="719" />
        <source>%n new</source>
        <translation>
            <numerusform>%n new</numerusform>
            <numerusform>%n new</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/update.py" line="722" />
        <source>%n to rebuild</source>
        <translation>
            <numerusform>%n to rebuild</numerusform>
            <numerusform>%n to rebuild</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/update.py" line="725" />
        <source>%n to downgrade</source>
        <translation>
            <numerusform>%n to downgrade</numerusform>
            <numerusform>%n to downgrade</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/update.py" line="727" />
        <source>%n binary</source>
        <translation>
            <numerusform>%n binary</numerusform>
            <numerusform>%n binary</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="729" />
        <source>download {size}</source>
        <translation>download {size}</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="740" />
        <source>Nothing to remove.</source>
        <translation>Nothing to remove.</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/update.py" line="741" />
        <source>%n package(s) could be removed.</source>
        <translation>
            <numerusform>%n package could be removed.</numerusform>
            <numerusform>%n packages could be removed.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="745" />
        <source>glsa-check is not installed. Install {package} to enable this check.</source>
        <translation>glsa-check is not installed. Install {package} to enable this check.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="752" />
        <source>This system is not affected by any known advisory.</source>
        <translation>This system is not affected by any known advisory.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="759" />
        <source>Update</source>
        <translation>Update</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="761" />
        <source>Six steps. Each one runs on its own, in any order, as often as you like.</source>
        <translation>Six steps. Each one runs on its own, in any order, as often as you like.</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="770" />
        <source>Synchronise</source>
        <translation>Synchronise</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="772" />
        <source>Mark all as read</source>
        <translation>Mark all as read</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="774" />
        <source>Nothing unread</source>
        <translation>Nothing unread</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="777" />
        <source>Calculate</source>
        <translation>Calculate</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="781" />
        <source>Package</source>
        <translation>Package</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="782" />
        <source>Version</source>
        <translation>Version</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="783" />
        <source>USE changes</source>
        <translation>USE changes</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="784" />
        <source>Download</source>
        <translation>Download</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="785" />
        <source>binary</source>
        <translation>binary</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="788" />
        <source>Update now</source>
        <translation>Update now</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="795" />
        <location filename="../ui/pages/update.py" line="789" />
        <source>Check</source>
        <translation>Check</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="791" />
        <source>Remove them…</source>
        <translation>Remove them…</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="792" />
        <source>Rebuild what needs it</source>
        <translation>Rebuild what needs it</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="794" />
        <source>Go to configuration files</source>
        <translation>Go to configuration files</translation>
    </message>
    <message>
        <location filename="../ui/pages/update.py" line="798" />
        <source>Apply the fixes…</source>
        <translation>Apply the fixes…</translation>
    </message>
</context><context>
    <name>UseFlagRow</name>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="169" />
        <source>Collapse</source>
        <translation>Collapse</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="169" />
        <source>What does this change?</source>
        <translation>What does this change?</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="174" />
        <source>ebuild default</source>
        <translation>ebuild default</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="175" />
        <source>profile</source>
        <translation>profile</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="176" />
        <source>make.conf</source>
        <translation>make.conf</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="177" />
        <source>per package</source>
        <translation>per package</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="178" />
        <source>environment</source>
        <translation>environment</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="179" />
        <source>off by default</source>
        <translation>off by default</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="185" />
        <source>locked on by the profile</source>
        <translation>locked on by the profile</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="187" />
        <source>locked on for this package</source>
        <translation>locked on for this package</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="191" />
        <source>masked by the profile</source>
        <translation>masked by the profile</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="193" />
        <source>masked for this package</source>
        <translation>masked for this package</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="196" />
        <source>changed by you</source>
        <translation>changed by you</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="198" />
        <source>named in REQUIRED_USE</source>
        <translation>named in REQUIRED_USE</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/widgets/use_flag_row.py" line="205" />
        <source>and %n more</source>
        <translation>
            <numerusform>and one more</numerusform>
            <numerusform>and %n more</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="214" />
        <source>With {flag} on, this also installs: {atoms}</source>
        <translation>With {flag} on, this also installs: {atoms}</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="220" />
        <source>{flag} adds no extra packages — it only changes how this one is built.</source>
        <translation>{flag} adds no extra packages — it only changes how this one is built.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="227" />
        <source>With {flag} off, it installs instead: {atoms}</source>
        <translation>With {flag} off, it installs instead: {atoms}</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="235" />
        <source>These have to carry the same setting, so changing it may rebuild them: {atoms}</source>
        <translation>These have to carry the same setting, so changing it may rebuild them: {atoms}</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="244" />
        <source>description from metadata.xml</source>
        <translation>description from metadata.xml</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="245" />
        <source>description from use.local.desc</source>
        <translation>description from use.local.desc</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="246" />
        <source>description from use.desc</source>
        <translation>description from use.desc</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="247" />
        <source>description from profiles/desc</source>
        <translation>description from profiles/desc</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="248" />
        <source>no description in the repository</source>
        <translation>no description in the repository</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flag_row.py" line="262" />
        <source>No description available.</source>
        <translation>No description available.</translation>
    </message>
</context><context>
    <name>UseFlagsPanel</name>
    <message>
        <location filename="../ui/widgets/use_flags_panel.py" line="247" />
        <source>REQUIRED_USE is not satisfied. Portage would refuse this combination, so there is nothing worth writing yet.</source>
        <translation>REQUIRED_USE is not satisfied. Portage would refuse this combination, so there is nothing worth writing yet.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flags_panel.py" line="284" />
        <source>does not apply</source>
        <translation>does not apply</translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flags_panel.py" line="285" />
        <source>not satisfied</source>
        <translation>not satisfied</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/widgets/use_flags_panel.py" line="295" />
        <source>%n flag(s) on</source>
        <translation>
            <numerusform>%n flag on</numerusform>
            <numerusform>%n flags on</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/widgets/use_flags_panel.py" line="297" />
        <source>%n changed</source>
        <translation>
            <numerusform>%n changed</numerusform>
            <numerusform>%n changed</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/widgets/use_flags_panel.py" line="307" />
        <source>USE flags</source>
        <translation>USE flags</translation>
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
        <translation>Take out of @world</translation>
    </message>
    <message>
        <location filename="../ui/pages/world.py" line="293" />
        <source>Remove {atom} from @world?

This does not uninstall anything. It only stops the package being one you asked for, so the next --depclean will remove it if nothing else needs it.

This will run:

  emerge --deselect {atom}</source>
        <translation>Remove {atom} from @world?

This does not uninstall anything. It only stops the package being one you asked for, so the next --depclean will remove it if nothing else needs it.

This will run:

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
        <translation>The packages you asked for. Everything else installed is here because one of these needs it.</translation>
    </message>
    <message>
        <location filename="../ui/pages/world.py" line="315" />
        <source>Installed</source>
        <translation>Installed</translation>
    </message>
    <message>
        <location filename="../ui/pages/world.py" line="316" />
        <source>filter by name</source>
        <translation>filter by name</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/world.py" line="321" />
        <source>%n package(s)</source>
        <translation>
            <numerusform>%n package</numerusform>
            <numerusform>%n packages</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/world.py" line="323" />
        <source>showing the first %n</source>
        <translation>
            <numerusform>showing the first %n</numerusform>
            <numerusform>showing the first %n</numerusform>
        </translation>
    </message>
</context><context>
    <name>WritePreview</name>
    <message>
        <location filename="../ui/widgets/write_preview.py" line="173" />
        <source>{file} is a directory, so the entry goes in a file of its own.</source>
        <translation>{file} is a directory, so the entry goes in a file of its own.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/write_preview.py" line="176" />
        <source>This file already has an entry for it.</source>
        <translation>This file already has an entry for it.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/write_preview.py" line="177" />
        <source>{file} is a single file; the line is added at the end.</source>
        <translation>{file} is a single file; the line is added at the end.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/write_preview.py" line="180" />
        <source>Neither {file} nor a directory of that name exists yet. Gentoo recommends the directory form, so that is what will be created.</source>
        <translation>Neither {file} nor a directory of that name exists yet. Gentoo recommends the directory form, so that is what will be created.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/write_preview.py" line="188" />
        <source>One line is replaced:
− {old}
+ {new}</source>
        <translation>One line is replaced:
− {old}
+ {new}</translation>
    </message>
    <message>
        <location filename="../ui/widgets/write_preview.py" line="192" />
        <source>One line is removed:
− {old}</source>
        <translation>One line is removed:
− {old}</translation>
    </message>
    <message>
        <location filename="../ui/widgets/write_preview.py" line="193" />
        <source>One line is added. Everything else in the file is left alone.</source>
        <translation>One line is added. Everything else in the file is left alone.</translation>
    </message>
    <message>
        <location filename="../ui/widgets/write_preview.py" line="196" />
        <source>Will be written</source>
        <translation>Will be written</translation>
    </message>
    <message>
        <location filename="../ui/widgets/write_preview.py" line="197" />
        <source>preview before saving</source>
        <translation>preview before saving</translation>
    </message>
    <message>
        <location filename="../ui/widgets/write_preview.py" line="198" />
        <source>Discard changes</source>
        <translation>Discard changes</translation>
    </message>
    <message>
        <location filename="../ui/widgets/write_preview.py" line="199" />
        <source>Saving…</source>
        <translation>Saving…</translation>
    </message>
    <message>
        <location filename="../ui/widgets/write_preview.py" line="199" />
        <source>Save</source>
        <translation>Save</translation>
    </message>
</context><context>
    <name>_CatalogueRow</name>
    <message>
        <location filename="../ui/pages/repos.py" line="188" />
        <source>official</source>
        <translation>official</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="188" />
        <source>unofficial</source>
        <translation>unofficial</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="191" />
        <source>already configured</source>
        <translation>already configured</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="191" />
        <source>Enable</source>
        <translation>Enable</translation>
    </message>
</context><context>
    <name>_ConditionalRow</name>
    <message>
        <location filename="../ui/pages/masks.py" line="142" />
        <source>Open this package</source>
        <translation>Open this package</translation>
    </message>
</context><context>
    <name>_ConfiguredRow</name>
    <message>
        <location filename="../ui/pages/repos.py" line="124" />
        <source>main repository</source>
        <translation>main repository</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="124" />
        <source>overlay</source>
        <translation>overlay</translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="126" />
        <source>hidden from Portage</source>
        <translation>hidden from Portage</translation>
    </message>
    <message numerus="yes">
        <location filename="../ui/pages/repos.py" line="128" />
        <source>%n package(s)</source>
        <translation>
            <numerusform>%n package</numerusform>
            <numerusform>%n packages</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../ui/pages/repos.py" line="135" />
        <source>never synchronised</source>
        <translation>never synchronised</translation>
    </message>
</context><context>
    <name>_EntryRow</name>
    <message>
        <location filename="../ui/pages/masks.py" line="122" />
        <source>Remove…</source>
        <translation>Remove…</translation>
    </message>
</context><context>
    <name>_FileRow</name>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="111" />
        <source>new file</source>
        <translation>new file</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="115" />
        <source>from {package}</source>
        <translation>from {package}</translation>
    </message>
    <message>
        <location filename="../ui/pages/cfgfiles.py" line="117" />
        <source>no package claims this file</source>
        <translation>no package claims this file</translation>
    </message>
</context><context>
    <name>_ProfileRow</name>
    <message>
        <location filename="../ui/pages/profile.py" line="95" />
        <source>unmarked</source>
        <translation>unmarked</translation>
    </message>
    <message>
        <location filename="../ui/pages/profile.py" line="97" />
        <source>in use</source>
        <translation>in use</translation>
    </message>
    <message>
        <location filename="../ui/pages/profile.py" line="97" />
        <source>Use this one…</source>
        <translation>Use this one…</translation>
    </message>
</context><context>
    <name>_VariableRow</name>
    <message>
        <location filename="../ui/pages/makeconf.py" line="142" />
        <source>not set in make.conf</source>
        <translation>not set in make.conf</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="176" />
        <source>Portage uses: {value}</source>
        <translation>Portage uses: {value}</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="186" />
        <source>This assignment spans several lines; Gentstore will not rewrite it.</source>
        <translation>This assignment spans several lines; Gentstore will not rewrite it.</translation>
    </message>
    <message>
        <location filename="../ui/pages/makeconf.py" line="198" />
        <source>A suggestion needs {package}; it is not installed.</source>
        <translation>A suggestion needs {package}; it is not installed.</translation>
    </message>
</context><context>
    <name>_WorldRow</name>
    <message>
        <location filename="../ui/pages/world.py" line="115" />
        <source>not installed</source>
        <translation>not installed</translation>
    </message>
    <message>
        <location filename="../ui/pages/world.py" line="117" />
        <source>Take out of @world…</source>
        <translation>Take out of @world…</translation>
    </message>
</context></TS>
