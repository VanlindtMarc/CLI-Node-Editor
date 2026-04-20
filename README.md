# CLI Node Editor

Ce logiciel a pour but de générer automatiquement des fichiers **batch**, **bash** et **PowerShell** complexes faisant appel à plusieurs logiciels en ligne de commande afin d'automatiser un flux sur un ou plusieurs fichiers.

Le logiciel passe par une interface nodale.

**Attention :** 
- Ce logiciel est toujours en cours de création et il peut planter lorsque l'on modifie des nœuds déjà en place. Pensez à sauvegarder votre flux couramment.
- Pour le moment, seul le **batch** est optimisé et testé : bien que le script final puisse être écrit en 3 langages, les nœuds, eux, sont écrits en batchs.

L'interface principe est divisée en trois : 
1. Une colonne à gauche où apparaissent tous les nœuds proposés
2. Une zone centrale montrant les nœuds et leurs liens
3. Une colonne à droite où peut être généré le code et visualiser le code à exporter.

![test](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI02.png?raw=true)

---

## Types de flux pouvant être créés

Il est possible de créer trois sortes de flux : 

1. Chaque fichier est traité individuellement et le flux est répété pour chaque fichier.
2. Tous les fichiers sont traités par un seul flux
3. Un certain nombre de fichiers est demandé, chacun d'un certain type, et chacun sera sélectionné par son extension pour la suite du flux.

Cela est configurable via l'interface et l'utilisation de certains nœuds.

---

## Nœuds d'entrée

![CLI03](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI03.png?raw=true)

Il existe trois nœuds d'entrée : 
1. **Fichier input** : ce nœud est celui par défaut et correspond au(x) fichier(s) que vous enverrez vers votre flux
2. **Fichier source** : indique un fichier fixe qui sera utilisé pendant le flux (par exemple un watermark pour des photos)
3. **Multi-fichiers** : indique le nombre et le type de fichier attendus pour ce flux.

Par défaut, l'interface vous présentera le nœud d'entrée **Fichier Input** et le nœud de sortie **Fichier Destination**, qui sont les bases d'un flux : une entrée → une sortie.

---

## Nœud de sortie

Il n'y en a qu'un, qui peut être appelé plusieurs fois si plusieurs fichiers sont à créer.

On y indique simplement le nom et l'extension voulue.

---

## Variables et opérations

Vous pouvez faire appel à deux nœuds permettant d'assigner des variables à votre flux.

Dans chacun des cas, une fois une variable créée, vous pourrez y faire appel via ***{nom de la variable}***.

### Opérations

Dans la catégorie **Batch**, vous pourrez trouver **Opération mathématique**, qui utilise le langage Batch pour réaliser les opérations. Ce langage est très limité puisqu'il ne fonctionne qu'avec des entiers. Si vous demandez 5 divisé en 2, cela vous donnera 3. Mais c'est parfait pour les résolutions.

Pour les calculs plus complexes, je vous conseille l'outil **Qalculate**.

### Variables d'entrée

Ce nœud fera qu'une série de questions sera posée au début du flux pour être ré-utilisée par la suite.

### Variables globales 

Certains nœuds peuvent renvoyer une valeur sauvegardée sous forme de fichier TXT, par exemple la largeur d'une image, l'artiste d'un audio...

Le nœud **Variables globales** peut créer des variables basées sur ces fichiers TXT, pouvant alors être utilisées dans toute l'interface.

---

## Outils CLI

![CLI11](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI11.png?raw=true)

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

---

## Nœuds vérifiés

Les nœuds vérifiés correspondent à des nœuds qui ont été testés.

La plupart des nœuds ont été générés par IA et demandent à être testés.

---

# Exemples de flux

## Watermark

![CLI10](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI10.png?raw=true)

Ce flux utilise **ffmpeg**.

1. Lorsque vous lancez le flux, il va vous demander quelle place, en %, doit prendre le watermark sur l'image à traiter.
2. Le flux retire la hauteur et la largeur de l'image à traiter et créé deux variables correspondant au %age voulu. (ffmpeg)
3. Le Watermark est redimensionné pour correspondre au %age voulu. (ffmpeg)
4. Le Watermark est déposé en bas à droite de l'image, à 10 pixels de chaque bord. (ffmpeg)
5. Le résultat est sauvegardé au format PNG sous le même nom que le fichier d'origine avec "-WM" à la fin.

## Vectorisation

![CLI06](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI06.png?raw=true)

Ce flux utilise **ffmpeg** et **potrace**.

1. Lorsque vous lancez le flux, il demandera la qualité voulue (en px) et où doit se situer la "coupure", c'est à dire, s'il ya un flou, à quel niveau de gris doit être réalisé la vectorisation.
2. Le fichier est transformé en BMP, format de base de Potrace.
3. L'image est redimensionnée à la qualité voulue.
4. L'image est vectorisée en SVG.
5. Le résultat est sauvegardé au format SVG avec le nom d'origine de l'image.

Mais vous pouvez simplement modifier votre flux pour, par exemple, rendre le principe de qualité plus compréhensible, en demandant une valeur de 1 à 16 :

![CLI07-2](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI07-2.png?raw=true)

Le problème est que si l'on prend une photo en couleur, la vectorisation peut ne pas correspondre aux attentes.

On peut donc créer un flux plus complexe créant cinq images : 

1. basée sur l'image en couleur
2. basée sur une mise en noir et blanc
3. basée sur le canal rouge
4. basée sur le canal vert
5. basée sur le canal bleu

![CLI08](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI08.png?raw=true)

## Modification image par traitement audio

![CLI09](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI09.png?raw=true)

Ce flux utilise **ffmpeg**, **imagemagick**, **sox** ainsi que des **scripts python persos**.

1. On demande la taille du fichier image finale
2. On va chercher la résolution de l'image d'origine pour en créer une variable
3. On sépare le fichier d'origine en trois fichiers image correspondant aux trois canaux de couleurs
4. Chaque couleur est transférée vers un spectrogramme audio dans un FLAC
5. Chaque audio reçoit un écho différent
6. On extrait de chaque audio le spectrogramme avec comme couleurs un dégradé de gris : une fois avec la résolution d'origine et une fois avec la résolution demandée
7. On reconstruit deux images : une dans la résolution d'origine et une dans la résolution demandée

Le but de ce flux est de reproduire plus fidèlement les effets de la télé analogique.







## A venir 

* Ajouter plus de dépendances et dans l'interface des zones pour voir les urls de téléchargement
* Pour les paramètres, afficher une explication plutôt que le paramètre (par exemple "Bas-Droit) pour le watermark plutôt que le paramètre complet.
* Indiquer pour quel langage est fait le nœud (batch, bash ou powershell) et faire en sorte de ne voir que ceux voulus.
