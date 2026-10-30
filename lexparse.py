# Lexer and parser for Brev.
import re


class CErr(Exception):
    def __init__(s, msg, line=0, col=0, hint=None):
        Exception.__init__(s, msg)
        s.msg = msg; s.line = line; s.col = col; s.hint = hint


KW = {'if', 'elif', 'else', 'while', 'for', 'pfor', 'in', 'return', 'break', 'continue', 'print', 'put',
      'and', 'or', 'not', 'true', 'false', 'type', 'assert', 'pass', 'def', 'fn', 'global'}
OPS = sorted('<<= >>= //= ** -> == != <= >= && || += -= *= /= %= &= |= ^= << >> ++ -- // '
             '+ - * / % < > = ! & | ^ ~ ? : . , ( ) [ ] { } # ;'.split(), key=len, reverse=True)
NUMRE = re.compile(r'0[xX][0-9a-fA-F_]+|0[bB][01_]+|(?:\d[\d_]*)?\.\d[\d_]*(?:[eE][+-]?\d+)?|\d[\d_]*(?:[eE][+-]?\d+)?')
ESC = {'n': '\n', 't': '\t', 'r': '\r', '0': '\0', '\\': '\\', '"': '"', "'": "'", '{': '{', '}': '}'}


class Tok:
    __slots__ = ('k', 'v', 'line', 'col')

    def __init__(s, k, v, line, col):
        s.k = k; s.v = v; s.line = line; s.col = col

    def __repr__(s):
        return '%s:%r@%d' % (s.k, s.v, s.line)


def is_comment(src, i):
    return src[i] == '#' and (i + 1 >= len(src) or src[i + 1] in ' \t\n#!')


