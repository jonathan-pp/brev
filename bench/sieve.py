import sys
n = int(sys.argv[1])
p = [True] * n
c = 0
for i in range(2, n):
    if p[i]:
        c += 1
        for j in range(i*i, n, i):
            p[j] = False
print(c)
