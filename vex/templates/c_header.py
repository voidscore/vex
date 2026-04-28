TEMPLATE_C_VERSION_HEADER = """#ifndef VERSION_H
#define VERSION_H

#define VERSION_MAJOR {major}
#define VERSION_MINOR {minor}
#define VERSION_PATCH {patch}

#define BUILD_COUNT {build_count}
#define BUILD_TIME "{build_time}"

#define GIT_BRANCH "{branch}"
#define GIT_HASH "{hash}"
#define GIT_DIRTY {dirty}

#endif // VERSION_H
"""