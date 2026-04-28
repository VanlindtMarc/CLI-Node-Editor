
# Terminal Architect

![Logo](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/Terminal%20Architect%20Logo%20final.svg)

**Terminal Architect** est une aide à la création de flux **batch**, **bash** et **PowerShell** complexes pour **Windows** passant par une interface nodale pouvant utiliser toute commande système ou logiciel CLI.

Il est principalement créé pour des flux de traitement de fichiers auxquels il est possible de faire appel directement dans l'explorateur ou via **Envoyer vers...**

Trois types de flux peuvent être créés :
1. Le flux traite chaque fichier séparément 
2. Tous les fichiers sont traités par un même flux
3. Un certain nombre de fichiers est demandé, chacun d'un certain type, et chacun sera sélectionné par son extension pour la suite du flux.

Le **batch** est le langage principal, car langage de script historique de **Windows** et considéré comme un exécutable, contrairement au format **.PS1** de **PowerShell**. 

---
## Interface

L'interface principale est divisée en trois : 
1. Une colonne à gauche où apparaissent tous les nœuds proposés et les options générales du flux
2. Une zone centrale montrant les nœuds et leurs liens
3. Une colonne à droite où peut être généré et visualisé le code à exporter ainsi que visualisé le log d'exécution lors des tests internes.

Dans la barre de menu, vous avez également **Outils** qui vous permet d'indiquer les outils CLI que vous possédez.

![test](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI02.png)

---

## Outils

![CLI11](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI11.png)

Avant toute utilisation, vous devez indiquer les outils qui seront utilisés par les flux.

* **Nom** : Le nom simple par lequel appeler l'outil par la suite
* **Chemin** : Chemin complet vers l'outil. Cela évite d'avoir tous les outils dans son %PATH%. Si un chemin est indiqué, ce chemin sera utilisé directement dans le flux.
* **Description** : ...
* **Arg Version** : argument permettant de connaître la version de l'outil et de réaliser un test pour la connaitre.

**Attention** au choix du nom à la création d'un outil. Si par la suite, vous changez le nom d'un outil, les nœuds y faisant appel ne fonctionneront plus.

--- 

## Nœuds

Un nœud est une opération dans le flux permettant de le faire évoluer.

Il existe plusieurs types de nœuds :

* **Fichier** : entrées et sorties de flux
* **Système** : gestion des variables (et debug simple)

Ces deux types de nœuds ne peuvent être modifiés, car directement gérés par **Terminal Architect**.

Les nœuds permettant de faire évoluer le flux sont les nœuds créés, faisant directement appels à une commande système ou à un logiciel CLI.

### Création/Edition

![CLI12](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI12.png)




###  Logiciels conseillés

* 7zip : compression/décompression
* BPM Counter : calcul très précis du BPM sur WAV et MP3
* Curl : transfert de données
* exiftool : manipulation de métadonnées
* ffmpeg : manipulation audio/image/vidéo
* flac : encodeur FLAC
* HandBrake : encodeur vidéo
* lame : encodeur MP3
* metaflac : modification des métas FLAC
* Pandoc : transformation de documents 
* Potrace : vectorisation vers SVG
* Qalculate : calculatrice renvoyant des valeurs non-entières
* sox : transformation audio

### Nœuds CLI

Chaque nœud peut être paramétré via quatre onglets.

#### Général 

![CLI12](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI12.png)

* **Nom du nœud** : nom réel
* **Nom affiché** : nom affiché dans les menus
* **Catégorie** : en général le nom de la commande CLI
* **Sous-catégorie** : le type d'usage fait de la commande
* **Commande CLI** : commande dans son nom court
* **Format de sortie** : format proposé par défaut
* **Formats suggérés** : autres formats dans lesquels il est possible de sauver le résultat
* **Description**
* **Couleur hexa** : couleur du nœud dans l'interface.



#### Ports

![CLI13](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI13.png)

Indique le nombre de fichiers attendus en entrée et en sortie.

Le port d'entrée principal sera appelé via {input}, le deuxième via {input2} et ainsi de suite.

Pareil pour {output}.

#### Paramètres

![CLI14](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI14.png)

Permet de créer des variables locales qui seront utilisées lors de l'appel à la commande. 

#### Template

![CLI15](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI15.png)

Commande à utiliser (dans son nom court indiqué dans la liste des outils), pouvant faire appel aux variables locales et globales.

---

## Bibliothèques de nœuds

## Nœuds d'entrée

![CLI03](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI03.png)

Il existe quatre nœuds d'entrée : 
1. **Fichier input** : ce nœud est celui par défaut et correspond au(x) fichier(s) que vous enverrez vers votre flux
2. **Fichier source** : indique un fichier fixe qui sera utilisé pendant le flux (par exemple un watermark pour des photos)
3. **Multi-fichiers** : indique le nombre et le type de fichier attendus pour ce flux.
4. **Liste** : indique que le fichier d'entrée est un fichier de type texte dont chaque ligne est un élément à traiter (liste de fichiers, d'URL...)

