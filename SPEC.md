# SPEC — LA TAUPE

## Problème (5 lignes)
Un utilisateur fournit une question et un corpus de documents. Certains documents contiennent des instructions cachées destinées à manipuler l'agent (injection de prompt indirecte). L'agent doit répondre correctement en n'utilisant que les documents légitimes, détecter et mettre en quarantaine les documents piégés, et produire un rapport d'audit traçant chaque tentative détectée avec l'extrait déclencheur.

## User Stories
1. **En tant qu'analyste**, je dépose un corpus mixte (documents sains + au moins un piégé) et je reçois une réponse fondée uniquement sur les documents sains, avec un rapport listant chaque document suspect, l'extrait incriminé et la technique détectée.
2. **En tant qu'analyste**, je consulte le panneau d'audit pour voir l'historique complet des détections : document, extrait, technique, confiance, horodatage, décision (quarantaine/accepté).
3. **En tant qu'analyste**, je soumets une question en langage naturel et j'obtiens une réponse citant ses sources (documents sains uniquement), sans que le contenu des documents en quarantaine n'ait influencé la génération.

## Hors Scope (v1 — Palier 1 uniquement)
- Aucun code, aucune implémentation, aucun appel LLM réel.
- Aucune base de données, aucun schéma de quarantaine persistant.
- Aucun frontend, aucune interface d'upload, aucun dashboard temps réel.
- Aucune détection d'injection fonctionnelle (regex, classifier, ou LLM-juge).
- Aucun pipeline RAG, aucune ingestion, aucun parsing de documents.
- Aucune journalisation structurée, aucun rapport de sécurité généré.
- Aucun test adversarial, aucune métrique de faux positifs/négatifs.
- Aucune gestion de clés API, aucun `.env`, aucune configuration déploiement.
- Aucune architecture multi-agents, aucune boucle de décision, aucun outil typé exécutable.
- Aucun traitement de formats (PDF, DOCX, TXT), aucune normalisation Unicode.