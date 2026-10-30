# Brev 0.3

Un langage de programmation simple, pensé pour que les IA écrivent vite (2 à 4 fois moins de tokens que Python ou C), et compilé en C optimisé (même vitesse que le C, 30 à 70 fois plus rapide que Python).

```
type Pers nom age
gens=[Pers("Bob",31),Pers("Ana",25)]
age p=p.age
sort(gens,age)
for p in gens:."{p.nom} a {p.age} ans"
```

## Démarrer
```
sh install.sh        # installe la commande brev
brev                 # mode interactif
brev run ex/vie.bv   # exécute un exemple
brev test            # 19 tests
```

## Contenu
- `GUIDE.md` : le guide complet, en français
- `SPEC.md` : la spec compacte à coller dans le prompt d'une IA
- `ex/` : exemples (jeu de la vie, gestion de stock, fréquence des mots…)
- `tests/` : suite de tests (sorties attendues et messages d'erreur)
- `bench/` : comparaisons de tokens et de vitesse avec C et Python
- `brev.py` (commande), `lexparse.py` (analyse), `compiler.py` (types et génération de C), `rt.py` (runtime C)

## Résultats mesurés
| Programme | Tokens Brev | Tokens Python | Tokens C | Temps Brev | Temps C | Temps Python |
|---|---|---|---|---|---|---|
| fib(38) | 25 | 36 | 65 | 0,053 s | 0,053 s | 3,29 s |
| crible 20 M | 44 | 66 | 127 | 0,095 s | 0,094 s | 3,99 s |
| collatz 2 M | 68 | 99 | 146 | 0,385 s | 0,378 s | 27,97 s |
| dictionnaire 10 M | — | — | — | 0,030 s | — | 1,03 s |

Tokens comptés avec le tokenizer o200k (GPT) ; Brev écrit ici en style lisible, le style compact descend encore plus bas.