Par défaut, l'interface vous présentera le nœud d'entrée **Fichier Input** et le nœud de sortie **Fichier Destination**, qui sont les bases d'un flux : une entrée → une sortie.

---

## Nœud de sortie

Il n'y en a qu'un, qui peut être appelé plusieurs fois si plusieurs fichiers sont à créer.

On y indique simplement le nom et l'extension voulue.

---

## Variables et opérations mathématiques

Vous pouvez faire appel à plusieurs nœuds permettant d'assigner des variables à votre flux.

Dans chacun des cas, une fois une variable créée, vous pourrez y faire appel via ***{nom de la variable}***.

### Opérations mathématiques

Dans la catégorie **Batch**, vous pourrez trouver **Opération mathématique**, qui utilise le langage **batch** pour réaliser les opérations. Ce langage est très limité puisqu'il ne fonctionne qu'avec des entiers. Si vous demandez 5 divisé en 2, cela vous donnera 3. Mais c'est parfait pour les résolutions.

Pour les calculs plus complexes, je vous conseille l'outil **Qalculate**.

### Variables d'entrée

Ce nœud fera qu'une série de questions sera posée au début du flux pour être ré-utilisée par la suite.

### Variables globales 

Certains nœuds peuvent renvoyer une valeur sauvegardée sous forme de fichier TXT, par exemple la largeur d'une image, l'artiste d'un audio...

Le nœud **Variables globales** peut créer des variables basées sur ces fichiers TXT, pouvant alors être utilisées dans toute l'interface.

### Choix

Le choix est une question posée proposant jusqu'à 8 propositions de réponses.

Vous pouvez indiquer un choix par défaut et un timer au bout duquel la proposition par défaut sera choisie automatiquement.

#### Choix - Si

![CLI19](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI19.png)

Cela permet d'indiquer une valeur correspondant aux choix, pouvant alors être renvoyée vers une variable globale.

### Math SI

![CLI21](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI21.png)

Ce nœud analyse deux variables via l'un des opérateurs : 

* **EQU** : "Equal", ou "égal"
* **NEQ** : "Not Equal", ou "non égal"
* **LSS** : "Less", ou "plus petit"
* **LES** : "Less or equal", ou "plus petit ou égal"
* **GTR** : "Greater", ou "plus grand"
* **GEQ** : "Greater or equal", ou "plus grand ou égal"

Il renverra alors la valeur si l'opération est vraie

### Math SI if else

idem, mais permet de renvoyer une autre valeur si l'opération est fausse

### Math SI if elseif

idem, mais renvoie trois valeurs : 

1. si inférieur
2. si égal
3. si supérieur

## Switch

![CLI22](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI22.png)

Ce nœud vous permet de diviser votre flux en sous-flux en fonction de certaines conditions.

Ce nœud reçoit une valeur en entrée afin de permettre à celle-ci de continuer le flux.

Il y a en sortie le nombre de condition + 1.

La dernière sortie est celle "par défaut" si aucune des conditions n'est remplie.

### Merge

Ce nœud permet de réunir différents flux créés par Switch afin de leur faire suivre une suite de flux unique.


---



---

## Nœuds vérifiés

Les nœuds vérifiés correspondent à des nœuds qui ont été testés.

La plupart des nœuds ont été générés par IA et demandent à être testés.

---

## Exemples de noeuds

### ImageMagick - Redimensioinner Max
```
magick {input} -resize {width}x{height} {output}
```
### HandBrakeCLI - ISO 2 MKV
```
HandBrakeCLI -i {input} -o {output}  --format av_mkv  --encoder {Encodeur}  --encoder-preset p4  --quality {Qualité} --all-audio  --all-subtitles  --aencoder  {AudioEncodeur}   --subtitle-burned=none --main-feature --min-duration {Durée min}  --maxWidth {Largeur Max} --maxHeight {Hauteur Max} --loose-anamorphic --comb-detect --decomb
```
---

# Exemples de flux

## Watermark

![CLI10](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI10.png)

Ce flux utilise **ffmpeg**.

1. Lorsque vous lancez le flux, il va vous demander quelle place, en %, doit prendre le watermark sur l'image à traiter.
2. Le flux retire la hauteur et la largeur de l'image à traiter et créé deux variables correspondant au %age voulu. (ffmpeg)
3. Le Watermark est redimensionné pour correspondre au %age voulu. (ffmpeg)
4. Le Watermark est déposé en bas à droite de l'image, à 10 pixels de chaque bord. (ffmpeg)
5. Le résultat est sauvegardé au format PNG sous le même nom que le fichier d'origine avec "-WM" à la fin.

## Watermark 2

![CLI18](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI18.png)

Ici, nous pouvons voir un appel au nœud **Math SI** qui me dit si la photo est horizontale ou verticale.

Si la largeur est plus grande ou égale à la hauteur, j'applique le watermark "horizontal.png".

Si ce n'est pas le cas, j'applique le watermark "vertical.png".

