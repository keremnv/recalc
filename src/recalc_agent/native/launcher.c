#define _POSIX_C_SOURCE 200809L
/* Installed command dispatch. The default run path execs the external observer. */
#include <errno.h>
#include <glob.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

static void fail(const char *reason) {
    fprintf(stderr, "recalc-agent: %s: %s\n", reason, strerror(errno));
    exit(2);
}

static char *join(const char *a, const char *b) {
    size_t size = strlen(a) + strlen(b) + 2;
    char *result = malloc(size);
    if (!result) fail("allocate path");
    snprintf(result, size, "%s/%s", a, b);
    return result;
}

static char *absolute(const char *path, const char *cwd) {
    return path[0] == '/' ? strdup(path) : join(cwd, path);
}

static void private_directory(const char *path) {
    char *copy = strdup(path);
    if (!copy) fail("allocate directory");
    for (char *part = copy + 1; *part; ++part) {
        if (*part != '/') continue;
        *part = 0;
        if (mkdir(copy, 0700) && errno != EEXIST) fail("create cache parent");
        *part = '/';
    }
    if (mkdir(copy, 0700) && errno != EEXIST) fail("create cache directory");
    struct stat st;
    if (lstat(copy, &st) || !S_ISDIR(st.st_mode) || st.st_uid != getuid()) {
        errno = EACCES; fail("unsafe cache directory");
    }
    if (chmod(copy, 0700)) fail("make cache private");
    free(copy);
}

static char *package_root(const char *prefix) {
    for (int i = 0; i < 2; ++i) {
        char *pattern = join(prefix, i ? "lib64/python*/site-packages/recalc_agent"
                                       : "lib/python*/site-packages/recalc_agent");
        glob_t found = {0};
        int result = glob(pattern, 0, NULL, &found);
        free(pattern);
        if (result == 0 && found.gl_pathc == 1) {
            char *root = strdup(found.gl_pathv[0]);
            globfree(&found);
            return root;
        }
        globfree(&found);
    }
    errno = ENOENT; fail("installed package not found beside launcher");
    return NULL;
}

static void python_cli(const char *python, int argc, char **argv) {
    char **next = calloc((size_t)argc + 3, sizeof(char *));
    if (!next) fail("allocate arguments");
    next[0] = (char *)python;
    next[1] = "-m";
    next[2] = "recalc_agent.cli";
    for (int i = 1; i < argc; ++i) next[i + 2] = argv[i];
    execv(python, next);
    fail("launch Python CLI");
}

int main(int argc, char **argv) {
    char exe[PATH_MAX];
    ssize_t n = readlink("/proc/self/exe", exe, sizeof(exe) - 1);
    if (n < 0 || n >= (ssize_t)sizeof(exe) - 1) fail("locate launcher");
    exe[n] = 0;
    char *slash = strrchr(exe, '/');
    if (!slash) { errno = EINVAL; fail("launcher path"); }
    *slash = 0;
    char *bindir = exe;
    char *python = join(bindir, "python");
    if (access(python, X_OK)) { free(python); python = join(bindir, "python3"); }
    if (access(python, X_OK)) fail("Python interpreter beside launcher");
    char *prefix = strdup(bindir);
    if (!prefix) fail("allocate prefix");
    slash = strrchr(prefix, '/');
    if (!slash) { errno = EINVAL; fail("environment prefix"); }
    *slash = 0;
    char *root = package_root(prefix);

    if (argc < 2 || strcmp(argv[1], "run") || getenv("RECALC_CONFIG") ||
            getenv("RECALC_NO_RUNTIME")) python_cli(python, argc, argv);
    char cwd[PATH_MAX];
    if (!getcwd(cwd, sizeof(cwd))) fail("working directory");
    const char *workdir_arg = cwd;
    int index = 2;
    if (index < argc && !strcmp(argv[index], "--workdir") && index + 1 < argc) {
        workdir_arg = argv[index + 1];
        index += 2;
    }
    if (index >= argc || argv[index][0] == '-' || !strcmp(argv[index], "--"))
        python_cli(python, argc, argv);
    char *script_arg = absolute(argv[index], cwd);
    char *workdir_input = absolute(workdir_arg, cwd);
    char script[PATH_MAX], workdir[PATH_MAX];
    if (!realpath(script_arg, script) || !realpath(workdir_input, workdir))
        python_cli(python, argc, argv);
    const char *xdg = getenv("XDG_CACHE_HOME");
    char *cache_base;
    if (xdg && *xdg) cache_base = absolute(xdg, cwd);
    else {
        const char *home = getenv("HOME");
        if (!home || !*home) python_cli(python, argc, argv);
        cache_base = join(home, ".cache");
    }
    char *cache = join(cache_base, "recalc-agent");
    char *runs = join(cache, "runs");
    private_directory(cache);
    private_directory(runs);
    char *observer = join(root, "native/observer");
    char *bootstrap = join(root, "_bootstrap");
    char *helper = join(root, "_capture_helper.py");
    char **next = calloc((size_t)argc + 7, sizeof(char *));
    if (!next) fail("allocate observer arguments");
    next[0] = observer; next[1] = python; next[2] = script; next[3] = workdir;
    next[4] = cache; next[5] = runs; next[6] = bootstrap; next[7] = helper;
    for (int i = index + 1; i < argc; ++i) next[i + 7 - index] = argv[i];
    execv(observer, next);
    fail("launch packaged observer");
}
