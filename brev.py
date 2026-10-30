#!/usr/bin/env python3
"""brev %s - a compact language for LLMs, compiled to optimized C.

usage:
  brev                         interactive mode (REPL)
  brev run FILE.bv [args...]   compile (cached) and run
  brev build FILE.bv [-o OUT]  produce a native executable
  brev c FILE.bv               print the generated C
  brev check FILE.bv           type-check only
  brev test [DIR]              run the test suite (DIR/*.bv vs *.out / *.err)
  brev version
options: --safe (check list indexes), --fast (-ffast-math)
"""
import sys, os, subprocess, hashlib, glob
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from lexparse import CErr, parse
from compiler import Compiler

VERSION = '0.3'
CACHE = os.path.join(os.path.expanduser('~'), '.cache', 'brev')


def fmt_err(path, src, e):
    lines = src.split('\n')
    msg = '%s:%d: error: %s' % (path, e.line, e.msg)
    if 0 < e.line <= len(lines):
        msg += '\n  %d | %s' % (e.line, lines[e.line - 1])
        if e.col:
            msg += '\n  %s | %s^' % (' ' * len(str(e.line)), ' ' * (e.col - 1))
    if e.hint: msg += '\n  hint: ' + e.hint
    return msg


def to_c(src, safe=False):
    structs, funcs, main = parse(src)
    return Compiler(structs, funcs, main, safe=safe).compile()


def cc(csrc, out, fast=False, opt='-O3'):
    flags = [opt, '-march=native', '-w', '-fno-math-errno']
    if fast: flags.append('-ffast-math')
    run = lambda fl: subprocess.run([os.environ.get('CC', 'gcc')] + fl + ['-x', 'c', '-', '-o', out, '-lm'],
                                    input=csrc.encode(), capture_output=True)
    r = run(flags)
    if r.returncode:  # some compilers (e.g. older clang on ARM) reject -march=native
        r = run([f for f in flags if f != '-march=native'])
    if r.returncode:
        raise RuntimeError('internal compiler error (C compilation failed):\n' + r.stderr.decode()[:3000])


def exe_for(csrc, fast=False, opt='-O3'):
    """compile once, reuse the binary while the C code is unchanged"""
    os.makedirs(CACHE, exist_ok=True)
    exe = os.path.join(CACHE, hashlib.sha1((csrc + str(fast) + opt).encode()).hexdigest()[:16])
    if not os.path.exists(exe):
        cc(csrc, exe + '.tmp', fast, opt); os.replace(exe + '.tmp', exe)
    return exe


def crash_msg(code, safe):
    sig = -code
    names = {11: 'segmentation fault', 8: 'arithmetic error', 6: 'abort'}
    hint = '; rerun with --safe to check list indexes' if sig == 11 and not safe else ''
    return 'program crashed (%s)%s' % (names.get(sig, 'signal %d' % sig), hint)


# ---------------------------------------------------------------- test runner
def run_tests(d):
    files = sorted(glob.glob(os.path.join(d, '*.bv')))
    if not files:
        print('no tests in', d); return 1
    ok = 0
    for f in files:
        base = f[:-3]
        src = open(f, encoding='utf-8').read()
        stdin = open(base + '.in', 'rb').read() if os.path.exists(base + '.in') else b''
        args = open(base + '.args').read().split() if os.path.exists(base + '.args') else []
        want_err = open(base + '.err', encoding='utf-8').read().strip() if os.path.exists(base + '.err') else None
        want_out = open(base + '.out', encoding='utf-8').read() if os.path.exists(base + '.out') else None
        problem = None
        try:
            csrc = to_c(src)
            r = subprocess.run([exe_for(csrc)] + args, input=stdin, capture_output=True, timeout=60)
            out, err = r.stdout.decode(), r.stderr.decode()
            if want_err is not None:
                if want_err not in err: problem = 'expected error containing %r, got %r' % (want_err, err.strip())
            elif r.returncode: problem = 'exit code %d: %s' % (r.returncode, err.strip()[:300])
            elif want_out is not None and out != want_out:
                problem = 'output differs:\n--- expected\n%s--- got\n%s' % (want_out, out)
        except CErr as e:
            if want_err is None or want_err not in fmt_err(f, src, e):
                problem = fmt_err(f, src, e)
        except Exception as e:
            problem = str(e)
        name = os.path.basename(f)
        if problem:
            print('FAIL', name); print('   ' + problem.replace('\n', '\n   '))
        else:
            ok += 1; print('ok  ', name)
    print('\n%d/%d tests passed' % (ok, len(files)))
    return 0 if ok == len(files) else 1


