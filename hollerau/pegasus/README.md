# pegasus (couloir Vincent)

Agent acheteur complet, chiffres décidés par le code, texte par gabarits (un narrateur LLM optionnel existe, désactivé car moins bon en mesure).

## Lancer
- Pré-vol : `PEGASUS_READER=1 uv run python -m hollerau.pegasus.preflight`
- Répétition hors ligne du chemin finale : `uv run python -m hollerau.pegasus.dryrun_final` (arène factice, aucune session)
- Entraînement (verrou d'Icham obligatoire) : `HOLLERAU_VALIDATED="qui, quoi" PEGASUS_READER=1 uv run python -m hollerau.pegasus.cli practice P01 P02`
- Finale : `HOLLERAU_VALIDATED="qui, quoi" PEGASUS_READER=1 uv run python -m hollerau.pegasus.cli final --parallel 10`
Le lecteur LLM (`PEGASUS_READER=1`) utilise `LLM_BASE_URL`/`LLM_MODEL`/`LLM_API_KEY` (DeepSeek V4.1 Flash sur Nebius chez nous, 2-8 s par lecture) et retombe sur des mots-clés sans clé.

## Résultats (entraînement, agent général sans réglage par cas)
P01 0,998 (record 1,000) · P03 0,935 (0,936) · P04 0,860 (0,874) · P11 0,794 (0,807) · P05 0,734 · P02 0,684 · P10 0,679 · P07 0,676 · P08 0,659 · P18 0,575. Équipe 5e (75,9) au moment de cette PR.

## Ce qui est général (rien n'est codé par cas)
structures choisies au prix attendu de l'accord ; concessions en coût total ; arguments vérifiés par ID (un seul usage) ; lecture des réponses (clause d'indexation exigée, chargeback refusé, délai ferme, paiement rapide, gel des prix, « c'est notre limite ») ; mémoire par fournisseur ; clôture avant le cap avec notre coût (pénalité relationnelle comprise).

## Données
`analysis/pegasus_data/` : fiches des cas, 150+ parties terminées (trace + back office), c_best des 10 cas, playbook/leçons/profils de Codex, corpus étiqueté du lecteur (2 859 phrases), revues de rejeu.
