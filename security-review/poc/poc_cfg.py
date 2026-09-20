"""PoC: cfg_apply never asks who may write the directory the ._cfg file is in.

The sandbox stands in for a real system: `etc` plays /etc (root-owned, 0755),
`etc/loose` plays any directory under a protected root that is not root's alone.
_only_root_can_write is reimplemented with the same rule, stopping at the
sandbox root instead of / and treating the user running the test as root —
so the check is as strict here as it is in production.
"""
import io
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "/home/janek/Dokumenty/githun/GentStore")
from gentstore.helper import gentstore_helper as helper

tmp = Path(tempfile.mkdtemp()).resolve()
etc = tmp / "etc"
(etc / "portage" / "repos.conf").mkdir(parents=True)
os.chmod(etc, 0o755)
helper.CONFIG_ROOT = etc / "portage"
helper.BACKUP_PARENT = etc
helper.CONFIG_PROTECT_SOURCES = ()
helper.ENV_D = tmp / "no-env-d"
helper.DEFAULT_PROTECTED = (str(etc),)

ME = os.getuid()
def only_root_can_write(path: Path) -> bool:
    p = Path(path)
    while True:
        info = p.stat()
        if info.st_uid != ME or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            return False
        if p == tmp:
            return True
        p = p.parent
helper._only_root_can_write = only_root_can_write
helper.os.geteuid = lambda: 0

loose = etc / "loose"           # e.g. a group-writable directory under /etc
loose.mkdir()
os.chmod(loose, 0o777)
victim = loose / "victim.conf"
victim.write_text("harmless\n", encoding="utf-8")
candidate = loose / "._cfg0000_victim.conf"   # planted by an unprivileged user
candidate.write_text("planted\n", encoding="utf-8")

print("is /etc a protected root?      ", [str(p) for p in helper.protected_roots()])
print("would the rule allow etc/loose?", only_root_can_write(loose))

stdin = io.StringIO(json.dumps({
    "op": "cfg_apply", "path": str(candidate), "decision": "merge",
    "content": "# content chosen by the caller, written as root\n",
}))
stdout = io.StringIO()
helper.main(stdin, stdout)
print("answer:", json.loads(stdout.getvalue())["ok"])
print("victim.conf now:", repr(victim.read_text()))
