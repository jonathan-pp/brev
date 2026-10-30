# Guide de Brev

Brev est un petit langage de programmation pensé pour être écrit par des IA (LLM) avec le moins de tokens possible, et qui tourne aussi vite que du C. Il ressemble à Python, en plus court.

## Installation

Il faut Python 3 et un compilateur C (gcc ou clang). Fonctionne sous Linux, macOS et Windows via WSL.

```
sh install.sh
brev version
```

## Premier programme

Crée `salut.bv` :
```
n=??"Ton nom ? "
."Bonjour {n} !"
```
Lance-le avec `brev run salut.bv`. Brev traduit le programme en C, le compile, garde l'exécutable en cache, puis l'exécute.

## Afficher et lire

| Écrire | Effet |
|---|---|
| `.x` | affiche x puis un retour à la ligne |
| `.a,b,c` | affiche plusieurs valeurs séparées par des espaces |
| `put a,b` | affiche sans séparateur ni retour à la ligne |
| `n=?` | lit un entier |
| `x=?.` | lit un nombre à virgule |
| `s=??` | lit une ligne de texte |
| `a=?"Âge ? "` | affiche une question puis lit |

Dans une chaîne, `{x}` insère une valeur et `{x:.2f}` l'arrondit à 2 décimales : `."Total : {t:.2f} €"`.

## Variables et constantes

```
x=5          # variable : son type est deviné
c++          # une variable jamais affectée vaut 0
MAX=100      # nom en MAJUSCULES = constante, interdite de modification
```

## Types

| Type | Exemple |
|---|---|
| entier `i` | `42` |
| nombre à virgule `f` | `3.14` |
| booléen `b` | `true`, `false` |
| texte `s` | `"bonjour"` |
| liste `[T]` | `[1,2,3]` |
| dictionnaire `{K:V}` | `{"a":1}` |
| structure | `P(1,2)` |

Les types sont devinés. On les précise seulement quand c'est impossible à deviner, par exemple pour une liste vide : `a:[i]=[]`.

## Conditions et boucles

```
if x>0:.x
elif x<0:."négatif"
else:."zéro"

for i<10:put i," "        # i de 0 à 9
for i=1<=10               # i de 1 à 10
for i=10>0,-2             # 10, 8, 6, 4, 2
for x in liste            # chaque élément
for i,x in liste          # index et élément
while x>1:x//=2
```
`c?a:b` vaut `a` si `c` est vrai, sinon `b`.

## Fonctions

```
carre x=x*x               # fonction d'une ligne

fib n                     # la dernière expression est la valeur renvoyée
 n<2?n:fib(n-1)+fib(n-2)

aire l:f h:f->f           # types optionnels
 return l*h
```

## Listes

```
a=[5,3,8]
a<<1                      # ajoute 1 à la fin
.a[0],a[-1],a[1:3],#a     # premier, dernier, tranche, longueur
sort(a)                   # trie
carres=[x*x for x in a if x>2]
```
Fonctions utiles : `pop ins del sort rsort sorted rev has find count sum min max uniq hpush hpop shuffle`.

## Texte

```
s="Bonjour le monde"
.upper(s),#s,split(s),replace(s,"o","0"),s[0:7]
for c in "été":put c,"|"   # parcourt les caractères, accents compris
```

## Dictionnaires

```
n={}
for w in split("le chat et le chien"):n[w]+=1   # une clé absente vaut 0
.n                         # {'le': 2, 'chat': 1, 'et': 1, 'chien': 1}
."chat" in n,get(n,"loup",0),keys(n)
for mot,c in n.items():."{mot} : {c}"
```
L'ordre d'insertion est conservé, comme en Python.

## Structures

```
type Pers nom age
p=Pers("Ana",25)
p.age+=1
.p                        # Pers('Ana', 26)

age x=x.age
gens=[Pers("Bob",31),p]
sort(gens,age)            # tri selon une fonction
.max(gens,age).nom
```
Une structure se comporte comme un objet Python : la passer à une fonction permet de la modifier.

## Erreurs

Les erreurs indiquent la ligne et proposent une correction :
```
prog.bv:2: error: unknown function 'lenn'
  2 | .lenn(a)
  hint: did you mean 'len'?
```
En cas de plantage pendant l'exécution, `brev run --safe prog.bv` vérifie les index de listes.

## Commandes

| Commande | Rôle |
|---|---|
| `brev` | mode interactif |
| `brev run f.bv` | compile et exécute |
| `brev build f.bv -o prog` | crée un exécutable autonome |
| `brev c f.bv` | montre le C généré |
| `brev check f.bv` | vérifie sans exécuter |
| `brev test` | lance la suite de tests |

## Utiliser Brev avec une IA

Colle le contenu de `SPEC.md` (environ 1 100 tokens) dans le prompt, puis demande le programme en Brev. Donne-lui les messages d'erreur du compilateur s'il se trompe : ils sont conçus pour qu'il se corrige seul.

## Limites

- Pas de classes avec héritage, de fonctions anonymes, d'exceptions ni de modules.
- Pas de bibliothèques externes (web, base de données…). Brev sert au calcul, aux algorithmes et au traitement de texte ou de données.
- La mémoire n'est jamais libérée pendant l'exécution : parfait pour des programmes qui calculent puis s'arrêtent, pas pour un serveur qui tourne des jours.
- `len` et les index de chaînes comptent les octets (un « é » compte 2) ; `for c in s` et `chars(s)` parcourent bien les caractères.
