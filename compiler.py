# Type inference + C code generation for Brev (basic version).
import difflib
from lexparse import CErr, N
from rt import (CORE, CORE2, LIST_DECL, LIST_BODY, LIST_FUNCS, LIST_NUM, LIST_CMP,
                MAP_DECL, MAP_BODY, MAP_FUNCS, fill, split_funcs)

NUM = ('i', 'f', 'b')
CONSTS = {'PI': ('f', 'M_PI'), 'INF': ('f', 'INFINITY'), 'IMAX': ('i', 'INT64_MAX'), 'IMIN': ('i', 'INT64_MIN')}
ALIASES = {'append': 'push', 'extend': 'ext', 'insert': 'ins', 'index': 'find', 'strip': 'trim',
           'startswith': 'starts', 'endswith': 'ends', 'reverse': 'rev', 'random': 'rand', 'randint': 'rnd',
           'time': 'clock', 'fabs': 'abs', 'length': 'len', 'size': 'len', 'contains': 'has', 'heappush': 'hpush',
           'heappop': 'hpop', 'bisect_left': 'bsearch', 'bisect': 'bsearch', 'reversed': 'revd'}
MATH1 = {'sqrt', 'sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'exp', 'log', 'log2', 'log10', 'cbrt', 'sinh', 'cosh', 'tanh'}
MATH2 = {'atan2', 'hypot', 'pow', 'fmod'}
BUILTINS = MATH1 | MATH2 | {
    'len', 'abs', 'min', 'max', 'sum', 'floor', 'ceil', 'round', 'trunc', 'clamp', 'gcd', 'lcm', 'isqrt', 'popcnt',
    'clz', 'ctz', 'rand', 'rnd', 'seed', 'shuffle', 'choice', 'clock', 'sleep', 'int', 'float', 'str', 'bool', 'chr',
    'ord', 'fmt', 'hex', 'bin', 'upper', 'lower', 'trim', 'split', 'join', 'find', 'rep', 'starts', 'ends', 'replace',
    'count', 'isdigit', 'isalpha', 'isspace', 'isupper', 'islower', 'isalnum', 'chars', 'push', 'pop', 'ins', 'del',
    'clear', 'sort', 'rsort', 'sorted', 'rev', 'revd', 'copy', 'fill', 'has', 'ext', 'swap', 'range', 'bsearch',
    'uniq', 'hpush', 'hpop', 'input', 'lines', 'ints', 'floats', 'readf', 'writef', 'arg', 'argc', 'exit', 'eof', 'list',
    'keys', 'vals', 'get'}
ALIASES['values'] = 'vals'


SCAL = ('i', 'f', 'b', 's')


def tn(t):
    if t is None: return '?'
    if isinstance(t, str): return {'v': 'nothing'}.get(t, t)
    if t[0] == 'L': return '[' + tn(t[1]) + ']'
    if t[0] == 'M': return '{' + tn(t[1]) + ':' + tn(t[2]) + '}'
    return t[1]


def holes(t):
    if t is None: return True
    if isinstance(t, str): return False
    if t[0] == 'L': return holes(t[1])
    if t[0] == 'M': return holes(t[1]) or holes(t[2])
    return False


def is_list(t):
    return isinstance(t, tuple) and t[0] == 'L'


def is_map(t):
    return isinstance(t, tuple) and t[0] == 'M'


def is_struct(t):
    return isinstance(t, tuple) and t[0] == 'S'


def mg(t):
    if t is None: return 'X'  # unknown yet (only in intermediate passes)
    if isinstance(t, str): return t
    if t[0] == 'L': return 'L' + mg(t[1])
    if t[0] == 'M': return 'M' + mg(t[1]) + mg(t[2]) + '_'
    return 'T' + t[1] + '_'


def ct(t):
    if t in ('i', 'f', 'b', 's'): return {'i': 'I', 'f': 'F', 'b': 'B', 's': 'S'}[t]
    if t == 'v': return 'void'
    return mg(t)


def jstrict(a, b, L, what):
    if a is None: return b
    if b is None: return a
    if a == b: return a
    if is_list(a) and is_list(b): return ('L', jstrict(a[1], b[1], L, what))
    if is_map(a) and is_map(b): return ('M', jstrict(a[1], b[1], L, what), jstrict(a[2], b[2], L, what))
    raise CErr('type conflict for %s: %s vs %s' % (what, tn(a), tn(b)), L, 0)


def join(a, b, L, what):
    if a is None: return b
    if b is None: return a
    if a == b: return a
    if a in NUM and b in NUM: return 'f' if 'f' in (a, b) else 'i'
    return jstrict(a, b, L, what)


def cstr(v):
    bs = v.encode('utf-8'); out = []
    for ch in bs:
        c = chr(ch)
        if 32 <= ch < 127 and c not in '"\\?': out.append(c)
        else: out.append('\\%03o' % ch)
    return '((S){"%s",%d})' % (''.join(out), len(bs))


def walk(x):
    if isinstance(x, N):
        yield x
        for v in x.__dict__.values(): yield from walk(v)
    elif isinstance(x, (list, tuple)):
        for v in x: yield from walk(v)


def assigned_names(body):
    out = set()
    for n in walk(body):
        if n.k == 'assign':
            for t in n.lhs:
                if t.k == 'var': out.add(t.name)
        elif n.k == 'decl': out.add(n.name)
        elif n.k in ('for', 'comp'):
            out.add(n.var)
            if getattr(n, 'var2', None): out.add(n.var2)
    return out


class Fn:
    def __init__(s, name, params, ret, body, line):
        s.name = name; s.params = params; s.ret_decl = ret; s.body = body; s.line = line
        s.ret = ret; s.locals = {}; s.annot = {}
        for p, t in params:
            s.locals[p] = t
            if t: s.annot[p] = t
        gl = set()
        for n in walk(body):
            if n.k == 'global': gl.update(n.names)
        s.declared_globals = gl
        s.localnames = (assigned_names(body) | {p for p, _ in params}) - gl


class Compiler:
    def __init__(s, structs, funcs, main, safe=False):
        s.safe = safe
        s.structs = {}
        for st in structs:
            if st.name in s.structs: raise CErr("type '%s' defined twice" % st.name, st.line, 1)
            names = [f for f, _ in st.fields]
            if len(set(names)) != len(names): raise CErr("duplicate field in type '%s'" % st.name, st.line, 1)
            s.structs[st.name] = {'fields': names, 'types': dict(st.fields),
                                  'annot': {f for f, t in st.fields if t is not None}, 'line': st.line}
        s.sortfns = {}
        s.lastline = 0
        s.fns = {}
        for f in funcs:
            if f.name in s.fns: raise CErr("function '%s' defined twice" % f.name, f.line, 1)
            if f.name in s.structs: raise CErr("'%s' is both a type and a function" % f.name, f.line, 1)
            s.fns[f.name] = Fn(f.name, f.params, f.ret, f.body, f.line)
        s.main = Fn('main', [], 'v', main, 1)
        s.main.localnames = assigned_names(main)
        s.gnames = set()
        for f in s.fns.values():
            for n in walk(f.body):
                if n.k == 'var' and n.name not in f.localnames and n.name in s.main.localnames:
                    s.gnames.add(n.name)
            for g in f.declared_globals:
                if g in s.main.localnames: s.gnames.add(g)
        s.types = {('L', 'i'), ('L', 'f'), ('L', 's')}
        s.final = False
        s.litconsts = {}
        s.check_consts(main, s.main)
        for f in s.fns.values(): s.check_consts(f.body, f)

    # ---------- constants: UPPERCASE names, assigned exactly once ----------
    def check_consts(s, body, fn):
        seen = {}
        hint = 'constants are UPPERCASE names assigned once; use a lowercase name for a variable'

        def mark(name, L, op, inloop):
            if not name.isupper(): return
            if fn is not s.main and name in fn.declared_globals:
                s.err("cannot modify constant '%s'" % name, L, hint)
            if op != '=': s.err("'%s' is a constant and cannot be modified" % name, L, hint)
            if inloop: s.err("constant '%s' is assigned inside a loop" % name, L, hint)
            if name in seen: s.err("constant '%s' is already defined on line %d" % (name, seen[name]), L, hint)
            seen[name] = L

        def rec(stmts, inloop, depth):
            for x in stmts:
                if x.k == 'assign':
                    for t in x.lhs:
                        if t.k == 'var': mark(t.name, x.line, x.op, inloop)
                    if fn is s.main and depth == 0 and len(x.lhs) == 1 and x.op == '=' and x.lhs[0].k == 'var' \
                            and x.lhs[0].name.isupper() and x.rhs[0].k in ('int', 'flt', 'bool', 'str'):
                        s.litconsts[x.lhs[0].name] = x.rhs[0]
                elif x.k == 'decl':
                    mark(x.name, x.line, '=', inloop)
                elif x.k == 'if':
                    for _, b in x.arms: rec(b, inloop, depth + 1)
                    if x.els: rec(x.els, inloop, depth + 1)
                elif x.k == 'while':
                    rec(x.body, True, depth + 1)
                elif x.k == 'for':
                    for v in (x.var, getattr(x, 'var2', None)):
                        if v and v.isupper(): s.err("loop variable '%s' cannot be a constant (UPPERCASE)" % v, x.line, hint)
                    rec(x.body, True, depth + 1)
        rec(body, False, 0)

    # ---------- driver ----------
    def snapshot(s):
        out = []
        for f in list(s.fns.values()) + [s.main]:
            out.append((f.name, f.ret, tuple(sorted(f.locals.items(), key=lambda kv: kv[0]))))
        for n, st in sorted(s.structs.items()):
            out.append((n, tuple(sorted(st['types'].items(), key=lambda kv: kv[0]))))
        return repr(out)

    def infer(s):
        for _ in range(100):
            snap = s.snapshot()
            for f in list(s.fns.values()) + [s.main]:
                s.compile_fn(f)
            if s.snapshot() == snap: return
        raise CErr('type inference did not converge', 1, 1)

    def compile(s):
        s.infer()
        for f in s.fns.values():
            for p, t in f.params:
                if f.locals.get(p) is None: f.locals[p] = 'i'
        for st in s.structs.values():
            for k, t in st['types'].items():
                if t is None: st['types'][k] = 'i'
        s.infer()
        s.final = True
        for n, st in s.structs.items():
            for k, t in st['types'].items():
                if holes(t):
                    raise CErr("cannot infer the type of field '%s' in type %s" % (k, n), st['line'], 1,
                               'annotate it, e.g. type %s %s:[i]' % (n, k))
        for f in list(s.fns.values()) + [s.main]:
            for n, t in f.locals.items():
                if holes(t):
                    ln = f.line
                    for x in walk(f.body):
                        if (x.k == 'assign' and any(y.k == 'var' and y.name == n for y in x.lhs)) or \
                           (x.k == 'decl' and x.name == n):
                            ln = x.line; break
                    raise CErr("cannot infer the type of '%s'" % n, ln, 1,
                               'annotate it, e.g. %s:[i]=[]' % n if is_list(t) else 'assign it a value first')
            if f.ret is None: f.ret = 'v'
        bodies = []
        for f in list(s.fns.values()) + [s.main]:
            bodies.append(s.compile_fn(f))
        return s.assemble(bodies)

    def compile_fn(s, f):
        s.cur = f; s.out = []; s.ind = 1; s.tmp = 0; s.loops = 0
        s.block(f.body, tail=f is not s.main)
        if f is s.main:
            return s.out
        if s.final and f.ret not in ('v', None):
            s.emit('{ %s _z={0}; return _z; }' % ct(f.ret))
        return s.out

    # ---------- emit helpers ----------
    def emit(s, line):
        s.out.append('    ' * s.ind + line)

    def t_(s):
        s.tmp += 1; return '_t%d' % s.tmp

    def use(s, t):
        if holes(t): return
        if is_list(t):
            s.types.add(t); s.use(t[1])
        elif is_map(t):
            if t[1] not in SCAL:
                s.err('dictionary keys must be i, f, b or s, not %s' % tn(t[1]), s.lastline)
            s.types.add(t); s.use(t[2]); s.use(('L', t[1])); s.use(('L', t[2]))

    def err(s, msg, L, hint=None):
        raise CErr(msg, L, 0, hint)

    # ---------- variables ----------
    def var_owner(s, name):
        f = s.cur
        if name in f.localnames: return f
        if name in s.gnames: return s.main
        return None

    def vartype(s, name):
        o = s.var_owner(name)
        return o.locals.get(name) if o else None

    def setvar(s, name, t, L):
        o = s.var_owner(name)
        if o is None:
            o = s.cur
        if name in o.annot:
            a = o.annot[name]
            if t is not None and not s.fits(t, a):
                s.err("'%s' is declared %s, cannot assign %s" % (name, tn(a), tn(t)), L)
            return a
        nt = join(o.locals.get(name), t, L, "variable '%s'" % name)
        o.locals[name] = nt
        return nt

    def fits(s, t, want):
        if t is None or want is None or t == want: return True
        if want == 'f' and t in ('i', 'b'): return True
        if want == 'i' and t == 'b': return True
        if (is_list(t) and is_list(want)) or (is_map(t) and is_map(want)): return s.fits_exact(t, want)
        return False

    def fits_exact(s, t, w):
        if t is None or w is None or t == w: return True
        if is_list(t) and is_list(w): return s.fits_exact(t[1], w[1])
        if is_map(t) and is_map(w): return s.fits_exact(t[1], w[1]) and s.fits_exact(t[2], w[2])
        return False

    def conv(s, t, c, want, L):
        if want is None or t is None or t == want: return c
        if want == 'f' and t in ('i', 'b'): return '((F)(%s))' % c
        if want == 'i' and t == 'b': return '((I)(%s))' % c
        if want == 'b' and t in ('i', 'f'): return '((%s)!=0)' % c
        if (is_list(t) or is_map(t)) and s.fits_exact(t, want): return c
        hint = 'write 1.0 instead of 1 to make it a float' if (want, t) == ('i', 'f') else None
        s.err('type mismatch: expected %s, got %s' % (tn(want), tn(t)), L, hint)

    def refine(s, node, newt, L):
        """the container held in `node` turned out to have type newt"""
        if node.k == 'var':
            if s.var_owner(node.name) is not None or not s.final:
                s.setvar(node.name, newt, L)
        elif node.k == 'idx':
            to, _ = s.ex(node.obj)
            if is_list(to): s.refine(node.obj, ('L', newt), L)
            elif is_map(to): s.refine(node.obj, ('M', to[1], newt), L)
        elif node.k == 'field':
            st, f = s.field_info(node)
            if st and f not in st['annot']:
                st['types'][f] = jstrict(st['types'][f], newt, L, "field '%s'" % f)

    def field_info(s, node):
        to, _ = s.ex(node.obj)
        if not is_struct(to): return None, None
        st = s.structs[to[1]]
        if node.name not in st['types']:
            m = difflib.get_close_matches(node.name, st['fields'], 1)
            s.err("type %s has no field '%s'" % (to[1], node.name), node.line,
                  "did you mean '%s'?" % m[0] if m else 'fields: ' + ' '.join(st['fields']))
        return st, node.name

    def truth(s, t, c, L):
        if t in NUM or t is None: return c
        if t == 's': return '((%s).n>0)' % c
        if is_list(t) or is_map(t): return '((%s)->n>0)' % c
        if is_struct(t): return '((%s)!=NULL)' % c
        s.err('cannot use %s as a condition' % tn(t), L)

    def tostr(s, t, c):
        if t == 's': return c
        return 'str_%s(%s)' % (mg(t), c)

    # ---------- expressions ----------
    def ex(s, e, want=None):
        s.lastline = e.line
        t, c = getattr(s, 'x_' + e.k)(e, want)
        if s.final and isinstance(t, tuple) and holes(t):
            s.err('cannot infer the element type here (%s)' % tn(t), e.line, 'give it a type, e.g. a:[i]=[]')
        if t not in (None, 'v'): s.use(t)
        return t, c

    def x_raw(s, e, want):
        return e.t, e.c

    def x_input(s, e, want):
        t, c = {'i': ('i', 'in_int()'), 'f': ('f', 'in_float()'), 's': ('s', 'in_line()')}[e.kind]
        if e.prompt is not None:
            tp, cp = s.ex(e.prompt)
            c = '(p_s(%s),%s)' % (cp, c)
        return t, c

    def x_int(s, e, want):
        if e.v == -2 ** 63: return 'i', 'INT64_MIN'
        return 'i', '%dLL' % e.v if e.v >= 0 else '(%dLL)' % e.v

    def x_flt(s, e, want):
        r = repr(e.v)
        return 'f', r if e.v >= 0 else '(%s)' % r

    def x_str(s, e, want):
        return 's', cstr(e.v)

    def x_bool(s, e, want):
        return 'b', '1' if e.v else '0'

    def x_var(s, e, want):
        n = e.name
        o = s.var_owner(n)
        if o is not None:
            return o.locals.get(n), 'v_' + n
        if n in CONSTS: return CONSTS[n]
        if s.final: s.undefined(n, e.line)
        return None, '0'

    def undefined(s, n, L):
        if n in s.fns or n in BUILTINS:
            s.err("'%s' is a function; call it with ()" % n, L)
        cands = list(s.cur.localnames) + list(s.gnames) + list(s.fns) + list(BUILTINS)
        m = difflib.get_close_matches(n, cands, 1)
        s.err("undefined name '%s'" % n, L, "did you mean '%s'?" % m[0] if m else 'assign it before use')

    def x_interp(s, e, want):
        parts = []
        for p in e.parts:
            if isinstance(p, str): parts.append(cstr(p))
            else:
                t, c = s.ex(p)
                if t == 'v': s.err('expression in {} has no value', e.line)
                parts.append(s.tostr(t, c) if t else c)
        return 's', 's_catn(%d,(S[]){%s})' % (len(parts), ','.join(parts))

    def x_un(s, e, want):
        t, c = s.ex(e.e)
        op = e.op
        if t is None: return (None, '0')
        if op == '-':
            if t not in NUM: s.err('cannot negate %s' % tn(t), e.line)
            return ('i' if t == 'b' else t), '(-%s)' % c
        if op == '!': return 'b', '(!%s)' % s.truth(t, c, e.line)
        if op == '~':
            if t not in ('i', 'b'): s.err('~ needs an integer', e.line)
            return 'i', '(~%s)' % c
        if op == '#': return 'i', s.length(t, c, e.line)

    def length(s, t, c, L):
        if t == 's': return '(%s).n' % c
        if is_list(t) or is_map(t): return '(%s)->n' % c
        s.err('cannot take the length of %s' % tn(t), L)

    def x_tern(s, e, want):
        tc, cc = s.ex(e.c)
        ta, ca = s.ex(e.a, want); tb, cb = s.ex(e.b, want)
        if ta is None or tb is None: return (ta or tb), '0'
        t = join(ta, tb, e.line, 'the two branches of ?:')
        return t, '(%s?%s:%s)' % (s.truth(tc, cc, e.line), s.conv(ta, ca, t, e.line), s.conv(tb, cb, t, e.line))

    def x_bin(s, e, want):
        op = e.op; L = e.line
        if op in ('and', 'or'):
            ta, ca = s.ex(e.a); tb, cb = s.ex(e.b)
            o = '&&' if op == 'and' else '||'
            return 'b', '(%s%s%s)' % (s.truth(ta, ca, L), o, s.truth(tb, cb, L))
        if op in ('in', 'notin'):
            ta, ca = s.ex(e.a); tb, cb = s.ex(e.b)
            if ta is None or tb is None: return 'b', '0'
            if tb == 's' and ta == 's': c = 's_has(%s,%s)' % (cb, ca)
            elif is_list(tb): c = '%s_has(%s,%s)' % (mg(tb), cb, s.conv(ta, ca, tb[1], L))
            elif is_map(tb):
                if holes(tb): return 'b', '0'
                c = '%s_has(%s,%s)' % (mg(tb), cb, s.conv(ta, ca, tb[1], L))
            else: s.err("'in' needs a list, dictionary or string on the right, got %s" % tn(tb), L)
            return 'b', c if op == 'in' else '(!%s)' % c
        if op == '<<':
            ta, ca = s.ex(e.a)
            if is_list(ta) or (ta is None and e.a.k == 'var'):
                return s.push(e.a, e.b, L)
        if op == '*' and e.a.k == 'list' and len(e.a.items) == 1:
            wel = want[1] if is_list(want) else None
            te, ce = s.ex(e.a.items[0], wel)
            tk, ck = s.ex(e.b)
            if tk not in ('i', 'b', None): s.err('list repeat count must be i, got %s' % tn(tk), L)
            el = wel if (wel is not None and s.fits(te, wel)) else te
            if el is None: return None, '0'
            lt = ('L', el); s.use(lt)
            x = e.a.items[0]
            if x.k in ('int', 'flt', 'bool') and not x.v:
                return lt, '%s_new(%s)' % (mg(lt), ck)
            return lt, '%s_rep(%s,%s)' % (mg(lt), ck, s.conv(te, ce, el, L))
        ta, ca = s.ex(e.a); tb, cb = s.ex(e.b)
        if ta is None or tb is None: return None, '0'
        if op in ('==', '!=', '<', '<=', '>', '>='): return s.cmp(op, ta, ca, tb, cb, L)
        return s.arith(op, ta, ca, tb, cb, L)

    def cmp(s, op, ta, ca, tb, cb, L):
        if ta in NUM and tb in NUM:
            if 'f' in (ta, tb):
                ca = s.conv(ta, ca, 'f', L); cb = s.conv(tb, cb, 'f', L)
            return 'b', '(%s%s%s)' % (ca, op, cb)
        if ta == 's' and tb == 's':
            if op == '==': return 'b', 's_eq(%s,%s)' % (ca, cb)
            if op == '!=': return 'b', '(!s_eq(%s,%s))' % (ca, cb)
            return 'b', '(s_cmp(%s,%s)%s0)' % (ca, cb, op)
        if isinstance(ta, tuple) and isinstance(tb, tuple) and op in ('==', '!='):
            t = jstrict(ta, tb, L, 'comparison')
            c = 'eq_%s(%s,%s)' % (mg(t), ca, cb)
            return 'b', c if op == '==' else '(!%s)' % c
        s.err('cannot compare %s %s %s' % (tn(ta), op, tn(tb)), L)

    def arith(s, op, ta, ca, tb, cb, L):
        if ta in NUM and tb in NUM:
            isf = 'f' in (ta, tb)
            fa = s.conv(ta, ca, 'f', L) if isf else ca
            fb = s.conv(tb, cb, 'f', L) if isf else cb
            if op in ('+', '-', '*'): return ('f' if isf else 'i'), '(%s%s%s)' % (fa, op, fb)
            if op == '/': return 'f', '(%s/%s)' % (s.conv(ta, ca, 'f', L), s.conv(tb, cb, 'f', L))
            if op == '//': return ('f', 'floor(%s/%s)' % (fa, fb)) if isf else ('i', 'idiv(%s,%s)' % (ca, cb))
            if op == '%': return ('f', 'fmodp(%s,%s)' % (fa, fb)) if isf else ('i', 'imod(%s,%s)' % (ca, cb))
            if op == '**':
                if isf: return 'f', 'pow(%s,%s)' % (fa, fb)
                return 'i', 'ipow(%s,%s)' % (ca, cb)
            if op in ('&', '|', '^', '<<', '>>'):
                if isf: s.err("operator %s needs integers" % op, L)
                return 'i', '(%s%s%s)' % (ca, op, cb)
        if op == '+' and ta == 's' and tb == 's': return 's', 's_cat(%s,%s)' % (ca, cb)
        if op == '+' and 's' in (ta, tb):
            s.err('cannot add %s and %s' % (tn(ta), tn(tb)), L, 'use str(x) or "...{x}..."')
        if op == '*' and ta == 's' and tb in ('i', 'b'): return 's', 's_rep(%s,%s)' % (ca, cb)
        if op == '*' and tb == 's' and ta in ('i', 'b'): return 's', 's_rep(%s,%s)' % (cb, ca)
        if op == '+' and is_list(ta) and is_list(tb):
            t = jstrict(ta, tb, L, 'list concatenation'); return t, '%s_cat(%s,%s)' % (mg(t), ca, cb)
        if op == '*' and is_list(ta) and tb in ('i', 'b'): return ta, '%s_mul(%s,%s)' % (mg(ta), ca, cb)
        s.err('operator %s is not defined for %s and %s' % (op, tn(ta), tn(tb)), L)

    def x_idx(s, e, want):
        to, co = s.ex(e.obj)
        if to is None: return None, '0'
        if is_map(to):
            tk, ck = s.ex(e.idx, to[1])
            if holes(to): return to[2], '0'
            return to[2], '(*%s_get(%s,%s))' % (mg(to), co, s.conv(tk, ck, to[1], e.line))
        ti, ci = s.ex(e.idx)
        if ti not in ('i', 'b', None):
            s.err('index must be an integer, got %s' % tn(ti), e.line, 'use int(x) or // for integer division')
        if to == 's': return 's', 's_at(%s,%s,%d)' % (co, ci, e.line)
        if is_list(to):
            if s.safe: return to[1], '(*%s_at(%s,%s,%d))' % (mg(to), co, ci, e.line)
            if e.idx.k == 'int' and e.idx.v < 0 and e.obj.k == 'var':
                return to[1], '%s->d[%s->n+%s]' % (co, co, ci)
            return to[1], '%s->d[%s]' % (co, ci)
        s.err('cannot index %s' % tn(to), e.line)

    def x_slice(s, e, want):
        to, co = s.ex(e.obj)
        a = s.ex(e.a)[1] if e.a else '0'
        b = s.ex(e.b)[1] if e.b else 'INT64_MAX'
        if to is None: return None, '0'
        if to == 's': return 's', 's_sub(%s,%s,%s)' % (co, a, b)
        if is_list(to): return to, '%s_slice(%s,%s,%s)' % (mg(to), co, a, b)
        s.err('cannot slice %s' % tn(to), e.line)

    def x_field(s, e, want):
        if e.obj.k == 'var' and e.obj.name == 'math' and s.var_owner('math') is None:
            c = {'pi': ('f', 'M_PI'), 'e': ('f', 'M_E'), 'inf': ('f', 'INFINITY')}.get(e.name)
            if c: return c
        t, c = s.ex(e.obj)
        if t is None: return None, '0'
        if is_struct(t):
            st, f = s.field_info(e)
            return st['types'][f], '(%s)->m_%s' % (c, f)
        if e.name in ('len', 'length', 'size'):
            return 'i', s.length(t, c, e.line)
        s.err("%s has no field '.%s'" % (tn(t), e.name), e.line, 'did you forget () for a method call?')

    def x_list(s, e, want):
        if not e.items:
            if is_list(want): return want, '%s_new(0)' % mg(want) if not holes(want) else 'NULL'
            return ('L', None), 'NULL'
        ts = [s.ex(x, want[1] if is_list(want) else None) for x in e.items]
        el = None
        for t, _ in ts: el = join(el, t, e.line, 'list elements')
        if is_list(want) and want[1] is not None and s.fits(el, want[1]): el = want[1]
        if el is None: return None, '0'
        lt = ('L', el); s.use(lt)
        return lt, '%s_lit(%d,(%s[]){%s})' % (mg(lt), len(ts), ct(el), ','.join(s.conv(t, c, el, e.line) for t, c in ts))

    def x_map(s, e, want):
        wk, wv = (want[1], want[2]) if is_map(want) else (None, None)
        if not e.items:
            if is_map(want) and not holes(want): return want, '%s_new()' % mg(want)
            return ('M', wk, wv), 'NULL'
        kts = [s.ex(k, wk) for k, _ in e.items]
        vts = [s.ex(v, wv) for _, v in e.items]
        kt = vt = None
        for t, _ in kts: kt = join(kt, t, e.line, 'dictionary keys')
        for t, _ in vts: vt = join(vt, t, e.line, 'dictionary values')
        if wk is not None and s.fits(kt, wk): kt = wk
        if wv is not None and s.fits(vt, wv): vt = wv
        mt = ('M', kt, vt)
        if holes(mt): return mt, 'NULL'
        s.use(mt); n = mg(mt); m = s.t_()
        sets = ''.join('*%s_get(%s,%s)=%s;' % (n, m, s.conv(a, ca, kt, e.line), s.conv(b, cb, vt, e.line))
                       for (a, ca), (b, cb) in zip(kts, vts))
        return mt, '({%s %s=%s_new();%s %s;})' % (n, m, n, sets, m)

    def iter_parts(s, it, v1, v2, L):
        """loop header pieces for `for v1[,v2] in it`: (open, assigns, close)"""
        if it.k == 'mcall' and it.name == 'items' and not it.args: it = it.obj
        if it.k == 'call' and it.name == 'enumerate' and len(it.args) == 1 and 'enumerate' not in s.fns:
            it = it.args[0]
        ti, ci = s.ex(it)
        if ti is None:
            s.setvar(v1, None, L)
            return None
        a = s.t_(); k = s.t_()
        if ti == 's':  # iterate UTF-8 characters
            if v2: s.setvar(v1, 'i', L); s.setvar(v2, 's', L)
            else: s.setvar(v1, 's', L)
            w = s.t_(); cnt = s.t_()
            op = '{ S %s = %s; I %s = 0, %s = -1; for (I %s = 0; %s < %s.n; %s += %s) { %s = u8w(%s.p+%s,%s.n-%s); %s++;' % (
                a, ci, w, cnt, k, k, a, k, w, w, a, k, a, k, cnt)
            get = '((S){%s.p+%s,%s})' % (a, k, w)
            asg = ('v_%s = %s; v_%s = %s;' % (v1, cnt, v2, get)) if v2 else 'v_%s = %s;' % (v1, get)
            return op, asg, '}}'
        if is_list(ti):
            el = 's' if ti == 's' else ti[1]
            if v2: s.setvar(v1, 'i', L); s.setvar(v2, el, L)
            else: s.setvar(v1, el, L)
            if holes(el): return None
            n_ = '%s.n' % a if ti == 's' else '%s->n' % a
            get = '((S){%s.p+%s,1})' % (a, k) if ti == 's' else '%s->d[%s]' % (a, k)
            op = '{ %s %s = %s; for (I %s = 0; %s < %s; %s++) {' % (ct(ti), a, ci, k, k, n_, k)
            asg = ('v_%s = %s; v_%s = %s;' % (v1, k, v2, get)) if v2 else 'v_%s = %s;' % (v1, get)
            return op, asg, '}}'
        if is_map(ti):
            s.setvar(v1, ti[1], L)
            if v2: s.setvar(v2, ti[2], L)
            if holes(ti): return None
            op = '{ %s %s = %s; for (I %s = 0; %s < %s->c; %s++) { if (!%s->u[%s]) continue;' % (
                ct(ti), a, ci, k, k, a, k, a, k)
            asg = 'v_%s = %s->k[%s];' % (v1, a, k) + (' v_%s = %s->v[%s];' % (v2, a, k) if v2 else '')
            return op, asg, '}}'
        s.err('cannot loop over %s' % tn(ti), L)

    def x_comp(s, e, want):
        L = e.line; it = e.it; r = s.t_()
        if it.k == 'call' and it.name == 'range' and 'range' not in s.fns and len(it.args) in (1, 2) and not e.var2:
            ab = [s.ex(x) for x in it.args]
            lo, hi = ('0LL', ab[0][1]) if len(ab) == 1 else (ab[0][1], ab[1][1])
            s.setvar(e.var, 'i', L); h = s.t_()
            parts = ('{ I %s = %s; for (v_%s = %s; v_%s < %s; v_%s++) {' % (h, hi, e.var, lo, e.var, h, e.var), '', '}}')
        else:
            parts = s.iter_parts(it, e.var, e.var2, L)
        cond = ''
        if e.cond is not None:
            tc, cc = s.ex(e.cond); cond = 'if (%s) ' % s.truth(tc, cc, L)
        te, ce = s.ex(e.elem, want[1] if is_list(want) else None)
        if te is None or parts is None: return (('L', te) if te else None), '0'
        if te == 'v': s.err('the expression in a comprehension has no value', L)
        lt = ('L', te); s.use(lt); n = mg(lt)
        return lt, '({ %s %s = %s_new(0); %s %s %s%s_push(%s,%s); %s %s; })' % (
            n, r, n, parts[0], parts[1], cond, n, r, ce, parts[2], r)

    def construct(s, e, want):
        st = s.structs[e.name]; fs = st['fields']
        if len(e.args) > len(fs):
            s.err('%s() takes at most %d argument(s), got %d' % (e.name, len(fs), len(e.args)), e.line,
                  'fields: ' + ' '.join(fs))
        codes = []
        for i, f in enumerate(fs):
            ft = st['types'][f]
            if i < len(e.args):
                ta, ca = s.ex(e.args[i], ft)
                if ta == 'v': s.err('argument has no value', e.line)
                if f not in st['annot'] and not s.final:
                    ft = st['types'][f] = join(ft, ta, e.line, "field '%s' of %s" % (f, e.name))
                elif holes(ft) and ta is not None:
                    ft = st['types'][f] = jstrict(ft, ta, e.line, "field '%s' of %s" % (f, e.name))
                codes.append('0' if holes(ft) or ta is None else s.conv(ta, ca, ft, e.line))
            else:
                codes.append('0' if holes(ft) else ('NULL' if is_struct(ft) else 'dflt_%s()' % mg(ft)))
        return ('S', e.name), '%s_new(%s)' % (mg(('S', e.name)), ','.join(codes))

    def x_mcall(s, e, want):
        if e.obj.k == 'var' and e.obj.name in ('math', 'random', 'time') and s.var_owner(e.obj.name) is None:
            return s.x_call(N('call', e.line, name=e.name, args=e.args), want)
        if e.name == 'join' and e.obj.k in ('str', 'var') and len(e.args) == 1:
            return s.x_call(N('call', e.line, name='join', args=[e.args[0], e.obj]), want)
        return s.x_call(N('call', e.line, name=e.name, args=[e.obj] + e.args), want)

    def x_call(s, e, want):
        if e.name in s.fns: return s.ucall(e)
        if e.name in s.structs: return s.construct(e, want)
        return s.builtin(ALIASES.get(e.name, e.name), e.args, e, want)

    def ucall(s, e):
        f = s.fns[e.name]
        if len(e.args) != len(f.params):
            s.err('%s() takes %d argument(s), got %d' % (e.name, len(f.params), len(e.args)), e.line)
        codes = []
        for (pn, pd), a in zip(f.params, e.args):
            pt = f.locals.get(pn)
            ta, ca = s.ex(a, pt)
            if ta == 'v': s.err('argument has no value', e.line)
            if pd is None and not s.final:
                f.locals[pn] = join(pt, ta, e.line, "parameter '%s' of %s()" % (pn, e.name))
            codes.append(s.conv(ta, ca, f.locals.get(pn), e.line))
        return f.ret, 'f_%s(%s)' % (e.name, ','.join(codes))

    def push(s, lst, x, L):
        tl, cl = s.ex(lst)
        if tl is None and not s.final:
            tx, _ = s.ex(x)
            if tx and lst.k == 'var' and s.vartype(lst.name) is None: pass
            return 'v', '0'
        if not is_list(tl): s.err('push needs a list, got %s' % tn(tl), L)
        tx, cx = s.ex(x, tl[1])
        el = tl[1]
        if el is None or holes(el):
            el = jstrict(el, tx, L, 'list elements') if tx is not None else el
            if el is not None: s.refine(lst, ('L', el), L)
            if holes(el): return 'v', '0'
        lt = ('L', el); s.use(lt)
        return 'v', '%s_push(%s,%s)' % (mg(lt), cl, s.conv(tx, cx, el, L))

    def keyed(s, name, args, L):
        """sort/rsort/sorted/min/max with a key function: sort(a,f)"""
        t, c = s.ex(args[0])
        fn = args[1].name; f = s.fns[fn]
        if len(f.params) != 1: s.err('%s() must take exactly 1 argument to be used as a key' % fn, L)
        if t is None: return (None if name in ('min', 'max', 'sorted') else 'v'), '0'
        if not is_list(t): s.err('%s() needs a list, got %s' % (name, tn(t)), L)
        pn, pd = f.params[0]
        if pd is None and not s.final:
            f.locals[pn] = join(f.locals.get(pn), t[1], L, "parameter '%s' of %s()" % (pn, fn))
        kt = f.ret
        rt = t[1] if name in ('min', 'max') else (t if name == 'sorted' else 'v')
        if kt is None or holes(t): return rt, '0'
        if kt not in SCAL: s.err('key function %s() must return i, f, b or s, not %s' % (fn, tn(kt)), L)
        n_ = mg(t); T = ct(t[1]); K = ct(kt)
        if name in ('min', 'max'):
            a, b, kb, i, k = [s.t_() for _ in range(5)]
            op = '>' if name == 'max' else '<'
            return rt, ('({%s %s=%s; if(!%s->n) die("%s() of empty list",%d); %s %s=%s->d[0]; %s %s=f_%s(%s); '
                        'for(I %s=1;%s<%s->n;%s++){%s %s=f_%s(%s->d[%s]); if(cmp_%s(%s,%s)%s0){%s=%s;%s=%s->d[%s];}} %s;})') % (
                n_, a, c, a, name, L, T, b, a, K, kb, fn, b,
                i, i, a, i, K, k, fn, a, i, kt, k, kb, op, kb, k, b, a, i, b)
        cmpn = 'kcmp_%s_%s%s' % (n_, fn, '_r' if name == 'rsort' else '')
        s.sortfns[cmpn] = (t, fn, kt, name == 'rsort')
        if name == 'sorted':
            r = s.t_()
            return t, '({%s %s=%s_copy(%s); %s_sortby(%s,%s); %s;})' % (n_, r, n_, c, n_, r, cmpn, r)
        return 'v', '%s_sortby(%s,%s)' % (n_, c, cmpn)

    def builtin(s, name, args, e, want):
        L = e.line; n = len(args)

        def need(*ns):
            if n not in ns:
                s.err('%s() takes %s argument(s), got %d' % (name, ' or '.join(map(str, ns)), n), L)

        def a(i, w=None):
            return s.ex(args[i], w)

        def lst(i):
            t, c = a(i)
            if t is not None and not is_list(t):
                s.err('%s() needs a list, got %s' % (name, tn(t)), L)
            return t, c

        def comparable(t):
            if t[1] not in ('i', 'f', 'b', 's'):
                s.err('%s() needs a list of i, f, b or s' % name, L)

        F_ = lambda i: s.conv(*a(i), 'f', L)
        if name not in BUILTINS:
            m = difflib.get_close_matches(name, list(BUILTINS) + list(s.fns), 1)
            s.err("unknown function '%s'" % name, L, "did you mean '%s'?" % m[0] if m else None)
        if name in ('sort', 'rsort', 'sorted', 'min', 'max') and n == 2 and args[1].k == 'var' \
                and args[1].name in s.fns and s.var_owner(args[1].name) is None:
            return s.keyed(name, args, L)
        if name in ('sort', 'rsort', 'sorted') and n == 2:
            s.err('the 2nd argument of %s() must be the name of a function' % name, L,
                  'define one, e.g.  age p=p.age  then  %s(a,age)' % name)
        if name == 'len':
            need(1); t, c = a(0)
            return ('i', s.length(t, c, L)) if t else (None, '0')
        if name == 'abs':
            need(1); t, c = a(0)
            if t == 'f': return 'f', 'fabs(%s)' % c
            return 'i', 'llabs(%s)' % c
        if name in ('min', 'max'):
            if n == 1:
                t, c = lst(0)
                if t is None: return None, '0'
                comparable(t); return t[1], '%s_%s(%s)' % (mg(t), name, c)
            if n < 2: need(2)
            ts = [a(i) for i in range(n)]
            if any(t is None for t, _ in ts): return None, '0'
            t = None
            for x, _ in ts:
                if x not in NUM: s.err('%s() needs numbers, got %s' % (name, tn(x)), L)
                t = join(t, x, L, name)
            fn = ('i' if t != 'f' else 'f') + name
            c = s.conv(ts[0][0], ts[0][1], t, L)
            for x, cc in ts[1:]: c = '%s(%s,%s)' % (fn, c, s.conv(x, cc, t, L))
            return t, c
        if name == 'sum':
            need(1); t, c = lst(0)
            if t is None: return None, '0'
            if t[1] not in ('i', 'f'): s.err('sum() needs [i] or [f]', L)
            return t[1], '%s_sum(%s)' % (mg(t), c)
        if name in MATH1:
            need(1); return 'f', '%s(%s)' % (name, F_(0))
        if name in MATH2:
            need(2); return 'f', '%s(%s,%s)' % (name, F_(0), F_(1))
        if name in ('floor', 'ceil', 'round', 'trunc'):
            need(1); t, c = a(0)
            if t in ('i', 'b'): return 'i', c
            fn = 'llrint' if name == 'round' else name  # round half to even, like Python
            return 'i', '((I)%s(%s))' % (fn, c)
        if name == 'clamp':
            need(3); ts = [a(i) for i in range(3)]
            t = 'f' if any(x == 'f' for x, _ in ts) else 'i'
            return t, '%sclamp(%s)' % (t, ','.join(s.conv(x, c, t, L) for x, c in ts))
        if name in ('gcd', 'lcm'):
            need(2); return 'i', 'i%s(%s,%s)' % (name, a(0)[1], a(1)[1])
        if name == 'isqrt':
            need(1); return 'i', 'isqrt_(%s)' % a(0)[1]
        if name in ('popcnt', 'clz', 'ctz'):
            need(1); fn = {'popcnt': 'popcount'}.get(name, name)
            return 'i', '((I)__builtin_%sll((unsigned long long)(%s)))' % (fn, a(0)[1])
        if name == 'rand':
            need(0); return 'f', 'r_f()'
        if name == 'rnd':
            need(1, 2)
            if n == 1: return 'i', 'r_i(%s)' % a(0)[1]
            x, y = a(0)[1], a(1)[1]
            return 'i', '({I _a=%s; _a+r_i((%s)-_a+1);})' % (x, y)
        if name == 'seed':
            need(1); return 'v', 'seed(%s)' % a(0)[1]
        if name == 'clock':
            need(0); return 'f', 'clk()'
        if name == 'sleep':
            need(1); return 'v', 'sleep_(%s)' % F_(0)
        if name == 'int':
            need(1); t, c = a(0)
            if t == 's': return 'i', 's_int(%s)' % c
            return 'i', '((I)(%s))' % c
        if name == 'float':
            need(1); t, c = a(0)
            if t == 's': return 'f', 's_float(%s)' % c
            return 'f', '((F)(%s))' % c
        if name == 'str':
            need(1); t, c = a(0)
            return 's', s.tostr(t, c) if t else c
        if name == 'bool':
            need(1); t, c = a(0); return 'b', '(!!%s)' % s.truth(t, c, L)
        if name == 'chr':
            need(1); return 's', 's_chr(%s)' % a(0)[1]
        if name == 'ord':
            need(1); return 'i', 's_ord(%s)' % a(0)[1]
        if name == 'fmt':
            need(2); return 's', 's_fmt(%s,%s)' % (F_(0), a(1)[1])
        if name in ('hex', 'bin'):
            need(1); return 's', 's_%s(%s)' % (name, a(0)[1])
        if name in ('upper', 'lower', 'trim', 'chars') or name.startswith('is') and name in BUILTINS:
            need(1); t, c = a(0)
            if t not in ('s', None): s.err('%s() needs a string, got %s' % (name, tn(t)), L)
            if name == 'chars': return ('L', 's'), 's_chars(%s)' % c
            return ('b' if name.startswith('is') else 's'), 's_%s(%s)' % (name, c)
        if name == 'split':
            need(1, 2)
            if n == 1: return ('L', 's'), 's_split_ws(%s)' % a(0)[1]
            return ('L', 's'), 's_split(%s,%s)' % (a(0)[1], a(1)[1])
        if name == 'join':
            need(1, 2)
            t0, c0 = a(0)
            if n == 1: return 's', 's_join(%s,((S){"",0}))' % c0
            t1, c1 = a(1)
            if t0 == 's' and is_list(t1): c0, c1 = c1, c0
            return 's', 's_join(%s,%s)' % (c0, c1)
        if name in ('starts', 'ends'):
            need(2); return 'b', 's_%s(%s,%s)' % (name, a(0)[1], a(1)[1])
        if name == 'rep':
            need(2); return 's', 's_rep(%s,%s)' % (a(0)[1], a(1)[1])
        if name == 'replace':
            need(3); return 's', 's_repl(%s,%s,%s)' % (a(0)[1], a(1)[1], a(2)[1])
        if name in ('find', 'has', 'count'):
            need(2); t, c = a(0)
            if t is None: return ('b' if name == 'has' else 'i'), '0'
            if t == 's': return ('b' if name == 'has' else 'i'), 's_%s(%s,%s)' % (name, c, a(1)[1])
            if is_map(t) and name == 'has':
                tx, cx = a(1, t[1])
                return 'b', '0' if holes(t) else '%s_has(%s,%s)' % (mg(t), c, s.conv(tx, cx, t[1], L))
            if not is_list(t): s.err('%s() needs a list or string' % name, L)
            tx, cx = a(1, t[1])
            return ('b' if name == 'has' else 'i'), '%s_%s(%s,%s)' % (mg(t), name, c, s.conv(tx, cx, t[1], L))
        if name == 'push':
            need(2); return s.push(args[0], args[1], L)
        if name == 'hpush':
            need(2); t, c = lst(0)
            if t is None: return 'v', '0'
            tx, cx = a(1, t[1])
            if holes(t):
                if tx is not None: s.refine(args[0], ('L', tx), L)
                return 'v', '0'
            comparable(t)
            return 'v', '%s_hpush(%s,%s)' % (mg(t), c, s.conv(tx, cx, t[1], L))
        if name == 'ins':
            need(3); t, c = lst(0)
            if t is None: return 'v', '0'
            tx, cx = a(2, t[1])
            return 'v', '%s_ins(%s,%s,%s)' % (mg(t), c, a(1)[1], s.conv(tx, cx, t[1], L))
        if name in ('pop', 'hpop'):
            need(1, 2); t, c = lst(0)
            if t is None: return None, '0'
            if n == 2: return t[1], '%s_del(%s,%s,%d)' % (mg(t), c, a(1)[1], L)
            if name == 'hpop': comparable(t)
            return t[1], '%s_%s(%s,%d)' % (mg(t), name, c, L)
        if name == 'del':
            need(2); t, c = a(0)
            if t is None: return None, '0'
            if is_map(t):
                tx, cx = a(1, t[1])
                return 'v', '0' if holes(t) else '%s_del(%s,%s)' % (mg(t), c, s.conv(tx, cx, t[1], L))
            if not is_list(t): s.err('del() needs a list or dictionary', L)
            return t[1], '%s_del(%s,%s,%d)' % (mg(t), c, a(1)[1], L)
        if name == 'clear':
            need(1); t, c = a(0)
            if is_map(t): return 'v', '%s_clear(%s)' % (mg(t), c) if not holes(t) else '0'
            return 'v', '((%s)->n=0)' % c
        if name in ('keys', 'vals'):
            need(1); t, c = a(0)
            if t is None: return None, '0'
            if not is_map(t): s.err('%s() needs a dictionary, got %s' % (name, tn(t)), L)
            el = t[1] if name == 'keys' else t[2]
            if holes(t): return ('L', el), '0'
            return ('L', el), '%s_%s(%s)' % (mg(t), name, c)
        if name == 'get':
            need(3); t, c = a(0)
            if t is not None and not is_map(t): s.err('get() needs a dictionary, got %s' % tn(t), L)
            tk, ck = a(1, t[1] if t else None); td, cd = a(2, t[2] if t else None)
            if t is None or holes(t): return td, '0'
            m, k = s.t_(), s.t_(); n_ = mg(t)
            return t[2], '({%s %s=%s; %s %s=%s; %s_has(%s,%s)?*%s_get(%s,%s):%s;})' % (
                n_, m, c, ct(t[1]), k, s.conv(tk, ck, t[1], L), n_, m, k, n_, m, k, s.conv(td, cd, t[2], L))
        if name in ('sort', 'rsort', 'sorted', 'uniq'):
            need(1); t, c = lst(0)
            if t is None: return None, '0'
            comparable(t)
            return ('v' if name in ('sort', 'rsort') else t), '%s_%s(%s)' % (mg(t), name, c)
        if name in ('rev', 'revd'):
            need(1); t, c = a(0)
            if t == 's': return 's', 's_rev(%s)' % c
            if t is None: return None, '0'
            if not is_list(t): s.err('%s() needs a list or string' % name, L)
            return ('v' if name == 'rev' else t), '%s_%s(%s)' % (mg(t), name, c)
        if name in ('copy', 'list'):
            need(1); t, c = a(0)
            if t == 's': return ('L', 's'), 's_chars(%s)' % c
            if t is None: return None, '0'
            if not is_list(t): s.err('%s() needs a list' % name, L)
            return t, '%s_copy(%s)' % (mg(t), c)
        if name == 'fill':
            need(2); t, c = lst(0)
            if t is None: return 'v', '0'
            tx, cx = a(1, t[1]); return 'v', '%s_fill(%s,%s)' % (mg(t), c, s.conv(tx, cx, t[1], L))
        if name == 'ext':
            need(2); t, c = lst(0); t2, c2 = a(1)
            if t is None or t2 is None: return 'v', '0'
            tt = jstrict(t, t2, L, 'ext()')
            if holes(t): s.refine(args[0], tt, L)
            return 'v', '%s_ext(%s,%s)' % (mg(tt), c, c2)
        if name == 'swap':
            need(3); t, c = lst(0)
            if t is None: return 'v', '0'
            return 'v', '%s_swap(%s,%s,%s)' % (mg(t), c, a(1)[1], a(2)[1])
        if name == 'shuffle':
            need(1); t, c = lst(0)
            return 'v', '%s_shuf(%s)' % (mg(t), c) if t else '0'
        if name == 'choice':
            need(1); t, c = lst(0)
            if t is None: return None, '0'
            return t[1], '%s_choice(%s)' % (mg(t), c)
        if name == 'bsearch':
            need(2); t, c = lst(0)
            if t is None: return 'i', '0'
            comparable(t); tx, cx = a(1, t[1])
            return 'i', '%s_bs(%s,%s)' % (mg(t), c, s.conv(tx, cx, t[1], L))
        if name == 'range':
            need(1, 2, 3)
            if n == 1: return ('L', 'i'), 'i_range(0,%s,1)' % a(0)[1]
            st = a(2)[1] if n == 3 else '1'
            return ('L', 'i'), 'i_range(%s,%s,%s)' % (a(0)[1], a(1)[1], st)
        if name == 'input':
            need(0); return 's', 'in_line()'
        if name == 'eof':
            need(0); return 'b', 'g_eof'
        if name == 'lines':
            need(0); return ('L', 's'), 'in_lines()'
        if name == 'ints':
            need(0); return ('L', 'i'), 'in_ints()'
        if name == 'floats':
            need(0); return ('L', 'f'), 'in_floats()'
        if name == 'readf':
            need(1); return 's', 'rd_file(%s)' % a(0)[1]
        if name == 'writef':
            need(2); return 'v', 'wr_file(%s,%s)' % (a(0)[1], a(1)[1])
        if name == 'arg':
            need(1); return 's', 'arg_s(%s)' % a(0)[1]
        if name == 'argc':
            need(0); return 'i', '((I)g_argc)'
        if name == 'exit':
            need(0, 1); return 'v', '(fflush(stdout),exit((int)(%s)))' % (a(0)[1] if n else '0')
        s.err("unknown function '%s'" % name, L)

    # ---------- statements ----------
    def block(s, stmts, tail=False):
        for i, x in enumerate(stmts):
            s.st(x, tail and i == len(stmts) - 1)

    def st(s, x, tail=False):
        getattr(s, 's_' + x.k)(x, tail)

    def s_pass(s, x, tail): pass

    def s_global(s, x, tail): pass

    def s_break(s, x, tail):
        if not s.loops: s.err("'break' outside a loop", x.line)
        s.emit('break;')

    def s_continue(s, x, tail):
        if not s.loops: s.err("'continue' outside a loop", x.line)
        s.emit('continue;')

    def ret_value(s, t, c, L):
        f = s.cur
        if t == 'v': s.err('this expression has no value to return', L)
        if f.ret_decl is None and not s.final:
            f.ret = join(f.ret, t, L, 'return type of %s()' % f.name)
        s.emit('return %s;' % s.conv(t, c, f.ret, L))

    def s_ret(s, x, tail):
        f = s.cur
        if x.e is None:
            s.emit('return 0;' if f is s.main else 'return;')
            return
        if f is s.main: s.err("'return' with a value at top level", x.line, 'use exit(code)')
        t, c = s.ex(x.e, f.ret)
        s.ret_value(t, c, x.line)

    def s_expr(s, x, tail):
        t, c = s.ex(x.e)
        if tail and t not in ('v', None):
            s.ret_value(t, c, x.line)
        else:
            s.emit(c + ';')

    def s_decl(s, x, tail):
        o = s.var_owner(x.name) or s.cur
        old = o.annot.get(x.name)
        if old and old != x.ty: s.err("'%s' declared twice with different types" % x.name, x.line)
        o.annot[x.name] = x.ty; o.locals[x.name] = x.ty
        t, c = s.ex(x.e, x.ty)
        s.emit('v_%s = %s;' % (x.name, s.conv(t, c, x.ty, x.line)))

    def lvalue(s, tgt, L):
        if tgt.k == 'var':
            return s.vartype(tgt.name), 'v_' + tgt.name
        if tgt.k == 'idx':
            to, _ = s.ex(tgt.obj)
            if to == 's': s.err('strings are immutable', L, 'build a new string instead')
            return s.ex(tgt)
        if tgt.k == 'field':
            return s.ex(tgt)
        s.err('cannot assign to this', L)

    def s_assign(s, x, tail):
        L = x.line
        if len(x.lhs) > 1 or len(x.rhs) > 1:
            if len(x.lhs) != len(x.rhs): s.err('%d targets but %d values' % (len(x.lhs), len(x.rhs)), L)
            if x.op != '=': s.err('only = works with several targets', L)
            tmps = []
            s.emit('{'); s.ind += 1
            for tgt, r in zip(x.lhs, x.rhs):
                tt = s.vartype(tgt.name) if tgt.k == 'var' else None
                t, c = s.ex(r, tt)
                if t is None: tmps.append(None); continue
                v = s.t_(); s.emit('%s %s = %s;' % (ct(t), v, c)); tmps.append((t, v))
            for tgt, tv in zip(x.lhs, tmps):
                if tv is None: continue
                s.assign1(tgt, N('raw', L, t=tv[0], c=tv[1]), L)
            s.ind -= 1; s.emit('}')
            return
        tgt, r = x.lhs[0], x.rhs[0]
        if x.op == '=':
            return s.assign1(tgt, r, L)
        bop = x.op[:-1]
        if tgt.k == 'var':
            vt = s.vartype(tgt.name)
            if s.var_owner(tgt.name) is None:
                if s.final: s.undefined(tgt.name, L)
                return
            if vt is None:  # never assigned: starts at 0 / 0.0 / ""
                tr0, _ = s.ex(r)
                if tr0 is None: return
                if is_list(tr0):
                    s.err("list '%s' must be created before use" % tgt.name, L, '%s=[] first' % tgt.name)
                vt = s.setvar(tgt.name, 'i' if tr0 == 'b' else tr0, L)
            if is_list(vt) and bop == '+':
                return s.st(N('expr', L, e=N('call', L, name='ext', args=[tgt, r])))
            tr, cr = s.ex(r, vt if is_list(vt) else None)
            if tr is None: return
            rt, rc = s.arith(bop, vt, 'v_' + tgt.name, tr, cr, L)
            nt = s.setvar(tgt.name, rt, L)
            if bop in ('+', '-', '*', '&', '|', '^', '<<', '>>') and nt == vt and vt in ('i', 'f') and tr in NUM:
                s.emit('v_%s %s= %s;' % (tgt.name, bop, s.conv(tr, cr, nt, L)))
            else:
                s.emit('v_%s = %s;' % (tgt.name, s.conv(rt, rc, nt, L)))
            return
        if tgt.k == 'idx':  # d[k]+=v on a dictionary whose types are still unknown
            to, _ = s.ex(tgt.obj)
            if is_map(to) and holes(to):
                tk, _ = s.ex(tgt.idx); tr0, _ = s.ex(r)
                if tk is None or tr0 is None: return
                nt = ('M', to[1] if to[1] is not None else tk,
                      to[2] if to[2] is not None else ('i' if tr0 == 'b' else tr0))
                s.refine(tgt.obj, nt, L)
                return
        tt, lv = s.lvalue(tgt, L)
        if tt is None: return
        tr, cr = s.ex(r)
        if tr is None: return
        if is_list(tt) and bop == '+':
            return s.st(N('expr', L, e=N('call', L, name='ext', args=[tgt, r])))
        p = s.t_(); rv = s.t_()
        rt, rc = s.arith(bop, tt, '(*%s)' % p, tr, rv, L)
        if tt == 'i' and rt == 'f':
            if tgt.k == 'field':
                st, f = s.field_info(tgt)
                if f not in st['annot'] and not s.final:
                    st['types'][f] = 'f'; return
            s.err('cannot store a float into an int element', L, 'store floats from the start (0.0 instead of 0)')
        s.emit('{ %s %s=%s; %s*%s=&%s; *%s = %s; }' % (ct(tr), rv, cr, ct(tt), p, lv, p, s.conv(rt, rc, tt, L)))

    def assign1(s, tgt, r, L):
        if tgt.k == 'var':
            name = tgt.name
            if name in CONSTS and s.var_owner(name) is None: s.err('cannot assign to constant %s' % name, L)
            if s.cur is s.main and s.litconsts.get(name) is r:  # literal constant -> C static const
                tr, _ = s.ex(r); s.setvar(name, tr, L); return
            vt = s.vartype(name)
            tr, cr = s.ex(r, vt)
            if tr == 'v': s.err('this expression has no value', L)
            if tr is None: return
            nt = s.setvar(name, tr, L)
            if holes(nt) and s.final: return
            s.emit('v_%s = %s;' % (name, s.conv(tr, cr, nt, L)))
            return
        if tgt.k == 'idx':
            to, co = s.ex(tgt.obj)
            if to is None: return
            if to == 's': s.err('strings are immutable', L, 'build a new string instead')
            if is_map(to):
                tk, ck = s.ex(tgt.idx, to[1]); tr, cr = s.ex(r, to[2])
                if tk is None or tr is None: return
                if tr == 'v': s.err('this expression has no value', L)
                if holes(to):
                    vt = tr if to[2] is None else jstrict(to[2], tr, L, 'dictionary values')
                    nt = ('M', to[1] if to[1] is not None else tk, vt)
                    s.refine(tgt.obj, nt, L)
                    if holes(nt): return
                    to = nt
                v = s.t_()  # value first: it may grow the dictionary
                s.emit('{ %s %s = %s; *%s_get(%s,%s) = %s; }' % (
                    ct(to[2]), v, s.conv(tr, cr, to[2], L), mg(to), co, s.conv(tk, ck, to[1], L), v))
                return
            if not is_list(to): s.err('cannot index %s' % tn(to), L)
            tr, cr = s.ex(r, to[1])
            if tr is None: return
            el = to[1]
            if holes(el):
                el = jstrict(el, tr, L, 'list elements'); s.refine(tgt.obj, ('L', el), L)
                if holes(el): return
            _, lv = s.ex(tgt)
            v = s.t_()
            s.emit('{ %s %s = %s; %s = %s; }' % (ct(el), v, s.conv(tr, cr, el, L), lv, v))
            return
        if tgt.k == 'field':
            to, co = s.ex(tgt.obj)
            if to is None: return
            if not is_struct(to): s.err('%s has no fields' % tn(to), L)
            st, f = s.field_info(tgt)
            ft = st['types'][f]
            tr, cr = s.ex(r, ft)
            if tr is None: return
            if tr == 'v': s.err('this expression has no value', L)
            if f not in st['annot'] and not s.final:
                ft = st['types'][f] = join(ft, tr, L, "field '%s'" % f)
            elif holes(ft):
                ft = st['types'][f] = jstrict(ft, tr, L, "field '%s'" % f)
            if holes(ft): return
            v = s.t_()
            s.emit('{ %s %s = %s; (%s)->m_%s = %s; }' % (ct(ft), v, s.conv(tr, cr, ft, L), co, f, v))
            return
        s.err('cannot assign to this', L)

    def s_if(s, x, tail):
        for i, (c, body) in enumerate(x.arms):
            t, cc = s.ex(c)
            s.emit(('if (%s) {' if i == 0 else '} else if (%s) {') % s.truth(t, cc, c.line))
            s.ind += 1; s.block(body, tail); s.ind -= 1
        if x.els:
            s.emit('} else {'); s.ind += 1; s.block(x.els, tail); s.ind -= 1
        s.emit('}')

    def s_while(s, x, tail):
        t, c = s.ex(x.c)
        s.emit('while (%s) {' % s.truth(t, c, x.line))
        s.ind += 1; s.loops += 1; s.block(x.body); s.loops -= 1; s.ind -= 1
        s.emit('}')

    def s_for(s, x, tail):
        L = x.line
        if x.par: s.err('pfor is not in this basic version', L, 'use for')
        s.loops += 1
        if x.kind == 'range':
            ts, cs = s.ex(x.start); te, ce = s.ex(x.end)
            if ts not in NUM + (None,) or te not in NUM + (None,):
                s.err('for range bounds must be numbers', L)
            vt = s.setvar(x.var, join(ts, te, L, 'loop bounds') or 'i', L)
            if x.step is not None:
                tst, cst = s.ex(x.step); inc = '+=%s' % cst
            else:
                inc = '++' if x.op in ('<', '<=') else '--'
            e = s.t_(); v = 'v_' + x.var
            s.emit('{ %s %s = %s;' % (ct(vt), e, s.conv(te, ce, vt, L)))
            s.emit('for (%s = %s; %s %s %s; %s%s) {' % (v, s.conv(ts, cs, vt, L), v, x.op, e, v, inc))
            s.ind += 1; s.block(x.body); s.ind -= 1
            s.emit('}}')
        else:
            parts = s.iter_parts(x.it, x.var, x.var2, L)
            if parts is None:
                if s.final: s.err('cannot infer what this loop iterates over', L, 'give the list a type, e.g. a:[i]=[]')
                n0 = len(s.out); s.block(x.body); del s.out[n0:]  # still learn types from the body
            else:
                s.emit(parts[0]); s.ind += 1; s.emit(parts[1])
                s.block(x.body); s.ind -= 1
                s.emit(parts[2])
        s.loops -= 1

    def s_print(s, x, tail, nl=True):
        for i, a in enumerate(x.args):
            if i and nl: s.emit("p_c(' ');")
            if a.k == 'interp':
                for p in a.parts:
                    if isinstance(p, str):
                        b = p.encode('utf-8')
                        s.emit('p_lit(%s.p,%d);' % (cstr(p), len(b)))
                    else:
                        t, c = s.ex(p)
                        if t is not None: s.emit('p_%s(%s);' % (mg(t), c))
                continue
            t, c = s.ex(a)
            if t == 'v': s.err('cannot print an expression with no value', x.line)
            if t is None: continue
            s.emit('p_%s(%s);' % (mg(t), c))
        if nl: s.emit("p_c('\\n');")

    def s_put(s, x, tail):
        s.s_print(x, tail, nl=False)

    def s_assert(s, x, tail):
        t, c = s.ex(x.c)
        msg = 'assertion failed'
        if x.msg is not None:
            tm, cm = s.ex(x.msg)
            s.emit('if (!(%s)) { fflush(stdout); S _m=%s; fprintf(stderr,"assertion failed (line %d): %%.*s\\n",(int)_m.n,_m.p); exit(1); }'
                   % (s.truth(t, c, x.line), s.tostr(tm, cm), x.line))
        else:
            s.emit('if (!(%s)) die("%s",%d);' % (s.truth(t, c, x.line), msg, x.line))

    # ---------- final assembly ----------
    def struct_funcs(s, name, st):
        T = mg(('S', name)); fs = st['fields']; ty = st['types']
        args = ','.join('%s a_%s' % (ct(ty[f]), f) for f in fs)
        r = ['static %s %s_new(%s){%s r=xm(sizeof(*r));%s return r;}' % (
            T, T, args, T, ''.join('r->m_%s=a_%s;' % (f, f) for f in fs))]
        eqs = '&&'.join('eq_%s(a->m_%s,b->m_%s)' % (mg(ty[f]), f, f) for f in fs)
        r.append('static B eq_%s(%s a,%s b){if(a==b)return 1;if(!a||!b)return 0;return %s;}' % (T, T, T, eqs))
        pr = "p_c(',');p_c(' ');".join('pe_%s(a->m_%s);' % (mg(ty[f]), f) for f in fs)
        r.append('static void p_%s(%s a){if(!a){fputs("null",OUT);return;}fputs("%s(",OUT);%sp_c(\')\');}' % (T, T, name, pr))
        r.append('static void pe_%s(%s a){p_%s(a);}' % (T, T, T))
        r.append('static %s dflt_%s(void){%s r=xm(sizeof(*r));%s return r;}' % (T, T, T, ''.join(
            'r->m_%s=%s;' % (f, 'NULL' if is_struct(ty[f]) else 'dflt_%s()' % mg(ty[f])) for f in fs)))
        r.append('static S str_%s(%s a){char*b=0;size_t n=0;FILE*f=open_memstream(&b,&n);FILE*o=OUT;OUT=f;'
                 'p_%s(a);fclose(f);OUT=o;return (S){b,(I)n};}' % (T, T, T))
        return r

    def assemble(s, bodies):
        out = [CORE]
        for st in s.structs.values():
            for t in st['types'].values(): s.use(t)
        conts = sorted(s.types, key=lambda t: (len(mg(t)), mg(t)))
        decls, cbodies, funcs = [], [], []
        for name, st in sorted(s.structs.items()):
            T = mg(('S', name))
            decls.append('typedef struct %s_s *%s;' % (T, T))
            cbodies.append('struct %s_s {%s};' % (T, ''.join('%s m_%s;' % (ct(st['types'][f]), f) for f in st['fields'])))
            funcs += s.struct_funcs(name, st)
        for t in conts:
            if is_list(t):
                kw = dict(N=mg(t), T=ct(t[1]), E=mg(t[1]))
                decls.append(fill(LIST_DECL, **kw)); cbodies.append(fill(LIST_BODY, **kw))
                txt = LIST_FUNCS
                if t[1] in ('i', 'f'): txt += '@@' + LIST_NUM
                if t[1] in SCAL: txt += '@@' + LIST_CMP
                funcs += split_funcs(fill(txt, **kw))
            else:
                kw = dict(N=mg(t), K=ct(t[1]), V=ct(t[2]), KE=mg(t[1]), VE=mg(t[2]),
                          LK=mg(('L', t[1])), LV=mg(('L', t[2])))
                decls.append(fill(MAP_DECL, **kw)); cbodies.append(fill(MAP_BODY, **kw))
                funcs += split_funcs(fill(MAP_FUNCS, **kw))
        out += decls + cbodies
        for f in funcs: out.append(f[:f.index('{')].rstrip() + ';')
        out += funcs
        out.append(CORE2)
        fl = list(s.fns.values())
        protos = []
        for f in fl:
            ps = ','.join('%s v_%s' % (ct(f.locals[p]), p) for p, _ in f.params) or 'void'
            protos.append('static %s f_%s(%s)' % (ct(f.ret), f.name, ps))
        for p in protos: out.append(p + ';')
        for cmpn, (t, fn, kt, rev) in sorted(s.sortfns.items()):
            T = ct(t[1]); x, y = ('b', 'a') if rev else ('a', 'b')
            out.append('static int %s(const %s*a,const %s*b){return cmp_%s(f_%s(*%s),f_%s(*%s));}' % (
                cmpn, T, T, kt, fn, x, fn, y))
        for name, node in sorted(s.litconsts.items()):
            c = getattr(s, 'x_' + node.k)(node, None)[1]
            if node.k == 'str': c = c[4:-1]
            out.append('static const %s v_%s = %s;' % (ct(s.main.locals[name]), name, c))
        for g in sorted(s.gnames):
            t = s.main.locals.get(g)
            if t is not None and g not in s.litconsts: out.append('static %s v_%s;' % (ct(t), g))
        for f, p, b in zip(fl, protos, bodies):
            out.append(p + ' {')
            pn = {q for q, _ in f.params}
            for n, t in sorted(f.locals.items()):
                if n not in pn and t is not None: out.append('    %s v_%s = {0};' % (ct(t), n))
            out += b
            out.append('}')
        out.append('int main(int argc, char **argv) {')
        out.append('    g_argc = argc; g_argv = argv; OUT = stdout; static char _ob[1<<16]; setvbuf(stdout,_ob,_IOFBF,sizeof _ob);')
        for n, t in sorted(s.main.locals.items()):
            if n not in s.gnames and n not in s.litconsts and t is not None: out.append('    %s v_%s = {0};' % (ct(t), n))
        out += bodies[-1]
        out.append('    fflush(stdout); return 0;')
        out.append('}')
        return '\n'.join(out) + '\n'
