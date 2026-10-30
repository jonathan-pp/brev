#include <stdio.h>
#include <stdlib.h>
int main(int argc, char **argv) {
    long n = atol(argv[1]);
    long best = 0, arg = 0;
    for (long i = 1; i < n; i++) {
        long x = i, s = 0;
        while (x != 1) {
            x = x % 2 == 0 ? x / 2 : 3 * x + 1;
            s++;
        }
        if (s > best) {
            best = s;
            arg = i;
        }
    }
    printf("%ld %ld\n", arg, best);
    return 0;
}
