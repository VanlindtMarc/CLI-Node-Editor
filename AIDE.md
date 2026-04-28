# Terminal Architect

Terminal Architect est un éditeur nodal pour construire des flux de traitement en ligne de commande.

## Principes

- Chaque noeud représente une étape.
- Les connexions définissent l'ordre et le passage des fichiers.
- Le panneau de droite montre le script généré.
- Le bouton `Lancer` exécute le flux depuis l'interface.

## Types de noeuds

- `Fichier Input` : entrée basée sur les fichiers fournis au lancement.
- `Fichier Source` : entrée fixe vers un fichier précis.
- `Fichier Destination` : copie ou dépose le résultat final.
- `Debug` : affiche ou enregistre des informations pendant le flux.
- `Switch`, `Merge`, `Variables Globales`, `Variables d'entrée` : noeuds système de contrôle.

## Débogage

- `Mode debug` ajoute des traces détaillées dans les scripts générés.
- `Pause avant chaque action` est utile pour un lancement manuel dans un terminal.
- Le noeud `Debug` permet de sonder le flux au milieu d'un workflow.

## Exécution depuis l'interface

- `Lancer` demande les fichiers d'entrée si le workflow en a besoin.
- Les noeuds sont mis en avant pendant l'exécution.
- Les logs apparaissent dans le panneau d'exécution.

## Bibliothèque

- Modifier un noeud dans la bibliothèque peut maintenant resynchroniser ses occurrences déjà présentes sur le canvas.

## Conseils

- Sauvegarder les workflows en `.workflow`.
- Utiliser `Cadrer tout le workflow` quand le graphe devient grand.
- Vérifier les dépendances CLI dans `Outils > Configurer les dépendances`.
