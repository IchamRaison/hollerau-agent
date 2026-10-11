# pegasus (couloir Vincent)

Agent acheteur complet, chiffres décidés par le code, texte par gabarits (un narrateur LLM optionnel existe, désactivé car moins bon en mesure).

## Lancer
- Pré-vol : `PEGASUS_READER=1 uv run python -m hollerau.pegasus.preflight`
- Répétition hors ligne du chemin finale : `uv run python -m hollerau.pegasus.dryrun_final` (arène factice, aucune session)
- Entraînement (verrou d'Icham obligatoire) : `HOLLERAU_VALIDATED="qui, quoi" PEGASUS_READER=1 uv run python -m hollerau.pegasus.cli practice P01 P02`
- Finale : `HOLLERAU_VALIDATED="qui, quoi" PEGASUS_READER=1 uv run python -m hollerau.pegasus.cli final --parallel 10`
Le lecteur LLM (`PEGASUS_READER=1`) utilise `LLM_BASE_URL`/`LLM_MODEL`/`LLM_API_KEY` (DeepSeek V4.1 Flash sur Nebius chez nous, 2-8 s par lecture) et retombe sur des mots-clés sans clé.

## Résultats (entraînement, agent général sans réglage par cas, 11/10 vers 01:45)
Meilleurs par cas : P01 0,998 · P03 0,935 · P04 0,860 · P11 0,840 · P05 0,824 · P02 0,735 · P07 0,715 · P10 0,702 · P08 0,673 · P18 0,575 — équipe 3e (0,791). Une partie par cas avec la version r35 : 77,1.

## Nouveau depuis la PR #8 (r14 → r35)
- Modèle relationnel calibré sur les pénalités réelles de l'arène : coût complet = should-cost / 1,02 ; coût de l'argent du fournisseur lu dans la correspondance (9,6 % s'il demande à être payé plus vite, 6,4 % sinon), affiné par ses propres paires prix/paiement.
- Cas relationnels : ouverture sur la structure au creux du U le plus bas (P01 : 14 j), ancre profonde bornée, paquets plafonnés au coût de son offre, accord sous le creux remonté au creux avant d'accepter (P02 : 352,95 = 0,33 → 361,21 = 0,735), sonde « sans clause » après un accord avec clause.
- Accord accepté tout de suite ; « prendre sa parole » (prix plus bas écrit en prose pour les mêmes termes, P05 28,00) ; miroir de toute alternative déjà proposée ; nudge d'un tick quand il tient son prix ; mémoire du tour où chaque fournisseur envoie son final et vrai pas juste avant.
- Pas de prix entre 1,2 % et 2,2 % par tour (un fournisseur) ; claim historique bas → récent en tête du premier message ; part d'affaires quand il ne fournit qu'une partie du besoin ; question sur le palier de remise ; réponse aux questions chiffrées avec la prévision et un CSV joint.
- Essayé et retiré (mesuré) : message après un final d'un fournisseur unique (il se retire : 4 cas à 0), claims « devis » (jugés hors sujet), claim qualité, pas plafonné par paquet, chargeback forcé à 0.

## Ce qui est général (rien n'est codé par cas)
structures choisies au prix attendu de l'accord ; concessions en coût total ; arguments vérifiés par ID (un seul usage) ; lecture des réponses (clause d'indexation exigée, chargeback refusé, délai ferme, paiement rapide, gel des prix, « c'est notre limite ») ; mémoire par fournisseur ; clôture avant le cap avec notre coût (pénalité relationnelle comprise).

## Données
`analysis/pegasus_data/` : fiches des cas, 150+ parties terminées (trace + back office), c_best des 10 cas, playbook/leçons/profils de Codex, corpus étiqueté du lecteur (2 859 phrases), revues de rejeu.