## Watermark 3

![CLI20](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI20.png)

Nous faisons ici appel au nœud **Math SI if elseif** qui permet de faire appel aux trois possibilités afin d'affecter à chacune une valeur.

## Vectorisation

![CLI06](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI06.png)

Ce flux utilise **imagemagick** et **potrace**.

1. Lorsque vous lancez le flux, il demandera la qualité voulue (en px) et où doit se situer la "coupure", c'est à dire, s'il ya un flou, à quel niveau de gris doit être réalisé la vectorisation.
2. Le fichier est transformé en BMP, format de base de Potrace.
3. L'image est redimensionnée à la qualité voulue.
4. L'image est vectorisée en SVG.
5. Le résultat est sauvegardé au format SVG avec le nom d'origine de l'image.

Mais vous pouvez simplement modifier votre flux pour, par exemple, rendre le principe de qualité plus compréhensible, en demandant une valeur de 1 à 16.

Le problème est que si l'on prend une photo en couleur, la vectorisation peut ne pas correspondre aux attentes.

On peut donc en même temps créer un flux plus complexe créant cinq images : 

1. basée sur l'image en couleur
2. basée sur une mise en noir et blanc
3. basée sur le canal rouge
4. basée sur le canal vert
5. basée sur le canal bleu

![CLI08](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI08.png)

## Modification image par traitement audio

![CLI09](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI09.png)

Ce flux utilise **ffmpeg**, **imagemagick**, **sox** ainsi que des **scripts python persos**.

1. On demande la taille du fichier image finale
2. On va chercher la résolution de l'image d'origine pour en créer une variable
3. On sépare le fichier d'origine en trois fichiers image correspondant aux trois canaux de couleurs
4. Chaque couleur est transférée vers un spectrogramme audio dans un FLAC
5. Chaque audio reçoit un écho différent
6. On extrait de chaque audio le spectrogramme avec comme couleurs un dégradé de gris : une fois avec la résolution d'origine et une fois avec la résolution demandée
7. On reconstruit deux images : une dans la résolution d'origine et une dans la résolution demandée

Le but de ce flux est de reproduire plus fidèlement les effets de la télé analogique.

## Transformer un  ISO ou Remux en MKV

![CLI17](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI17.png)

Ce flux utilise **HandBrake-CLI**.

## Calculer le BPM

![CLI23](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI23.png)

Nous allons ici utiliser le nœud **Switch** car les différents outils permettant de calculer le BPM et d'inscrire cette information en tant que tag dans un fichier différent selon le format.

L'outil pour calculer le BPM ne fonctionne qu'avec les extensions **WAV** et **MP3**. Il faut donc transformer l'audio en **MP3** avant le calcul.

En fonction du format, ce n'est pas le même outil qui est utilisé pour inscrire le tag, ffmpeg ayant des problèmes avec les flac.

## Calculer le BPM 2

![CLI24](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI24.png)

Dans la première version, nous avions plusieurs appels aux nœuds **Calcul BPM**, **Variables Globales** et **Fichier Destination**.

Ici, nous utilisons le nœud **Merge** afin de réunir les propositions du switch et ne garder que la condition remplie afin de suivre le flux.

Enfin, une fois l'ajout du tag fait, nous réunissons les résultats pour ne faire appel qu'à un seul appel au fichier de destination puisqu'il ne peut y avoir qu'un seul fichier créé en fonction du flux.

## Informations systèmes

![CLI25](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/cli25.png)

Créez simplement un fichier HTML vide et lancez le script sur celui-ci.

Il se transformera en un fichier comprenant l'ensemble de vos fichiers installés : 

![CLI26](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/cli26.png)

## Téléchargement YouTube

![CLI27](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI27.png)

Nous faisons appel au nœud d'entrée Liste qui reçoit en entrée un fichier TXT contenant, ici, des URL.

Pour chaque URL, il ira chercher l'auteur et le nom de la vidéo puis téléchargera l'audio au format MP3 vers un format **Auteur - Titre.mp3**

---

## Bugs connus 
- Lorsque l'on modifie un paramètre de nœud, il faut réécrire le paramètre, car il y a un bug dans l'édition
- Si vous lancez un flux depuis l'interface et qu'il y a des questions posées, le flux se bloquera car les questions ne sont pas demandées.
- Plante si on teste "tous les outils"
- Si on modifie la couleur d'un nœud, le pickcolor ne reprend pas la couleur affectée au nœud

## Ajouts à venir
- Clic droit sur un nœud pour le remplacer directement par un autre
- Ajout à la fin des fichiers générés d'une zone de remarque contenant le flux. Cette zone pourrait être captée par l'outil afin de récupérer le flux directement d'un flux généré.
- Ajouter une colonne "URL" pour le gestionnaire d'outils
- Ajouter un téléchargement automatique des outils
- Faire en sorte que les tests ne soient réalisés que sur les outils ayant un "arg version"
- Permettre de remplacer un flux par un autre s'il a le même nombre de ports d'entrée et de sortie
