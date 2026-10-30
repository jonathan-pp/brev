# C runtime and per-type templates for the Brev compiler.

CORE = r'''
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <math.h>
#include <time.h>
#include <ctype.h>
#include <unistd.h>
typedef int64_t I; typedef double F; typedef bool B;
typedef struct { const char *p; I n; } S;
static FILE *OUT;
static int g_argc; static char **g_argv; static int g_eof;
static void die(const char *m, I line){ fflush(stdout); if(line) fprintf(stderr,"runtime error (line %lld): %s\n",(long long)line,m); else fprintf(stderr,"runtime error: %s\n",m); exit(1); }
static void die_idx(I i, I n, I line){ char b[96]; snprintf(b,96,"index %lld out of range (length %lld)",(long long)i,(long long)n); die(b,line); }
static void *xm(size_t n){ void *p=malloc(n?n:1); if(!p) die("out of memory",0); return p; }
static void *xc(size_t n){ void *p=calloc(n?n:1,1); if(!p) die("out of memory",0); return p; }
static void *xr(void *q,size_t n){ void *p=realloc(q,n?n:1); if(!p) die("out of memory",0); return p; }
static inline I imin(I a,I b){return a<b?a:b;}
static inline I imax(I a,I b){return a>b?a:b;}
static inline I iclamp(I x,I a,I b){return x<a?a:x>b?b:x;}
static inline F fclamp(F x,F a,F b){return x<a?a:x>b?b:x;}
static inline I idiv(I a,I b){if(__builtin_expect(b==0,0))die("division by zero",0);I q=a/b; if((a%b!=0)&&((a<0)!=(b<0))) q--; return q;}
static inline I imod(I a,I b){if(__builtin_expect(b==0,0))die("division by zero",0);I r=a%b; if(r!=0&&((r<0)!=(b<0))) r+=b; return r;}
static inline F fmodp(F a,F b){F r=fmod(a,b); if(r!=0&&((r<0)!=(b<0))) r+=b; return r;}
static inline I ipow(I b,I e){I r=1; if(e<0) return 0; while(e){ if(e&1) r*=b; b*=b; e>>=1;} return r;}
static inline I igcd(I a,I b){ if(a<0)a=-a; if(b<0)b=-b; while(b){I t=a%b;a=b;b=t;} return a;}
static inline I ilcm(I a,I b){ return (a&&b) ? a/igcd(a,b)*b : 0; }
static inline I isqrt_(I n){ if(n<=0) return 0; I r=(I)sqrt((double)n); while(r*r>n) r--; while((r+1)*(r+1)<=n) r++; return r; }
static uint64_t rs_[4]={0x9E3779B97F4A7C15ULL,0xBF58476D1CE4E5B9ULL,0x94D049BB133111EBULL,0x2545F4914F6CDD1DULL};
static inline uint64_t rotl_(uint64_t x,int k){return (x<<k)|(x>>(64-k));}
static inline uint64_t rn(void){uint64_t*s=rs_;uint64_t r=rotl_(s[1]*5,7)*9,t=s[1]<<17;s[2]^=s[0];s[3]^=s[1];s[1]^=s[2];s[0]^=s[3];s[2]^=t;s[3]=rotl_(s[3],45);return r;}
static void seed(I x){uint64_t z=(uint64_t)x; for(int i=0;i<4;i++){z+=0x9E3779B97F4A7C15ULL;uint64_t y=z;y=(y^(y>>30))*0xBF58476D1CE4E5B9ULL;y=(y^(y>>27))*0x94D049BB133111EBULL;rs_[i]=y^(y>>31);}}
static inline F r_f(void){return (rn()>>11)*0x1.0p-53;}
static inline I r_i(I n){ if(n<=0) die("rnd(n): n must be > 0",0); return (I)(((unsigned __int128)rn()*(uint64_t)n)>>64);}
static F clk(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
static void sleep_(F s){ if(s<=0) return; struct timespec t; t.tv_sec=(time_t)s; t.tv_nsec=(long)((s-(F)t.tv_sec)*1e9); nanosleep(&t,0); }
/* ---- strings ---- */
static S s_new(I n,char**p){char*b=xm(n+1);b[n]=0;*p=b;return (S){b,n};}
static S s_cat(S a,S b){char*p;S r=s_new(a.n+b.n,&p);memcpy(p,a.p,a.n);memcpy(p+a.n,b.p,b.n);return r;}
static S s_catn(int k,S*v){I n=0;for(int i=0;i<k;i++)n+=v[i].n;char*p;S r=s_new(n,&p);for(int i=0;i<k;i++){memcpy(p,v[i].p,v[i].n);p+=v[i].n;}return r;}
static inline B s_eq(S a,S b){return a.n==b.n&&(a.p==b.p||!memcmp(a.p,b.p,a.n));}
static inline int s_cmp(S a,S b){I m=a.n<b.n?a.n:b.n;int c=m?memcmp(a.p,b.p,m):0;if(c)return c<0?-1:1;return (a.n>b.n)-(a.n<b.n);}
static S s_dup(const char*c,I n){char*p;S r=s_new(n,&p);memcpy(p,c,n);return r;}
static S s_i(I x){char b[24];int n=snprintf(b,24,"%lld",(long long)x);return s_dup(b,n);}
static int fmt_f(char*b,F x){ int n=0; for(int pr=15;pr<=17;pr++){ n=snprintf(b,40,"%.*g",pr,x); if(strtod(b,0)==x) break;} if(!strpbrk(b,".eni")){b[n++]='.';b[n++]='0';b[n]=0;} return n;}
static S s_f(F x){char b[48];int n=fmt_f(b,x);return s_dup(b,n);}
static S s_b(B x){return x?(S){"true",4}:(S){"false",5};}
static S s_fmt(F x,I d){char b[512];int n=snprintf(b,512,"%.*f",(int)d,x);return s_dup(b,n);}
static S s_hex(I x){char b[24];int n=snprintf(b,24,"%llx",(unsigned long long)x);return s_dup(b,n);}
static S s_bin(I x){char b[66];int n=0;uint64_t u=(uint64_t)x;do{b[n++]='0'+(u&1);u>>=1;}while(u);char*p;S r=s_new(n,&p);for(int i=0;i<n;i++)p[i]=b[n-1-i];return r;}
static inline S s_at(S s,I i,I line){ I j=i<0?i+s.n:i; if(j<0||j>=s.n) die_idx(i,s.n,line); return (S){s.p+j,1};}
static S s_sub(S s,I a,I b){I n=s.n;if(a<0)a+=n;if(b<0)b+=n;if(a<0)a=0;if(b>n)b=n;if(b<a)b=a;return (S){s.p+a,b-a};}
static I s_find(S s,S t){ if(t.n==0) return 0; if(t.n>s.n) return -1; const char*r=memmem(s.p,s.n,t.p,t.n); return r? (I)(r-s.p) : -1;}
static B s_has(S s,S t){return s_find(s,t)>=0;}
static I s_count(S s,S t){ if(!t.n) return s.n+1; I c=0,i=0; while(i<=s.n){ const char*r=memmem(s.p+i,s.n-i,t.p,t.n); if(!r)break; c++; i=(I)(r-s.p)+t.n;} return c;}
static S s_upper(S s){char*p;S r=s_new(s.n,&p);for(I i=0;i<s.n;i++)p[i]=toupper((unsigned char)s.p[i]);return r;}
static S s_lower(S s){char*p;S r=s_new(s.n,&p);for(I i=0;i<s.n;i++)p[i]=tolower((unsigned char)s.p[i]);return r;}
static S s_rev(S s){char*p;S r=s_new(s.n,&p);for(I i=0;i<s.n;i++)p[i]=s.p[s.n-1-i];return r;}
static S s_trim(S s){I a=0,b=s.n;while(a<b&&isspace((unsigned char)s.p[a]))a++;while(b>a&&isspace((unsigned char)s.p[b-1]))b--;return (S){s.p+a,b-a};}
static S s_rep(S s,I k){if(k<0)k=0;char*p;S r=s_new(s.n*k,&p);for(I i=0;i<k;i++)memcpy(p+i*s.n,s.p,s.n);return r;}
static B s_starts(S s,S t){return t.n<=s.n&&!memcmp(s.p,t.p,t.n);}
static B s_ends(S s,S t){return t.n<=s.n&&!memcmp(s.p+s.n-t.n,t.p,t.n);}
static S s_repl(S s,S a,S b){ if(!a.n) return s; I c=s_count(s,a); char*p; S r=s_new(s.n+c*(b.n-a.n),&p); I i=0; while(i<s.n){ if(i+a.n<=s.n && !memcmp(s.p+i,a.p,a.n)){memcpy(p,b.p,b.n);p+=b.n;i+=a.n;} else *p++=s.p[i++]; } return r;}
static I s_int(S s){I i=0,r=0;int neg=0;while(i<s.n&&isspace((unsigned char)s.p[i]))i++;if(i<s.n&&(s.p[i]=='-'||s.p[i]=='+')){neg=s.p[i]=='-';i++;}while(i<s.n&&s.p[i]>='0'&&s.p[i]<='9')r=r*10+(s.p[i++]-'0');return neg?-r:r;}
static F s_float(S s){char b[128];I n=s.n<127?s.n:127;memcpy(b,s.p,n);b[n]=0;return strtod(b,0);}
static inline I u8w(const char*p,I rem){unsigned char c=(unsigned char)*p;I w=c<0x80?1:c<0xC0?1:c<0xE0?2:c<0xF0?3:4;return w>rem?rem:w;}
static S s_chr(I c){char*p;S r=s_new(1,&p);p[0]=(char)c;return r;}
static inline I s_ord(S s){return s.n?(unsigned char)s.p[0]:0;}
#define SPRED(nm,fn) static B nm(S s){if(!s.n)return 0;for(I i=0;i<s.n;i++)if(!fn((unsigned char)s.p[i]))return 0;return 1;}
SPRED(s_isdigit,isdigit) SPRED(s_isalpha,isalpha) SPRED(s_isspace,isspace) SPRED(s_isupper,isupper) SPRED(s_islower,islower) SPRED(s_isalnum,isalnum)
/* ---- output ---- */
static inline void p_c(int c){putc_unlocked(c,OUT);}
static void p_i(I x){char b[24];int n=0;uint64_t u=x<0?-(uint64_t)x:(uint64_t)x;if(x<0)p_c('-');do{b[n++]='0'+u%10;u/=10;}while(u);while(n)p_c(b[--n]);}
static void p_f(F x){char b[48];fmt_f(b,x);fputs(b,OUT);}
static void p_b(B x){fputs(x?"true":"false",OUT);}
static void p_s(S s){fwrite(s.p,1,s.n,OUT);}
static void p_lit(const char*s,I n){fwrite(s,1,n,OUT);}
static void pe_i(I x){p_i(x);} static void pe_f(F x){p_f(x);} static void pe_b(B x){p_b(x);}
static void pe_s(S s){p_c('\'');p_s(s);p_c('\'');}
/* ---- scalar generics ---- */
static inline B eq_i(I a,I b){return a==b;} static inline B eq_f(F a,F b){return a==b;}
static inline B eq_b(B a,B b){return a==b;} static inline B eq_s(S a,S b){return s_eq(a,b);}
static inline int cmp_i(I a,I b){return (a>b)-(a<b);} static inline int cmp_f(F a,F b){return (a>b)-(a<b);}
static inline int cmp_b(B a,B b){return (a>b)-(a<b);} static inline int cmp_s(S a,S b){return s_cmp(a,b);}
#define lt_i(a,b) ((a)<(b))
#define lt_f(a,b) ((a)<(b))
#define lt_b(a,b) ((a)<(b))
#define lt_s(a,b) (s_cmp((a),(b))<0)
static inline uint64_t h_i(I x){uint64_t z=(uint64_t)x;z=(z^(z>>30))*0xBF58476D1CE4E5B9ULL;z=(z^(z>>27))*0x94D049BB133111EBULL;return z^(z>>31);}
static inline uint64_t h_b(B x){return h_i(x);}
static inline uint64_t h_f(F x){ if(x==0)x=0; uint64_t u; memcpy(&u,&x,8); return h_i((I)u);}
static uint64_t h_s(S s){uint64_t h=0xcbf29ce484222325ULL;for(I i=0;i<s.n;i++){h^=(unsigned char)s.p[i];h*=0x100000001b3ULL;}return h_i((I)h);}
static inline I dflt_i(void){return 0;} static inline F dflt_f(void){return 0;}
static inline B dflt_b(void){return 0;} static inline S dflt_s(void){return (S){"",0};}
static inline S str_i(I x){return s_i(x);} static inline S str_f(F x){return s_f(x);}
static inline S str_b(B x){return s_b(x);} static inline S str_s(S x){return x;}
/* ---- input ---- */
static S in_line(void){ fflush(stdout); char*l=0;size_t c=0; ssize_t n=getline(&l,&c,stdin); if(n<0){g_eof=1; return (S){"",0};} while(n>0&&(l[n-1]=='\n'||l[n-1]=='\r'))n--; return (S){l,(I)n};}
static I in_int(void){ fflush(stdout); int c=getchar_unlocked(); while(c!=EOF&&!(c=='-'||(c>='0'&&c<='9'))) c=getchar_unlocked(); if(c==EOF){g_eof=1;return 0;} int neg=0; if(c=='-'){neg=1;c=getchar_unlocked();} I v=0; while(c>='0'&&c<='9'){v=v*10+(c-'0');c=getchar_unlocked();} if(c!='\n'&&c!=EOF) ungetc(c,stdin); else if(c=='\n') {} return neg?-v:v; }
static F in_float(void){ fflush(stdout); double x; if(scanf("%lf",&x)!=1){g_eof=1;return 0;} int c=getchar_unlocked(); if(c!='\n'&&c!=EOF) ungetc(c,stdin); return x; }
static S read_all(FILE*f){ size_t c=1<<16,n=0; char*b=xm(c); size_t r; while((r=fread(b+n,1,c-n,f))>0){n+=r; if(n==c){c*=2;b=xr(b,c);}} return (S){b,(I)n};}
static char* cpath(S p){char*b=xm(p.n+1);memcpy(b,p.p,p.n);b[p.n]=0;return b;}
static S rd_file(S path){char*p=cpath(path);FILE*f=fopen(p,"rb");if(!f){char m[600];snprintf(m,600,"cannot open file '%s'",p);die(m,0);}S r=read_all(f);fclose(f);free(p);return r;}
static void wr_file(S path,S s){char*p=cpath(path);FILE*f=fopen(p,"wb");if(!f){char m[600];snprintf(m,600,"cannot write file '%s'",p);die(m,0);}fwrite(s.p,1,s.n,f);fclose(f);free(p);}
static S arg_s(I i){ if(i<0||i>=g_argc) return (S){"",0}; return (S){g_argv[i],(I)strlen(g_argv[i])}; }
'''

