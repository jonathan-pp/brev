import sys
n = int(sys.argv[1])
best = 0
arg = 0
for i in range(1, n):
    x = i
    s = 0
    while x != 1:
        x = x // 2 if x % 2 == 0 else 3 * x + 1
        s += 1
    if s > best:
        best = s
        arg = i
print(arg, best)
