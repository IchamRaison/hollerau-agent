"""Copie du transcript de la session Claude Code ouverte depuis /home/animus, à rattacher à Entire
depuis le worktree du pilote (la session ne tourne pas dans le dépôt : aucun hook ne la capture).
La copie est complète. Seules les valeurs de clés sont remplacées par « [clé retirée] » : les
valeurs des .env et tout motif de clé OpenAI ; deux lignes de mémoire personnelle sans rapport
avec le projet sont retirées. Contrôle avant d'écrire : plus aucune clé dans la copie.

python3 -I analysis/dsh/entire_trim_session.py
  ->  ~/.claude/projects/-home-animus-ehl-tacto-hollerau-dsh/<id de session>.jsonl
puis, depuis le worktree :  entire session attach <id de session> --force"""
import re
import sys
from pathlib import Path

HOME = Path.home()
SID = "422a02e0-ed78-4ce0-93eb-062721198ef6"
SRC = HOME / ".claude/projects/-home-animus" / f"{SID}.jsonl"
DST = HOME / ".claude/projects/-home-animus-ehl-tacto-hollerau-dsh" / f"{SID}.jsonl"
KEYLIKE = re.compile(r"(?<![A-Za-z])sk-[A-Za-z0-9_\-]{16,}")
PRIVATE = re.compile(r"- \[(RDX Agency contexte|Projet prof de piano IA)\]\([^)]*\)[^\\\n]*")
GONE = "[clé retirée]"

secrets = set()
for env in ("ehl-tacto/hollerau-agent/.env", "ehl-tacto/hollerau-dsh/.env"):
    try:
        for line in (HOME / env).read_text().splitlines():
            k, sep, v = line.partition("=")
            v = v.strip().strip("\"'")
            if sep and any(t in k for t in ("KEY", "TOKEN", "SECRET")) and len(v) >= 12:
                secrets.add(v)
    except OSError:
        pass

lines = SRC.read_text().splitlines()
kept, masked = [], 0
for line in lines:
    for s in secrets:
        masked += line.count(s)
        line = line.replace(s, GONE)
    line, n = KEYLIKE.subn(GONE, line)
    masked += n
    kept.append(PRIVATE.sub("- [note personnelle sans rapport, retirée]", line))
bad = [i for i, line in enumerate(kept) if any(s in line for s in secrets) or KEYLIKE.search(line)]
if bad:
    sys.exit(f"clé encore présente aux lignes {bad[:10]} : rien n'est écrit")
DST.parent.mkdir(parents=True, exist_ok=True)
DST.write_text("\n".join(kept) + "\n")
print(f"{len(kept)} lignes copiées (transcript complet), {masked} valeur(s) de clé masquée(s) -> {DST}")
