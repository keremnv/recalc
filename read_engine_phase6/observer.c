#define _XOPEN_SOURCE 700
#define _POSIX_C_SOURCE 200809L
/* Phase-6 offline observer. No spreadsheet semantics or Python embedding. */
#include <errno.h>
#include <fcntl.h>
#include <ftw.h>
#include <limits.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

typedef struct { char *rel; unsigned char *bytes; size_t size; } File;
typedef struct { File *files; size_t count, cap; } Snapshot;
static const char *scan_root;
static Snapshot *scan_target;
static int scan_error;
static size_t scan_root_len;

static uint64_t ns(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t)) return 0;
    return (uint64_t)t.tv_sec * 1000000000ULL + (uint64_t)t.tv_nsec;
}
static void die(const char *message) { fprintf(stderr, "phase6 observer: %s: %s\n", message, strerror(errno)); exit(125); }
static char *join(const char *a, const char *b) {
    size_t n = strlen(a) + strlen(b) + 2;
    char *s = malloc(n);
    if (!s) die("malloc path");
    snprintf(s, n, "%s/%s", a, b);
    return s;
}
static void json_string(FILE *f, const char *s) {
    fputc('"', f);
    for (const unsigned char *p = (const unsigned char *)s; *p; ++p) {
        if (*p == '"' || *p == '\\') { fputc('\\', f); fputc(*p, f); }
        else if (*p < 32) fprintf(f, "\\u%04x", *p);
        else fputc(*p, f);
    }
    fputc('"', f);
}
static void *read_bytes(const char *path, size_t *size) {
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) return NULL;
    struct stat st;
    if (fstat(fd, &st) || st.st_size < 0 || (uint64_t)st.st_size > 512ULL * 1024 * 1024) { close(fd); errno = EFBIG; return NULL; }
    size_t n = (size_t)st.st_size, off = 0;
    unsigned char *buf = malloc(n ? n : 1);
    if (!buf) { close(fd); return NULL; }
    while (off < n) {
        ssize_t got = read(fd, buf + off, n - off);
        if (got <= 0) { free(buf); close(fd); errno = EIO; return NULL; }
        off += (size_t)got;
    }
    close(fd); *size = n; return buf;
}
static int collect(const char *path, const struct stat *st, int type, struct FTW *ftw) {
    (void)st; (void)ftw;
    if (type != FTW_F || scan_error) return 0;
    const char *name = strrchr(path, '/'); name = name ? name + 1 : path;
    size_t len = strlen(name);
    if (len < 5 || strcmp(name + len - 5, ".xlsx") || strstr(name, ".tmp")) return 0;
    if (strncmp(path, scan_root, scan_root_len) || path[scan_root_len] != '/') { scan_error = 1; return 1; }
    if (scan_target->count >= 1000) { scan_error = 1; return 1; }
    if (scan_target->count == scan_target->cap) {
        size_t cap = scan_target->cap ? 2 * scan_target->cap : 8;
        File *next = realloc(scan_target->files, cap * sizeof(File));
        if (!next) { scan_error = 1; return 1; }
        scan_target->files = next; scan_target->cap = cap;
    }
    File *file = &scan_target->files[scan_target->count];
    file->rel = strdup(path + scan_root_len + 1);
    if (!file->rel || strchr(file->rel, '\n') || strchr(file->rel, '\t')) { scan_error = 1; return 1; }
    file->bytes = read_bytes(path, &file->size);
    if (!file->bytes) { scan_error = 1; return 1; }
    scan_target->count++;
    return 0;
}
static Snapshot snapshot(const char *root) {
    Snapshot result = {0};
    scan_root = root; scan_root_len = strlen(root); scan_target = &result; scan_error = 0;
    if (nftw(root, collect, 20, FTW_PHYS) || scan_error) die("snapshot XLSX");
    return result;
}
static void free_snapshot(Snapshot *s) {
    for (size_t i = 0; i < s->count; ++i) { free(s->files[i].rel); free(s->files[i].bytes); }
    free(s->files);
}
static File *lookup(const Snapshot *s, const char *rel) {
    for (size_t i = 0; i < s->count; ++i) if (!strcmp(s->files[i].rel, rel)) return &s->files[i];
    return NULL;
}
static size_t changed_count(const Snapshot *pre, const Snapshot *post) {
    size_t n = 0;
    for (size_t i = 0; i < pre->count; ++i) {
        File *b = lookup(post, pre->files[i].rel);
        if (!b || b->size != pre->files[i].size || memcmp(b->bytes, pre->files[i].bytes, b->size)) ++n;
    }
    for (size_t i = 0; i < post->count; ++i) if (!lookup(pre, post->files[i].rel)) ++n;
    return n;
}
static void save_pre(const Snapshot *pre, const char *run_dir) {
    char *dir = join(run_dir, "pre");
    if (mkdir(dir, 0700) && errno != EEXIST) die("mkdir pre");
    char *index = join(run_dir, "pre_index.tsv");
    FILE *out = fopen(index, "w");
    if (!out) die("pre index");
    for (size_t i = 0; i < pre->count; ++i) {
        char file[40]; snprintf(file, sizeof file, "%06zu.bin", i);
        char *path = join(dir, file);
        FILE *f = fopen(path, "wb");
        if (!f || fwrite(pre->files[i].bytes, 1, pre->files[i].size, f) != pre->files[i].size || fclose(f)) die("save pre bytes");
        fprintf(out, "%s\t%s\n", file, pre->files[i].rel);
        free(path);
    }
    if (fclose(out)) die("close pre index");
    free(index); free(dir);
}
static int helper(const char *python, const char *root, const char *workdir, const char *run_dir) {
    char *script = join(root, "read_engine_phase6/capture_helper.py");
    pid_t pid = fork();
    if (pid < 0) die("fork helper");
    if (!pid) {
        unsetenv("READ_ENGINE_PHASE6_CONTEXT"); unsetenv("PYTHONPATH");
        char *argv[] = {(char *)python, script, (char *)workdir, (char *)run_dir, NULL};
        execv(python, argv); _exit(127);
    }
    int status;
    while (waitpid(pid, &status, 0) < 0) if (errno != EINTR) die("wait helper");
    free(script);
    return WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
}
static void write_empty_capture(const char *run_dir) {
    char *path = join(run_dir, "capture.json");
    FILE *f = fopen(path, "w"); if (!f) die("capture receipt");
    fputs("[]\n", f); if (fclose(f)) die("close capture receipt"); free(path);
}
int main(int argc, char **argv) {
    uint64_t t0 = ns();
    if (argc != 7) { fputs("usage: observer PYTHON SCRIPT WORKDIR CACHE_ROOT RUN_ROOT REPO_ROOT\n", stderr); return 125; }
    const char *python=argv[1], *script=argv[2], *workdir=argv[3], *cache=argv[4], *run_root=argv[5], *root=argv[6];
    char wd[PATH_MAX], sp[PATH_MAX];
    if (!realpath(workdir, wd) || !realpath(script, sp)) die("realpath");
    size_t wl = strlen(wd);
    if (strncmp(sp, wd, wl) || sp[wl] != '/' || strchr(sp + wl + 1, '/')) { errno = EINVAL; die("script outside workdir"); }
    if (mkdir(cache, 0700) && errno != EEXIST) die("mkdir cache");
    if (mkdir(run_root, 0700) && errno != EEXIST) die("mkdir run root");
    char *template = join(run_root, "run-XXXXXX");
    if (!mkdtemp(template)) die("mkdtemp");
    const char *run_dir = template;
    char *context = join(run_dir, "context.txt");
    FILE *cf = fopen(context, "w"); if (!cf) die("context");
    if (strchr(sp,'\n') || strchr(wd,'\n') || strchr(cache,'\n') || strchr(run_dir,'\n')) { errno=EINVAL; die("newline path"); }
    fprintf(cf, "%s\n%s\n%s\n%s\n", sp, wd, cache, run_dir);
    if (fclose(cf)) die("close context");
    uint64_t t1=ns();
    Snapshot pre=snapshot(wd);
    uint64_t t2=ns();
    char *bootstrap=join(root, "read_engine_phase6/bootstrap");
    size_t plen=strlen(bootstrap)+strlen(root)+2;
    char *pythonpath=malloc(plen); if (!pythonpath) die("PYTHONPATH alloc");
    snprintf(pythonpath, plen, "%s:%s", bootstrap, root);
    struct sigaction ignored={0}, original_int={0}, original_term={0};
    ignored.sa_handler=SIG_IGN; sigemptyset(&ignored.sa_mask);
    sigaction(SIGINT,&ignored,&original_int); sigaction(SIGTERM,&ignored,&original_term);
    pid_t pid=fork();
    if (pid<0) die("fork script");
    if (!pid) {
        sigaction(SIGINT,&original_int,NULL); sigaction(SIGTERM,&original_term,NULL);
        setenv("PYTHONPATH",pythonpath,1); setenv("READ_ENGINE_PHASE6_CONTEXT",context,1);
        if (chdir(wd)) _exit(127);
        char *childargv[]={(char *)python,sp,NULL};
        execv(python,childargv); _exit(127);
    }
    uint64_t t3=ns();
    int status=0;
    while (waitpid(pid,&status,0)<0) if (errno!=EINTR) die("wait script");
    uint64_t t4=ns();
    Snapshot post=snapshot(wd);
    size_t changed=changed_count(&pre,&post);
    uint64_t t5=ns();
    int helper_status=0;
    if (changed) { save_pre(&pre,run_dir); helper_status=helper(python,root,wd,run_dir); }
    else write_empty_capture(run_dir);
    uint64_t t6=ns();
    char *receipt=join(run_dir,"observer_receipt.json");
    FILE *rf=fopen(receipt,"w"); if (!rf) die("receipt");
    fputs("{\"run_dir\":",rf);json_string(rf,run_dir);
    fprintf(rf,",\"target_exit_code\":%d,\"target_signal\":%d,\"pre_files\":%zu,\"post_files\":%zu,\"changed_xlsx\":%zu,\"capture_helper_exit\":%d,",
            WIFEXITED(status)?WEXITSTATUS(status):-1,WIFSIGNALED(status)?WTERMSIG(status):0,pre.count,post.count,changed,helper_status);
    fprintf(rf,"\"profile_ns\":{\"argument_run_dir\":%llu,\"pre_snapshot\":%llu,\"fork_launch\":%llu,\"wait_target\":%llu,\"post_snapshot_compare\":%llu,\"changed_helper_or_empty_receipt\":%llu,\"observer_to_receipt\":%llu}}\n",
            (unsigned long long)(t1-t0),(unsigned long long)(t2-t1),(unsigned long long)(t3-t2),
            (unsigned long long)(t4-t3),(unsigned long long)(t5-t4),(unsigned long long)(t6-t5),
            (unsigned long long)(ns()-t0));
    if (fclose(rf)) die("close receipt");
    char *last=join(run_root,"last_run.json");
    FILE *lf=fopen(last,"w");if(!lf) die("last run");
    fputs("{\"run_dir\":",lf);json_string(lf,run_dir);fputs("}\n",lf);if(fclose(lf)) die("close last run");
    free_snapshot(&pre);free_snapshot(&post);free(receipt);free(last);free(bootstrap);free(pythonpath);free(context);
    int signal_number=WIFSIGNALED(status)?WTERMSIG(status):0;
    free(template);
    if (signal_number) {
        struct sigaction def={0}; def.sa_handler=SIG_DFL;sigemptyset(&def.sa_mask);
        sigaction(signal_number,&def,NULL);raise(signal_number);return 128+signal_number;
    }
    return WIFEXITED(status)?WEXITSTATUS(status):125;
}