# needs Li and Ls
CORE2 = r'''
static Ls s_split_ws(S s){Ls r=Ls_new(0);I i=0;while(i<s.n){while(i<s.n&&isspace((unsigned char)s.p[i]))i++;if(i>=s.n)break;I j=i;while(j<s.n&&!isspace((unsigned char)s.p[j]))j++;Ls_push(r,(S){s.p+i,j-i});i=j;}return r;}
static Ls s_chars(S s){Ls r=Ls_new(0);for(I i=0,w;i<s.n;i+=w){w=u8w(s.p+i,s.n-i);Ls_push(r,(S){s.p+i,w});}return r;}
static Ls s_split(S s,S sep){ if(!sep.n) return s_chars(s); Ls r=Ls_new(0); I i=0; for(;;){ const char*q=memmem(s.p+i,s.n-i,sep.p,sep.n); if(!q){Ls_push(r,(S){s.p+i,s.n-i});break;} Ls_push(r,(S){s.p+i,(I)(q-(s.p+i))}); i=(I)(q-s.p)+sep.n;} return r;}
static S s_join(Ls a,S sep){I n=0;for(I i=0;i<a->n;i++)n+=a->d[i].n+(i?sep.n:0);char*p;S r=s_new(n,&p);for(I i=0;i<a->n;i++){if(i){memcpy(p,sep.p,sep.n);p+=sep.n;}memcpy(p,a->d[i].p,a->d[i].n);p+=a->d[i].n;}return r;}
static Ls in_lines(void){S all=read_all(stdin);Ls r=Ls_new(0);I i=0;while(i<all.n){I j=i;while(j<all.n&&all.p[j]!='\n')j++;I e=j;if(e>i&&all.p[e-1]=='\r')e--;Ls_push(r,(S){all.p+i,e-i});i=j+1;}return r;}
static Li in_ints(void){S all=read_all(stdin);Li r=Li_new(0);const char*p=all.p,*e=all.p+all.n;while(p<e){while(p<e&&!(isdigit((unsigned char)*p)||(*p=='-'&&p+1<e&&isdigit((unsigned char)p[1]))))p++;if(p>=e)break;int neg=0;if(*p=='-'){neg=1;p++;}I v=0;while(p<e&&isdigit((unsigned char)*p))v=v*10+(*p++-'0');Li_push(r,neg?-v:v);}return r;}
static Lf in_floats(void){S all=read_all(stdin);Lf r=Lf_new(0);char*b=cpath(all);char*p=b;for(;;){char*q;while(*p&&!(isdigit((unsigned char)*p)||*p=='-'||*p=='.'||*p=='+'))p++;if(!*p)break;F v=strtod(p,&q);if(q==p){p++;continue;}Lf_push(r,v);p=q;}free(b);return r;}
static Li i_range(I a,I b,I st){ if(st==0) die("range step must not be 0",0); Li r=Li_new(0); if(st>0) for(I i=a;i<b;i+=st) Li_push(r,i); else for(I i=a;i>b;i+=st) Li_push(r,i); return r;}
'''

