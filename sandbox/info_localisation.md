### code article 
Section "Code brève ADIT" (partie basse droite) 
```html
<span class="style15">Code br&egrave;ve<br>ADIT : </span><a href="...67068.htm">67068</a>
```
### Numéro bulletin
Zone de contenu principal (corps de page)
```html
<span class="style32">BE France 258</span>
```
### Date de l'article
Balise `<title>` (en-tête) et dans la barre de titre du corps de page (même `<p>` que le numéro bulletin, via `style42`)
```html
<title>2011/06/21&nbsp;&gt; BE France&nbsp;258&nbsp;&gt; ...</title>
```
```html
<p><span class="style32">BE France 258</span><span class="style55">&gt;&gt;</span><span class="style42">&nbsp;&nbsp;21/06/2011</span></p>
```
> Note : `style42` est partagé avec la rubrique — ici il est distinguable car il est dans le même `<p>` que `style32` (numéro bulletin).

### La rubrique
Zone de contenu principal (corps de page), premier élément du `<p class="style96">` contenant aussi le titre
```html
<p class="style96"><span class="style42">Focus<br></span><span class="style17">...</span></p>
```
> Note : `style42` est partagé avec la date — ici il est distinguable car il est le premier enfant d'un `<p class="style96">`.

### Titre de l'article 
Balise `<title>` (en-tête) et zone de contenu principal (corps de page), sous la rubrique
```html
<span class="style17">Physique : Mathias Fink, un bel exemple de chercheur qui innove</span>
```
(Classe Style17 unqiue dans chaque fichier)

### Auteur de l'article
Section "Rédacteur" en bas de page (colonne gauche sombre). `style28` est partagé avec d'autres labels ("contacts :", etc.) — l'auteur est identifiable par le `style28` dont le contenu textuel est "Rédacteur :", suivi du `style95` dans la cellule voisine.
```html
<span class="style28">R&eacute;dacteur :</span>
...
<span class="style95">ADIT - Jean-Fran&ccedil;ois Desessard - email : <a href="mailto:jfd@adit.fr">jfd@adit.fr</a></span>
```

### Texte de l'article
Zone de contenu principal (corps de page), dans le `<p class="style96">` dont le premier enfant est un `<span class="style95">` (et non `<span class="style42">` comme pour la rubrique)
```html
<p class="style96"><span class="style95">Le 27 avril dernier, le CNRS d&eacute;cernait...</span></p>
```

### La /les images avec leur(s) URL(s) et leur(s) légende(s) respective(s)
Colonne gauche (sidebar), pas de légende explicite dans le HTML
```html
<img src="http://www.bulletins-electroniques.com/Resources_fm/drapeau01/france.jpeg" ...>
<img src="http://www.bulletins-electroniques.com/Resources_fm/ambassade01/france.png" ...>
```
> Note : l'article ne contient pas d'image illustrative avec légende — uniquement des images de mise en page.

### Les informations de contact
Section "Pour en savoir plus, contacts :" en bas de page. Identifiable par le `style28` dont le texte est "Pour en savoir plus, contacts :", suivi du `style85` dans la cellule voisine au sein d'un **`<p class="style44">`**.
> Note : `style85` seul n'est pas unique (aussi utilisé pour les liens de navigation "Suivant/Précédent") — c'est la combinaison `<p class="style44"><span class="style85">` qui est l'identifiant fiable.
```html
<span class="style28">Pour en savoir plus, contacts :</span>
...
<p class="style44"><span class="style85">Institut Langevin &quot;Ondes et Images&quot; - Mathias Fink
- email : <a href="mailto:mathias.fink@espci.fr">mathias.fink@espci.fr</a>
- <a href="http://www.institut-langevin.espci.fr">http://www.institut-langevin.espci.fr</a></span></p>
```
