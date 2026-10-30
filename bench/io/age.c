#include <stdio.h>
#include <string.h>
#define MAJ 18
int main(void) {
    char n[100];
    int a;
    printf("Nom ? ");
    fgets(n, sizeof n, stdin);
    n[strcspn(n, "\n")] = 0;
    printf("Age ? ");
    scanf("%d", &a);
    printf("%s est %s\n", n, a >= MAJ ? "majeur" : "mineur");
    return 0;
}
