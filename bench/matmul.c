#include <stdio.h>
#include <stdlib.h>
int main(int argc, char **argv) {
    long n = atol(argv[1]);
    double *a = calloc(n * n, sizeof(double));
    double *b = calloc(n * n, sizeof(double));
    double *c = calloc(n * n, sizeof(double));
    for (long i = 0; i < n * n; i++) {
        a[i] = i % 7 * 0.5;
        b[i] = i % 5 * 0.25;
    }
    for (long i = 0; i < n; i++)
        for (long k = 0; k < n; k++) {
            double x = a[i * n + k];
            for (long j = 0; j < n; j++) c[i * n + j] += x * b[k * n + j];
        }
    double s = 0;
    for (long i = 0; i < n * n; i++) s += c[i];
    printf("%.1f\n", s);
    return 0;
}