def lex(src, line0=1):
    src = src.replace('\r\n', '\n').replace('\r', '\n')
    toks = []; ind = [0]; depth = 0; i = 0; n = len(src); line = line0; bol = True; lstart = 0

    def add(k, v, col):
        toks.append(Tok(k, v, line, col))

    while i < n:
        if bol and depth == 0:
            j = i; w = 0
            while j < n and src[j] in ' \t':
                w += 4 if src[j] == '\t' else 1; j += 1
            if j >= n:
                i = j; break
            if src[j] == '\n':
                i = j + 1; line += 1; lstart = i; continue
            if is_comment(src, j):
                while j < n and src[j] != '\n': j += 1
                i = j; continue
            if w > ind[-1]:
                ind.append(w); add('IND', None, 1)
            else:
                while w < ind[-1]:
                    ind.pop(); add('DED', None, 1)
                if w != ind[-1]:
                    raise CErr('inconsistent indentation', line, w + 1,
                               'indent with the same number of spaces as an enclosing block')
            i = j; bol = False; continue
        c = src[i]
        if c == '\n':
            line += 1; i += 1; lstart = i
            if depth == 0:
                if toks and toks[-1].k not in ('NL',):
                    toks.append(Tok('NL', None, line - 1, 0))
                bol = True
            continue
        if c in ' \t':
            i += 1; continue
        if c == '\\' and i + 1 < n and src[i + 1] == '\n':
            i += 2; line += 1; lstart = i; continue
        if is_comment(src, i):
            while i < n and src[i] != '\n': i += 1
            continue
        col = i - lstart + 1
        stmt_start = not toks or toks[-1].k in ('NL', 'IND', 'DED') or (toks[-1].k == 'OP' and toks[-1].v in (':', ';'))
        if c.isdigit() or (c == '.' and i + 1 < n and src[i + 1].isdigit() and not stmt_start):
            m = NUMRE.match(src, i); t = m.group(0).replace('_', ''); i = m.end()
            if t[:2] in ('0x', '0X', '0b', '0B'):
                add('INT', int(t, 0), col)
            elif '.' in t or ('e' in t.lower() and '-' in t):
                add('FLT', float(t), col)
            elif 'e' in t.lower():
                add('INT', int(float(t)), col)
            else:
                add('INT', int(t), col)
            continue
        if c in 'fF' and i + 1 < n and src[i + 1] in '"\'':  # Python f-string prefix: ignored
            i += 1; continue
        if c.isalpha() or c == '_':
            j = i
            while j < n and (src[j].isalnum() or src[j] == '_'): j += 1
            w = src[i:j]; i = j
            add('KW' if w in KW else 'ID', w, col)
            continue
        if c in '"\'':
            q = c; j = i + 1; parts = []; buf = []
            while True:
                if j >= n or src[j] == '\n':
                    raise CErr('unterminated string', line, col, 'close the string with ' + q)
                ch = src[j]
                if ch == q:
                    j += 1; break
                if ch == '\\':
                    e = src[j + 1] if j + 1 < n else ''
                    buf.append(ESC.get(e, '\\' + e)); j += 2; continue
                if ch == '{':
                    if j + 1 < n and src[j + 1] == '{':
                        buf.append('{'); j += 2; continue
                    k = j + 1; d = 1; inq = None
                    while k < n and src[k] != '\n':
                        ck = src[k]
                        if inq:
                            if ck == inq: inq = None
                        elif ck in '"\'' and ck != q: inq = ck
                        elif ck == '{': d += 1
                        elif ck == '}':
                            d -= 1
                            if d == 0: break
                        k += 1
                    if k >= n or src[k] != '}':
                        raise CErr("unclosed '{' in string", line, j - lstart + 1, 'write {{ for a literal brace')
                    inner = src[j + 1:k]
                    if inner.strip() == '':
                        buf.append('{' + inner + '}')
                    else:
                        if buf: parts.append(('s', ''.join(buf))); buf = []
                        parts.append(('e', inner, line, j - lstart + 2))
                    j = k + 1; continue
                if ch == '}' and j + 1 < n and src[j + 1] == '}':
                    buf.append('}'); j += 2; continue
                buf.append(ch); j += 1
            if buf or not parts: parts.append(('s', ''.join(buf)))
            i = j
            add('STR', parts, col)
            continue
        for op in OPS:
            if src.startswith(op, i):
                if op in '([{': depth += 1
                elif op in ')]}': depth = max(0, depth - 1)
                add('OP', op, col); i += len(op)
                break
        else:
            raise CErr('unexpected character %r' % c, line, col)
    if toks and toks[-1].k != 'NL':
        toks.append(Tok('NL', None, line, 0))
    while len(ind) > 1:
        ind.pop(); toks.append(Tok('DED', None, line, 0))
    toks.append(Tok('EOF', None, line, 0))
    return toks


class N:
    def __init__(s, k, line, **kw):
        s.k = k; s.line = line; s.__dict__.update(kw)

    def __repr__(s):
        return 'N(%s)' % ', '.join('%s=%r' % kv for kv in s.__dict__.items() if kv[0] != 'line')


TYPENAMES = {'i': 'i', 'f': 'f', 'b': 'b', 's': 's', 'int': 'i', 'float': 'f', 'bool': 'b', 'str': 's',
             'string': 's', 'i64': 'i', 'f64': 'f', 'double': 'f', 'long': 'i'}
CMPOPS = ('==', '!=', '<', '<=', '>', '>=')
BINP = {'|': 5, '^': 6, '&': 7, '<<': 8, '>>': 8, '+': 9, '-': 9, '*': 10, '/': 10, '//': 10, '%': 10}
ASSIGN = ('=', '+=', '-=', '*=', '/=', '//=', '%=', '&=', '|=', '^=', '<<=', '>>=')
COMPOUND = ('if', 'while', 'for')


def is_type_start(t):
    if t.k == 'OP' and t.v in ('[', '{'): return True
    return t.k == 'ID' and (t.v in TYPENAMES or t.v[0].isupper())


