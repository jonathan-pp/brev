# Brev — spec (paste this into the LLM prompt)

Brev compiles to optimized C (same speed as C). Python-like, but write it COMPACT: no spaces around operators, 1-space indent, shortest forms.

## Basics
- Blocks = indentation; `:` before a block is optional. One-liners: `if x>0:y=1;z=2`
- `# comment` (# + space). `#a` = length of a. `;` separates statements.
- Top-level code is the program. Functions and types are defined at top level.

## Print, input, variables, constants
```
.x,y               # print, space-separated + newline;  . alone = empty line
put a,b            # print without separator/newline
n=?  x=?.  s=??    # read int / float / line;  a=?"Age? " shows a prompt
x=5                # variable (type inferred); never-assigned vars start at 0 / 0.0 / ""
MAX=100            # UPPERCASE = constant (assigned once)
```

## Types
`i` int64, `f` float64, `b` bool, `s` string (UTF-8), `[T]` list, `{K:V}` dict (K = i f b s), structs.
Inferred; annotate only when needed: `a:[i]=[]`, `d:{s:f}={}`.

## Functions
```
fib n                       # params typed from calls; last expression = return value
 n<2?n:fib(n-1)+fib(n-2)
sq x=x*x                    # one-liner
dist a:f b:f->f             # optional annotations
 return sqrt(a*a+b*b)
```
`global x` to assign a top-level variable inside a function. Method sugar: `a.sort()` == `sort(a)`, `p.f(x)` == `f(p,x)`.

## Structs (reference semantics, like Python objects)
```
type P x y                  # field types inferred; or  type P x:f y:f
p=P(1.0,2.0); p.x+=1; .p    # prints P(2.0, 2.0)
type Node v next:Node       # unset struct fields are null; test with  if n.next
```

## Statements
```
if c ... elif c ... else ...      while c ...      break continue return pass
for i<n          for i=a<=b       for i=a<b,2      for i=n-1>=0
for x in a       for i,x in a     for c in s       for k in d      for k,v in d
assert c,msg
```

## Expressions
`+ - * / // % **` (`/` float division; `//` `%` floor like Python), `& | ^ ~ << >>`,
`== != < <= > >=` (chainable), `and or not`, `c?a:b`, `x in a`, `a[i] a[-1] a[i:j]`,
`"x={x} m={m:.2f}"` interpolation, `[e for x in a if c]` comprehension.
Lists: `[1,2]`, `[0]*n`, `a<<x` push, `a+b`. Dicts: `{"a":1}`, `d[k]` (missing key → 0/""/[] and inserted), `k in d`.
Dicts keep insertion order. `==` compares lists, dicts and structs by content.

## Built-ins
- math: `abs min max sum sqrt sin cos tan atan2 exp log log2 log10 pow hypot floor ceil round trunc clamp gcd lcm isqrt popcnt`, `PI INF IMAX IMIN`
- convert: `int float str bool chr ord fmt(x,decimals) hex bin`
- strings: `len upper lower trim split(s[,sep]) join(a,sep) find has count starts ends replace rep chars rev isdigit isalpha isalnum isspace`
- lists: `push pop(a[,i]) ins(a,i,x) del(a,i) clear sort rsort sorted rev revd copy fill has find count ext swap range bsearch uniq hpush hpop shuffle choice`
- key functions: `sort(a,f) rsort(a,f) sorted(a,f) min(a,f) max(a,f)` (f = name of a 1-arg function)
- dicts: `keys vals get(d,k,default) has del(d,k) clear len`
- random/time: `rand() rnd(n) rnd(a,b) seed(x) clock() sleep(s)`
- io: `input() lines() ints() floats() readf(path) writef(path,s) arg(i) argc() exit(c)`

Python spellings work too: `print() input() def append len range enumerate items values True False f"..." math.sqrt`.

Not available: classes/inheritance, closures/lambdas, exceptions, sets (use a dict), modules.
