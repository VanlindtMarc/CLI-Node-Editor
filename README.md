# CLI Node Editor

Ce logiciel a pour but de générer automatiquement des fichiers **batch**, **bash** et **PowerShell** complexes faisant appel à plusieurs logiciels en ligne de commande afin d'automatiser un flux sur un ou plusieurs fichiers.

Le logiciel passe par une interface nodale.

Vous aurez donc : 

- À gauche : La liste de tous les noeuds
- Au centre : l'interface nodale
- À droite : une prévisualisation du code 

**Attention :** 
- Ce logiciel est toujours en cours de création et il peut planter lorsque l'on modifie des nœuds déjà en place. Pensez à sauvegarder votre flux couramment.
- Pour le moment, seul le **batch** est optimisé et testé.

![test](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI02.png)

## Types de flux pouvant être créés

Il est possible de créer trois sortes de flux : 

1. Chaque fichier est traité individuellement et le flux est répété pour chaque fichier
2. Tous les fichiers sont traités par un seul flux
3. Un certain nombre de fichiers est demandé, chacun d'un certain type, et chacun sera sélectionné par son extension pour la suite du flux.

Cela est configurable via l'interface et l'utilisation de certains nœuds.

## Nœuds d'entrée

Par défaut, l'interface vous présentera le nœud d'entrée **Fichier Input** et le nœud de sortie **Fichier Destination**, qui sont les bases d'un flux : une entrée -> une sortie.

Ce nœud d'entrée correspond aux cas 1 et 2 vus dans les types de flux.

Pour le cas 3, vous pouvez supprimer le nœud **Fichier Input** et faire appel au nœud **Multi Fichiers**.

Celui-ci vous permettra d'indiquer le nombre de fichiers devant être reçu en entrée et d'indiquer les différents types attendus. Par exemple, vidéo (avec plusieurs formats possibles) et sous-titres (idem).

## Noeud de sortie

Il n'y en a qu'un, qui peut être appelé plusieurs fois si plusieurs fichiers sont à créer.

On y indique simplement le nom et l'extension voulue.

## Variables

Vous pouvez faire appel à deux nœuds permettant d'assigner des variables à votre flux.

Dans chacun des cas, une fois une variable créée, vous pourrez y faire appel via ***{nom de la variable}***.

### Variables d'entrée

Ce nœud fera qu'une série de questions sera posée au début du flux pour être ré-utilisée par la suite.

### Variables globales 

Certains nœuds peuvent renvoyer une valeur sauvegardée sous forme de fichier TXT, par exemple la largeur d'une image, l'artiste d'un audio...

Le nœud **Variables globales** peut créer des variables basées sur ces fichiers TXT, pouvant alors être utilisées dans toute l'interface.

## Outils CLI

Vous allez pouvoir utiliser tous les outils CLI que vous voulez.

Ils seront sauvés dans une base de données contenant :

**Nom court à utiliser dans l'interface** - **Lien complet vers l'outil** - **Description**

### Nœuds CLI

Chaque nœud peut être paramétré via quatre onglets.

#### Général 
* Nom du nœud : nom réel
* Nom affiché : nom affiché dans les menus
* Catégorie : en général le nom de la commande CLI
* Sous-catégorie : le type d'usage fait de la commande
* Commande CLI : commande dans son nom court
* Format de sortie : format proposé par défaut
* Formats suggérés : autres formats dans lesquels il est possible de sauver le résultat
* Description
* Couleur hexa : couleur du nœud dans l'interface.

#### Ports
Indique le nombre de fichiers attendus en entrée et en sortie.

#### Paramètres

Permet de créer des variables locales qui seront utilisées lors de l'appel à la commande. 

#### Template

Commande à utiliser (dans son nom court indiqué dans la liste des outils), pouvant faire appel aux variables locales et globales.

### Nœuds vérifiés

Les nœuds vérifiés correspondent à des nœuds qui ont été testés.

La plupart des nœuds ont été générés par IA et demandent à être vérifiés.



## Idées 

* Ajouter plus de dépendances et dans l'interface des zones pour voir les urls de téléchargement