# ---------------------------------------------------------------- REPL
def repl():
    print('brev %s - interactive mode. End block headers with ":" (e.g. "fib n:"), blank line to finish.' % VERSION)
    print('Commands: :reset  :code  :quit')
    hist = []; prev = ''
    while True:
        try:
            line = input('>>> ')
        except (EOFError, KeyboardInterrupt):
            print(); return 0
        if not line.strip(): continue
        cmd = line.strip()
        if cmd in (':q', ':quit', 'exit', 'quit'): return 0
        if cmd == ':reset': hist = []; prev = ''; print('(cleared)'); continue
        if cmd == ':code': print('\n'.join(hist)); continue
        chunk = [line]
        if line.rstrip().endswith(':'):
            while True:
                try:
                    l2 = input('... ')
                except (EOFError, KeyboardInterrupt):
                    break
                if not l2.strip(): break
                chunk.append(l2)
        chunk = '\n'.join(chunk)
        tries = [chunk]
        if '\n' not in chunk and not chunk.lstrip().startswith(('.', 'print', 'put')):
            tries.insert(0, 'put "\x01"\n.(' + chunk + ')')  # bare expression: show its value
        for i, c in enumerate(tries):
            src = '\n'.join(hist + [c]) + '\n'
            try:
                csrc = to_c(src)
            except CErr as e:
                if i < len(tries) - 1: continue
                print(fmt_err('<repl>', src, e)); break
            try:
                r = subprocess.run([exe_for(csrc, opt='-O1')], stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
            except Exception as ex:
                print(ex); break
            out = r.stdout.decode()
            keep = out
            if i == 0 and len(tries) == 2 and '\x01' in out:  # value echo is not part of the program
                m = out.rfind('\x01'); keep = out[:m]; out = out[:m] + out[m + 1:]
            sys.stdout.write(out[len(prev):] if out.startswith(prev) else out)
            if r.returncode:
                sys.stdout.write(r.stderr.decode() or crash_msg(r.returncode, False) + '\n')
                break
            hist.append(chunk); prev = keep
            break


def main(argv):
    opts = [a for a in argv if a in ('--safe', '--fast')]
    argv = [a for a in argv if a not in opts]
    safe, fast = '--safe' in opts, '--fast' in opts
    if not argv: return repl()
    cmd = argv[0]
    if cmd in ('version', '--version', '-v'):
        print('brev', VERSION); return 0
    if cmd == 'test':
        return run_tests(argv[1] if len(argv) > 1 else os.path.join(os.path.dirname(os.path.realpath(__file__)), 'tests'))
    if cmd not in ('run', 'build', 'c', 'check') or len(argv) < 2:
        if cmd.endswith('.bv') and os.path.exists(cmd): argv = ['run'] + argv; cmd = 'run'
        else:
            print(__doc__ % VERSION); return 1
    path = argv[1]
    try:
        src = open(path, encoding='utf-8').read()
    except OSError as e:
        print('cannot read %s: %s' % (path, e.strerror), file=sys.stderr); return 1
    try:
        csrc = to_c(src, safe)
    except CErr as e:
        print(fmt_err(path, src, e), file=sys.stderr); return 1
    try:
        if cmd == 'check':
            print('ok'); return 0
        if cmd == 'c':
            sys.stdout.write(csrc); return 0
        if cmd == 'build':
            out = argv[argv.index('-o') + 1] if '-o' in argv else os.path.splitext(path)[0]
            cc(csrc, out, fast); return 0
        exe = exe_for(csrc, fast)
    except RuntimeError as e:
        print(e, file=sys.stderr); return 2
    r = subprocess.run([exe] + argv[2:])
    if r.returncode < 0:
        print('\n' + crash_msg(r.returncode, safe), file=sys.stderr); return 1
    return r.returncode


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