class Parser:
    def __init__(s, toks):
        s.t = toks; s.p = 0

    def peek(s, k=0):
        return s.t[min(s.p + k, len(s.t) - 1)]

    def next(s):
        t = s.t[s.p]; s.p += 1; return t

    def at(s, v, k=0):
        t = s.peek(k); return t.k in ('OP', 'KW') and t.v == v

    def accept(s, v):
        if s.at(v): return s.next()
        return None

    def expect(s, v, what=None):
        t = s.peek()
        if not s.at(v):
            raise CErr("expected '%s'%s, got %s" % (v, ' ' + what if what else '', s.desc(t)), t.line, t.col)
        return s.next()

    def desc(s, t):
        if t.k == 'NL': return 'end of line'
        if t.k == 'EOF': return 'end of file'
        if t.k == 'IND': return 'unexpected indentation'
        if t.k == 'DED': return 'end of block'
        if t.k == 'STR': return 'a string'
        return repr(t.v)

    def ident(s):
        t = s.peek()
        if t.k != 'ID':
            raise CErr('expected a name, got %s' % s.desc(t), t.line, t.col)
        return s.next().v

    def end_stmt(s):
        t = s.peek()
        if t.k == 'NL': s.next(); return
        if t.k in ('DED', 'EOF'): return
        raise CErr('unexpected %s; expected end of statement' % s.desc(t), t.line, t.col,
                   'one statement per line, or separate statements with ;')

    # ---------- program ----------
    def program(s):
        structs = []; funcs = []; main = []
        while s.peek().k != 'EOF':
            t = s.peek()
            if t.k == 'NL': s.next(); continue
            if t.k in ('IND', 'DED'):
                raise CErr('unexpected indentation', t.line, t.col)
            if s.at('type'):
                structs.append(s.pstruct()); continue
            f = s.try_func()
            if f: funcs.append(f); continue
            main.extend(s.stmt_line())
        return structs, funcs, main

    def ptype(s):
        t = s.next()
        if t.k == 'OP' and t.v == '[':
            e = s.ptype(); s.expect(']'); return ('L', e)
        if t.k == 'OP' and t.v == '{':
            k = s.ptype(); s.expect(':'); v = s.ptype(); s.expect('}'); return ('M', k, v)
        if t.k == 'ID':
            if t.v in TYPENAMES: return TYPENAMES[t.v]
            return ('S', t.v)
        raise CErr('expected a type (i f b s [T] {K:V} or a type name), got %s' % s.desc(t), t.line, t.col)

    def pfield(s):
        name = s.ident(); ty = None
        if s.accept(':'): ty = s.ptype()
        return (name, ty)

    def pstruct(s):
        line = s.next().line
        name = s.ident()
        fields = []
        close = None
        if s.accept('('): close = ')'
        elif s.accept('{'): close = '}'
        elif s.accept(':'): pass
        if close:
            while not s.accept(close):
                fields.append(s.pfield()); s.accept(',')
            s.end_stmt()
        elif s.peek().k == 'NL' and s.peek(1).k == 'IND':
            s.next(); s.next()
            while not (s.peek().k in ('DED', 'EOF')):
                if s.peek().k == 'NL': s.next(); continue
                fields.append(s.pfield()); s.accept(','); s.accept(';')
            s.accept_k('DED')
        else:
            while s.peek().k == 'ID':
                fields.append(s.pfield()); s.accept(',')
            s.end_stmt()
        if not fields:
            raise CErr("type %s has no fields" % name, line, 1, 'example: type P x:f y:f')
        return N('struct', line, name=name, fields=fields)

    def accept_k(s, k):
        if s.peek().k == k: return s.next()
        return None

    def try_func(s):
        p0 = s.p
        try:
            h = s.header()
        except CErr:
            h = None
        if h is None:
            s.p = p0; return None
        name, params, ret, kind, line = h
        if kind == 'block':
            s.next(); body = s.indented()
        elif kind == 'expr':
            s.next(); e = s.expr(); s.end_stmt(); body = [N('ret', e.line, e=e)]
        else:
            s.next()
            if s.peek().k == 'NL':
                s.next(); body = s.indented()
            else:
                body = s.inline()
        return N('fn', line, name=name, params=params, ret=ret, body=body)

    def header(s):
        explicit = bool(s.accept('def') or s.accept('fn'))
        t = s.peek()
        if t.k != 'ID': return None
        s.next(); name = t.v; params = []; paren = False

        def param():
            pt = s.next(); ty = None
            if s.at(':') and is_type_start(s.peek(1)):
                s.next(); ty = s.ptype()
            params.append((pt.v, ty))

        if s.at('('):
            paren = True; s.next()
            while not s.accept(')'):
                if s.peek().k != 'ID': return None
                param()
                if not s.accept(','):
                    if not s.at(')'): return None
        else:
            while s.peek().k == 'ID':
                param()
        ret = None
        if s.accept('->'): ret = s.ptype()
        nt = s.peek(); short = explicit or paren or params
        if nt.k == 'NL' and s.peek(1).k == 'IND': return (name, params, ret, 'block', t.line)
        if s.at('=') and short: return (name, params, ret, 'expr', t.line)
        if s.at(':') and short: return (name, params, ret, 'colon', t.line)
        return None

    # ---------- statements ----------
    def indented(s):
        t = s.peek()
        if not s.accept_k('IND'):
            raise CErr('expected an indented block', t.line, t.col)
        out = []
        while True:
            t = s.peek()
            if t.k == 'DED': s.next(); break
            if t.k == 'EOF': break
            if t.k == 'NL': s.next(); continue
            if t.k == 'IND': raise CErr('unexpected indentation', t.line, t.col)
            out.extend(s.stmt_line())
        return out

    def inline(s):
        out = [s.stmt()]
        if out[-1].k in COMPOUND: return out  # nested if/for/while already ended the line
        while s.accept(';'):
            if s.peek().k in ('NL', 'EOF', 'DED'): break
            out.append(s.stmt())
            if out[-1].k in COMPOUND: return out
        s.end_stmt()
        return out

    def body(s):
        if s.accept(':'):
            if s.peek().k == 'NL':
                s.next(); return s.indented()
            return s.inline()
        if s.peek().k == 'NL':
            s.next(); return s.indented()
        t = s.peek()
        raise CErr("expected ':' or a new line before the block, got %s" % s.desc(t), t.line, t.col)

    def stmt_line(s):
        st = s.stmt()
        if st.k in COMPOUND: return [st]
        out = [st]
        while s.accept(';'):
            if s.peek().k in ('NL', 'EOF', 'DED'): break
            out.append(s.stmt())
        s.end_stmt()
        return out

    def stmt(s):
        t = s.peek(); L = t.line
        if t.k == 'OP' and t.v == '.':  # .x,y  = print
            s.next(); args = []
            if s.peek().k not in ('NL', 'DED', 'EOF') and not s.at(';'):
                args.append(s.expr())
                while s.accept(','): args.append(s.expr())
            return N('print', L, args=args)
        if t.k == 'KW':
            v = t.v
            if v == 'if':
                s.next(); arms = []
                c = s.expr(); arms.append((c, s.body()))
                els = None
                while True:
                    if s.at('elif') or (s.at('else') and s.at('if', 1)):
                        if s.next().v == 'else': s.next()
                        c = s.expr(); arms.append((c, s.body()))
                    elif s.accept('else'):
                        els = s.body(); break
                    else:
                        break
                return N('if', L, arms=arms, els=els)
            if v == 'while':
                s.next(); c = s.expr(); return N('while', L, c=c, body=s.body())
            if v in ('for', 'pfor'):
                return s.pfor()
            if v == 'return':
                s.next()
                e = None if s.peek().k in ('NL', 'DED', 'EOF') or s.at(';') else s.expr()
                return N('ret', L, e=e)
            if v in ('break', 'continue', 'pass'):
                s.next(); return N(v, L)
            if v == 'global':
                s.next(); names = [s.ident()]
                while s.accept(','): names.append(s.ident())
                return N('global', L, names=names)
            if v in ('print', 'put'):
                s.next(); args = []
                if s.at('('):
                    p0 = s.p
                    try:
                        s.next(); a = []
                        while not s.accept(')'):
                            a.append(s.expr())
                            if not s.accept(','):
                                s.expect(')'); break
                        if s.peek().k in ('NL', 'DED', 'EOF') or s.at(';'):
                            return N(v, L, args=a)
                    except CErr:
                        pass
                    s.p = p0
                if s.peek().k not in ('NL', 'DED', 'EOF') and not s.at(';'):
                    args.append(s.expr())
                    while s.accept(','): args.append(s.expr())
                return N(v, L, args=args)
            if v == 'assert':
                s.next(); c = s.expr(); msg = s.expr() if s.accept(',') else None
                return N('assert', L, c=c, msg=msg)
            if v in ('def', 'fn', 'type'):
                raise CErr("functions and types must be defined at top level (no indentation)", L, t.col)
        # typed declaration  x:T = e
        if t.k == 'ID' and s.at(':', 1) and is_type_start(s.peek(2)):
            s.next(); s.next(); ty = s.ptype(); s.expect('=', 'after the type'); e = s.expr()
            return N('decl', L, name=t.v, ty=ty, e=e)
        lhs = [s.expr()]
        while s.accept(','): lhs.append(s.expr())
        nt = s.peek()
        if nt.k == 'OP' and nt.v in ASSIGN:
            op = s.next().v
            rhs = [s.expr()]
            while s.accept(','): rhs.append(s.expr())
            for x in lhs:
                if x.k not in ('var', 'idx', 'field'):
                    raise CErr('cannot assign to this expression', x.line, 0)
            return N('assign', L, lhs=lhs, op=op, rhs=rhs)
        if nt.k == 'OP' and nt.v in ('++', '--'):
            s.next()
            if lhs[0].k not in ('var', 'idx', 'field'):
                raise CErr('cannot increment this expression', L, 0)
            return N('assign', L, lhs=lhs, op=nt.v[0] + '=', rhs=[N('int', L, v=1)])
        if len(lhs) > 1:
            raise CErr("expected '=' after a list of targets", nt.line, nt.col)
        return N('expr', L, e=lhs[0])

    def pfor(s):
        t = s.next(); L = t.line; par = t.v == 'pfor'
        s.accept('(')
        v = s.ident(); v2 = None
        if s.accept(','): v2 = s.ident()
        node = None
        if v2 is None and (s.at('<') or s.at('<=')):
            op = s.next().v; end = s.expr()
            node = N('range', L, var=v, start=N('int', L, v=0), op=op, end=end, step=None)
        elif v2 is None and s.accept('='):
            start = s.bin(5)
            ot = s.next()
            if ot.v not in ('<', '<=', '>', '>='):
                raise CErr('expected < <= > or >= in for range, got %s' % s.desc(ot), ot.line, ot.col,
                           'for i=0<n  /  for i=n-1>=0')
            end = s.bin(5)
            step = s.bin(5) if s.accept(',') else None
            node = N('range', L, var=v, start=start, op=ot.v, end=end, step=step)
        else:
            s.expect('in', 'in for loop')
            it = s.orx()
            if it.k == 'call' and it.name == 'range' and v2 is None:
                a = it.args
                if len(a) == 1: node = N('range', L, var=v, start=N('int', L, v=0), op='<', end=a[0], step=None)
                elif len(a) == 2: node = N('range', L, var=v, start=a[0], op='<', end=a[1], step=None)
                elif len(a) == 3:
                    st = a[2]
                    neg = (st.k == 'int' and st.v < 0)
                    if st.k != 'int':
                        raise CErr('range step must be a number literal', L, 0, 'use a while loop for a variable step')
                    node = N('range', L, var=v, start=a[0], op='>' if neg else '<', end=a[1], step=st)
                else:
                    raise CErr('range() takes 1 to 3 arguments', L, 0)
            else:
                node = N('forin', L, var=v, var2=v2, it=it)
        s.accept(')')
        node.body = s.body(); node.par = par
        if par and node.k != 'range':
            raise CErr('pfor only works on numeric ranges', L, 0, 'pfor i<n')
        node.k = 'for' if node.k == 'range' else 'forin'
        node.kind = 'range' if node.k == 'for' else 'in'
        node.k = 'for'
        return node

    # ---------- expressions ----------
    def expr(s):
        c = s.orx()
        if s.accept('?'):
            a = s.expr(); s.expect(':', 'in ?: expression'); b = s.expr()
            return N('tern', c.line, c=c, a=a, b=b)
        if s.at('if') and s.peek().line == c.line and s.allow_pyif():
            s.next(); cond = s.orx(); s.expect('else', "in 'a if c else b'"); b = s.expr()
            return N('tern', c.line, c=cond, a=c, b=b)
        return c

    def allow_pyif(s):
        return True

    def orx(s):
        a = s.andx()
        while s.at('or') or s.at('||'):
            t = s.next(); b = s.andx(); a = N('bin', t.line, op='or', a=a, b=b)
        return a

    def andx(s):
        a = s.notx()
        while s.at('and') or s.at('&&'):
            t = s.next(); b = s.notx(); a = N('bin', t.line, op='and', a=a, b=b)
        return a

    def notx(s):
        if s.at('not'):
            t = s.next(); return N('un', t.line, op='!', e=s.notx())
        return s.cmpx()

    def cmpx(s):
        left = s.bin(5); items = []
        while True:
            t = s.peek()
            if t.k == 'OP' and t.v in CMPOPS:
                s.next(); op = t.v
            elif s.at('in'):
                s.next(); op = 'in'
            elif s.at('not') and s.at('in', 1):
                s.next(); s.next(); op = 'notin'
            else:
                break
            r = s.bin(5); items.append(N('bin', t.line, op=op, a=left, b=r)); left = r
        if not items: return left
        e = items[0]
        for x in items[1:]: e = N('bin', x.line, op='and', a=e, b=x)
        return e

    def bin(s, minp):
        left = s.unary()
        while True:
            t = s.peek()
            p = BINP.get(t.v) if t.k == 'OP' else None
            if p is None or p < minp: return left
            s.next(); right = s.bin(p + 1)
            left = N('bin', t.line, op=t.v, a=left, b=right)

    def unary(s):
        t = s.peek()
        if t.k == 'OP' and t.v in ('-', '+', '!', '~', '#'):
            s.next(); e = s.unary()
            if t.v == '-' and e.k in ('int', 'flt'):
                e.v = -e.v; return e
            if t.v == '+': return e
            return N('un', t.line, op=t.v, e=e)
        return s.power()

    def power(s):
        b = s.postfix()
        if s.at('**'):
            t = s.next(); e = s.unary()
            return N('bin', t.line, op='**', a=b, b=e)
        return b

    def args(s, close):
        a = []
        while not s.accept(close):
            a.append(s.expr())
            if not s.accept(','):
                s.expect(close); break
        return a

    def postfix(s):
        e = s.primary()
        while True:
            t = s.peek()
            if t.k != 'OP': break
            if t.v == '(':
                s.next(); a = s.args(')')
                if e.k == 'var': e = N('call', t.line, name=e.name, args=a)
                elif e.k == 'field': e = N('mcall', t.line, obj=e.obj, name=e.name, args=a)
                else: raise CErr('this expression cannot be called', t.line, t.col)
            elif t.v == '[':
                s.next()
                if s.accept(':'):
                    b = None if s.at(']') else s.expr(); s.expect(']')
                    e = N('slice', t.line, obj=e, a=None, b=b)
                else:
                    a = s.expr()
                    if s.accept(':'):
                        b = None if s.at(']') else s.expr(); s.expect(']')
                        e = N('slice', t.line, obj=e, a=a, b=b)
                    else:
                        s.expect(']'); e = N('idx', t.line, obj=e, idx=a)
            elif t.v == '.':
                s.next(); nt = s.peek()
                if nt.k not in ('ID', 'KW'):
                    raise CErr('expected a name after .', nt.line, nt.col)
                s.next(); e = N('field', t.line, obj=e, name=nt.v)
            else:
                break
        return e

    def primary(s):
        t = s.next(); L = t.line
        if t.k == 'INT':
            if t.v > 2 ** 63 - 1: raise CErr('integer literal too large for 64 bits', L, t.col)
            return N('int', L, v=t.v)
        if t.k == 'FLT': return N('flt', L, v=t.v)
        if t.k == 'STR':
            parts = []
            for p in t.v:
                if p[0] == 's': parts.append(p[1])
                else:
                    src = p[1]; fmtd = None
                    m = re.match(r'^(.*?):\.(\d+)f$', src, re.S)
                    if m: src, fmtd = m.group(1), int(m.group(2))
                    sub = Parser(lex(src, p[2]))
                    e = sub.expr()
                    if sub.peek().k not in ('NL', 'EOF'):
                        raise CErr('bad expression inside {} in string', p[2], p[3])
                    if fmtd is not None:
                        e = N('call', L, name='fmt', args=[e, N('int', L, v=fmtd)])
                    parts.append(e)
            if len(parts) == 1 and isinstance(parts[0], str): return N('str', L, v=parts[0])
            return N('interp', L, parts=parts)
        if t.k == 'KW' and t.v in ('true', 'false'): return N('bool', L, v=t.v == 'true')
        if t.k == 'ID':
            if t.v in ('True', 'False'): return N('bool', L, v=t.v == 'True')
            return N('var', L, name=t.v)
        if t.k == 'OP':
            if t.v == '?':  # ? int   ?. float   ?? line   (optional "prompt" after)
                kind = 's' if s.accept('?') else 'f' if s.accept('.') else 'i'
                prompt = s.primary() if s.peek().k == 'STR' else None
                return N('input', L, kind=kind, prompt=prompt)
            if t.v == '(':
                e = s.expr(); s.expect(')'); return e
            if t.v == '[':
                if s.accept(']'): return N('list', L, items=[])
                first = s.expr()
                if s.at('for'):
                    s.next(); v = s.ident(); v2 = None
                    if s.accept(','): v2 = s.ident()
                    s.expect('in', 'in comprehension'); it = s.orx()
                    cond = s.orx() if s.accept('if') else None
                    s.expect(']')
                    return N('comp', L, elem=first, var=v, var2=v2, it=it, cond=cond)
                items = [first]
                while s.accept(','):
                    if s.at(']'): break
                    items.append(s.expr())
                s.expect(']')
                return N('list', L, items=items)
            if t.v == '{':
                if s.accept('}'): return N('map', L, items=[])
                items = []
                while True:
                    k = s.expr(); s.expect(':', 'in map literal'); v = s.expr(); items.append((k, v))
                    if not s.accept(','): break
                    if s.at('}'): break
                s.expect('}')
                return N('map', L, items=items)
        if t.k == 'KW' and t.v == 'print':
            raise CErr('print is a statement, not a function value', L, t.col, 'print a,b')
        raise CErr('unexpected %s' % s.desc(t), L, t.col)


def parse(src):
    return Parser(lex(src)).program()
