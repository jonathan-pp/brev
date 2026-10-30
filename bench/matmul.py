import sys
n = int(sys.argv[1])
a = [0.0] * (n * n)
b = [0.0] * (n * n)
c = [0.0] * (n * n)
for i in range(n * n):
    a[i] = i % 7 * 0.5
    b[i] = i % 5 * 0.25
for i in range(n):
    for k in range(n):
        x = a[i * n + k]
        for j in range(n):
            c[i * n + j] += x * b[k * n + j]
print(sum(c))