LIST_DECL = 'typedef struct $N_ *$N;'
LIST_BODY = 'struct $N_ {$T*d;I n,c;};'
LIST_FUNCS = r'''
static $N $N_new(I n){$N a=xm(sizeof(*a));a->n=n;a->c=n<4?4:n;a->d=xc(sizeof($T)*a->c);return a;}
@@
static $N $N_rep(I n,$T x){$N a=$N_new(n);for(I i=0;i<n;i++)a->d[i]=x;return a;}
@@
static $N $N_lit(I n,const $T*x){$N a=$N_new(n);if(n)memcpy(a->d,x,sizeof($T)*n);return a;}
@@
static void $N_grow($N a){a->c=a->c*2+4;a->d=xr(a->d,sizeof($T)*a->c);}
@@
static inline void $N_push($N a,$T x){if(__builtin_expect(a->n>=a->c,0))$N_grow(a);a->d[a->n++]=x;}
@@
static $T $N_pop($N a,I line){if(a->n<=0)die("pop from empty list",line);return a->d[--a->n];}
@@
static inline $T* $N_at($N a,I i,I line){I j=i<0?i+a->n:i;if(j<0||j>=a->n)die_idx(i,a->n,line);return &a->d[j];}
@@
static $N $N_slice($N a,I i,I j){I n=a->n;if(i<0)i+=n;if(j<0)j+=n;if(i<0)i=0;if(j>n)j=n;if(j<i)j=i;return $N_lit(j-i,a->d+i);}
@@
static void $N_ext($N a,$N b){I bn=b->n;while(a->c<a->n+bn)$N_grow(a);memmove(a->d+a->n,b->d,sizeof($T)*bn);a->n+=bn;}
@@
static $N $N_cat($N a,$N b){$N r=$N_lit(a->n,a->d);$N_ext(r,b);return r;}
@@
static $N $N_copy($N a){return $N_lit(a->n,a->d);}
@@
static $N $N_mul($N a,I k){$N r=$N_new(0);for(I j=0;j<k;j++)$N_ext(r,a);return r;}
@@
static void $N_ins($N a,I i,$T x){I n=a->n;if(i<0)i+=n;if(i<0)i=0;if(i>n)i=n;$N_push(a,x);memmove(a->d+i+1,a->d+i,sizeof($T)*(n-i));a->d[i]=x;}
@@
static $T $N_del($N a,I i,I line){if(i<0)i+=a->n;if(i<0||i>=a->n)die_idx(i,a->n,line);$T x=a->d[i];memmove(a->d+i,a->d+i+1,sizeof($T)*(a->n-i-1));a->n--;return x;}
@@
static void $N_rev($N a){for(I i=0,j=a->n-1;i<j;i++,j--){$T t=a->d[i];a->d[i]=a->d[j];a->d[j]=t;}}
@@
static $N $N_revd($N a){$N r=$N_copy(a);$N_rev(r);return r;}
@@
static void $N_msort($T*d,$T*t,I n,int(*cmp)(const $T*,const $T*)){if(n<2)return;if(n<=16){for(I i=1;i<n;i++){$T x=d[i];I j=i;while(j>0&&cmp(&d[j-1],&x)>0){d[j]=d[j-1];j--;}d[j]=x;}return;}I m=n/2;$N_msort(d,t,m,cmp);$N_msort(d+m,t,n-m,cmp);if(cmp(&d[m-1],&d[m])<=0)return;memcpy(t,d,sizeof($T)*m);I i=0,j=m,k=0;while(i<m&&j<n)d[k++]=cmp(&d[j],&t[i])<0?d[j++]:t[i++];while(i<m)d[k++]=t[i++];}
@@
static void $N_sortby($N a,int(*cmp)(const $T*,const $T*)){$T*t=xm(sizeof($T)*(a->n/2+1));$N_msort(a->d,t,a->n,cmp);free(t);}
@@
static void $N_fill($N a,$T x){for(I i=0;i<a->n;i++)a->d[i]=x;}
@@
static void $N_swap($N a,I i,I j){$T t=a->d[i];a->d[i]=a->d[j];a->d[j]=t;}
@@
static B $N_has($N a,$T x){for(I i=0;i<a->n;i++)if(eq_$E(a->d[i],x))return 1;return 0;}
@@
static I $N_find($N a,$T x){for(I i=0;i<a->n;i++)if(eq_$E(a->d[i],x))return i;return -1;}
@@
static I $N_count($N a,$T x){I c=0;for(I i=0;i<a->n;i++)c+=eq_$E(a->d[i],x);return c;}
@@
static void $N_shuf($N a){for(I i=a->n-1;i>0;i--){I j=r_i(i+1);$T t=a->d[i];a->d[i]=a->d[j];a->d[j]=t;}}
@@
static $T $N_choice($N a){if(!a->n)die("choice from empty list",0);return a->d[r_i(a->n)];}
@@
static B eq_$N($N a,$N b){if(a==b)return 1;if(a->n!=b->n)return 0;for(I i=0;i<a->n;i++)if(!eq_$E(a->d[i],b->d[i]))return 0;return 1;}
@@
static void p_$N($N a){p_c('[');for(I i=0;i<a->n;i++){if(i){p_c(',');p_c(' ');}pe_$E(a->d[i]);}p_c(']');}
@@
static void pe_$N($N a){p_$N(a);}
@@
static $N dflt_$N(void){return $N_new(0);}
@@
static S str_$N($N a){char*b=0;size_t n=0;FILE*f=open_memstream(&b,&n);FILE*o=OUT;OUT=f;p_$N(a);fclose(f);OUT=o;return (S){b,(I)n};}
'''
LIST_NUM = r'''
static $T $N_sum($N a){$T s=0;for(I i=0;i<a->n;i++)s+=a->d[i];return s;}
'''
LIST_CMP = r'''
static $T $N_min($N a){if(!a->n)die("min of empty list",0);$T m=a->d[0];for(I i=1;i<a->n;i++)if(lt_$E(a->d[i],m))m=a->d[i];return m;}
@@
static $T $N_max($N a){if(!a->n)die("max of empty list",0);$T m=a->d[0];for(I i=1;i<a->n;i++)if(lt_$E(m,a->d[i]))m=a->d[i];return m;}
@@
static void $N_isort($T*d,I n){for(I i=1;i<n;i++){$T x=d[i];I j=i-1;while(j>=0&&lt_$E(x,d[j])){d[j+1]=d[j];j--;}d[j+1]=x;}}
@@
static void $N_sift($T*d,I s,I n){$T x=d[s];for(;;){I c=2*s+1;if(c>=n)break;if(c+1<n&&lt_$E(d[c],d[c+1]))c++;if(!lt_$E(x,d[c]))break;d[s]=d[c];s=c;}d[s]=x;}
@@
static void $N_hs($T*d,I n){for(I s=n/2-1;s>=0;s--)$N_sift(d,s,n);for(I e=n-1;e>0;e--){$T t=d[0];d[0]=d[e];d[e]=t;$N_sift(d,0,e);}}
@@
static void $N_qs($T*d,I n,int dep){while(n>24){if(dep--<=0){$N_hs(d,n);return;}I m=n/2;$T t;if(lt_$E(d[m],d[0])){t=d[m];d[m]=d[0];d[0]=t;}if(lt_$E(d[n-1],d[m])){t=d[m];d[m]=d[n-1];d[n-1]=t;if(lt_$E(d[m],d[0])){t=d[m];d[m]=d[0];d[0]=t;}}$T p=d[m];I i=-1,j=n;for(;;){do i++;while(lt_$E(d[i],p));do j--;while(lt_$E(p,d[j]));if(i>=j)break;t=d[i];d[i]=d[j];d[j]=t;}I k=j+1;if(k<n-k){$N_qs(d,k,dep);d+=k;n-=k;}else{$N_qs(d+k,n-k,dep);n=k;}}$N_isort(d,n);}
@@
static void $N_sort($N a){int dep=4;for(I n=a->n;n>1;n>>=1)dep+=2;$N_qs(a->d,a->n,dep);}
@@
static void $N_rsort($N a){$N_sort(a);$N_rev(a);}
@@
static $N $N_sorted($N a){$N r=$N_copy(a);$N_sort(r);return r;}
@@
static I $N_bs($N a,$T x){I lo=0,hi=a->n;while(lo<hi){I m=(lo+hi)>>1;if(lt_$E(a->d[m],x))lo=m+1;else hi=m;}return lo;}
@@
static $N $N_uniq($N a){$N r=$N_sorted(a);I k=0;for(I i=0;i<r->n;i++)if(!k||!eq_$E(r->d[k-1],r->d[i]))r->d[k++]=r->d[i];r->n=k;return r;}
@@
static void $N_hpush($N a,$T x){$N_push(a,x);I i=a->n-1;$T*d=a->d;while(i>0){I p=(i-1)/2;if(!lt_$E(x,d[p]))break;d[i]=d[p];i=p;}d[i]=x;}
@@
static $T $N_hpop($N a,I line){if(a->n<=0)die("hpop from empty heap",line);$T*d=a->d;$T top=d[0];$T x=d[--a->n];I n=a->n,i=0;if(n){for(;;){I c=2*i+1;if(c>=n)break;if(c+1<n&&lt_$E(d[c+1],d[c]))c++;if(!lt_$E(d[c],x))break;d[i]=d[c];i=c;}d[i]=x;}return top;}
'''

