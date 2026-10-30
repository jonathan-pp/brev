#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc, char **argv) {
    long n = atol(argv[1]);
    char *p = malloc(n);
    memset(p, 1, n);
    long c = 0;
    for (long i = 2; i < n; i++) {
        if (p[i]) {
            c++;
            for (long j = i * i; j < n; j += i) p[j] = 0;
        }
    }
    printf("%ld\n", c);
    return 0;
}