MAP_DECL = 'typedef struct $N_ *$N;'
# insertion-ordered dict: dense arrays k/v/u (u = live flag, c = dense length) + open-addressing index ix
MAP_BODY = 'struct $N_ {$K*k;$V*v;uint8_t*u;I n,c,cap;I*ix;I hc;};'
MAP_FUNCS = r"""
static $N $N_new(void){$N m=xm(sizeof(*m));m->cap=8;m->c=0;m->n=0;m->k=xm(sizeof($K)*8);m->v=xm(sizeof($V)*8);m->u=xc(8);m->hc=16;m->ix=xc(sizeof(I)*16);return m;}
@@
static I $N_find($N m,$K k){I mask=m->hc-1,h=(I)(h_$KE(k)&(uint64_t)mask);for(;;){I e=m->ix[h];if(!e)return -1;if(e>0&&eq_$KE(m->k[e-1],k))return e-1;h=(h+1)&mask;}}
@@
static void $N_rebuild($N m){I j=0;for(I i=0;i<m->c;i++)if(m->u[i]){m->k[j]=m->k[i];m->v[j]=m->v[i];m->u[j]=1;j++;}for(I i=j;i<m->c;i++)m->u[i]=0;m->c=j;I hc=16;while(hc<4*(j+1))hc*=2;free(m->ix);m->hc=hc;m->ix=xc(sizeof(I)*hc);I mask=hc-1;for(I i=0;i<j;i++){I h=(I)(h_$KE(m->k[i])&(uint64_t)mask);while(m->ix[h])h=(h+1)&mask;m->ix[h]=i+1;}}
@@
static $V* $N_get($N m,$K k){I i=$N_find(m,k);if(i>=0)return &m->v[i];if((m->c+1)*2>m->hc)$N_rebuild(m);if(m->c>=m->cap){m->cap*=2;m->k=xr(m->k,sizeof($K)*m->cap);m->v=xr(m->v,sizeof($V)*m->cap);m->u=xr(m->u,m->cap);}I j=m->c++;m->k[j]=k;m->v[j]=dflt_$VE();m->u[j]=1;m->n++;I mask=m->hc-1,h=(I)(h_$KE(k)&(uint64_t)mask);while(m->ix[h]>0)h=(h+1)&mask;m->ix[h]=j+1;return &m->v[j];}
@@
static B $N_has($N m,$K k){return $N_find(m,k)>=0;}
@@
static void $N_del($N m,$K k){I mask=m->hc-1,h=(I)(h_$KE(k)&(uint64_t)mask);for(;;){I e=m->ix[h];if(!e)return;if(e>0&&eq_$KE(m->k[e-1],k)){m->ix[h]=-1;m->u[e-1]=0;m->n--;return;}h=(h+1)&mask;}}
@@
static void $N_clear($N m){memset(m->ix,0,sizeof(I)*m->hc);m->c=0;m->n=0;}
@@
static $LK $N_keys($N m){$LK r=$LK_new(0);for(I i=0;i<m->c;i++)if(m->u[i])$LK_push(r,m->k[i]);return r;}
@@
static $LV $N_vals($N m){$LV r=$LV_new(0);for(I i=0;i<m->c;i++)if(m->u[i])$LV_push(r,m->v[i]);return r;}
@@
static B eq_$N($N a,$N b){if(a==b)return 1;if(!a||!b||a->n!=b->n)return 0;for(I i=0;i<a->c;i++)if(a->u[i]){I j=$N_find(b,a->k[i]);if(j<0||!eq_$VE(a->v[i],b->v[j]))return 0;}return 1;}
@@
static void p_$N($N m){p_c('{');int f=0;for(I i=0;i<m->c;i++)if(m->u[i]){if(f){p_c(',');p_c(' ');}f=1;pe_$KE(m->k[i]);p_c(':');p_c(' ');pe_$VE(m->v[i]);}p_c('}');}
@@
static void pe_$N($N a){p_$N(a);}
@@
static $N dflt_$N(void){return $N_new();}
@@
static S str_$N($N a){char*b=0;size_t n=0;FILE*f=open_memstream(&b,&n);FILE*o=OUT;OUT=f;p_$N(a);fclose(f);OUT=o;return (S){b,(I)n};}
"""


def fill(tpl, **kw):
    # replace longest placeholders first
    for k in sorted(kw, key=len, reverse=True):
        tpl = tpl.replace('$' + k, kw[k])
    return tpl


def split_funcs(txt):
    return [f.strip() for f in txt.split('@@') if f.strip()]
