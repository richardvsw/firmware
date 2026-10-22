// string.h shim for Windows cross-compilation with Zig/libc++
//
// PROBLEM: On Windows, the case-insensitive filesystem causes:
//   1. ArduinoCore-API/api/String.h to match <string.h> searches (clang warning:
//      "non-portable path to file '<String.h>'")
//   2. #include_next <string.h> from this shim also finds String.h again
//      (not the real glibc string.h), so string functions are never declared.
//   3. libc++'s <cstring> checks for _LIBCPP_STRING_H after #include <string.h>;
//      if String.h is found instead, _LIBCPP_STRING_H is never set → error.
//
// SOLUTION: This self-contained shim:
//   - Is injected as the very FIRST -I path (in the Zig wrapper script)
//   - Defines _LIBCPP_STRING_H (satisfies libc++'s <cstring> guard)
//   - Directly declares ALL standard C + POSIX/GNU string functions without
//     chaining to any other file (avoids the Windows case-insensitive trap)
//   - Provides proper C++ const-qualified overloads for strchr, strrchr etc.
//     (matching what glibc provides with __CORRECT_ISO_CPP_STRING_H_PROTO)
//
// Generated for hiby-r1 mipsel-linux-gnueabi cross-compilation on Windows.

#ifndef _LIBCPP_STRING_H
#define _LIBCPP_STRING_H

// Also set glibc's own string.h and strings.h guard so it won't try to re-include if it
// somehow gets referenced later.
#ifndef _STRING_H
#define _STRING_H 1
#endif
#ifndef _STRINGS_H
#define _STRINGS_H 1
#endif

#include <stddef.h>   // size_t, NULL
#include <stdint.h>   // uint8_t etc. (some callers expect these alongside string.h)
#include <stdlib.h>   // malloc, free, realloc, calloc, rand (frequently expected with string.h)

// libc++ needs _LIBCPP_STRING_H_HAS_CONST_OVERLOADS so it knows we provide them
#define _LIBCPP_STRING_H_HAS_CONST_OVERLOADS
// glibc sets this when it provides const-correct C++ prototypes
#define __CORRECT_ISO_CPP_STRING_H_PROTO

#ifdef __cplusplus
extern "C" {
#endif

// ── ISO C standard string functions ──────────────────────────────────────────

void*  memcpy (void* __restrict, const void* __restrict, size_t);
void*  memmove(void*, const void*, size_t);
void*  memset (void*, int, size_t);
int    memcmp (const void*, const void*, size_t);
char*  strcpy (char* __restrict, const char* __restrict);
char*  strncpy(char* __restrict, const char* __restrict, size_t);
char*  strcat (char* __restrict, const char* __restrict);
char*  strncat(char* __restrict, const char* __restrict, size_t);
int    strcmp (const char*, const char*);
int    strncmp(const char*, const char*, size_t);
int    strcoll(const char*, const char*);
size_t strxfrm(char* __restrict, const char* __restrict, size_t);
size_t strcspn(const char*, const char*);
size_t strspn (const char*, const char*);
char*  strtok (char* __restrict, const char* __restrict);
size_t strlen (const char*);
char*  strerror(int);

// ── POSIX / GNU extension string functions ────────────────────────────────────

char*  strdup    (const char*);
char*  strndup   (const char*, size_t);
size_t strnlen   (const char*, size_t);
size_t strlcpy   (char* __restrict, const char* __restrict, size_t);
size_t strlcat   (char* __restrict, const char* __restrict, size_t);
int    strcasecmp (const char*, const char*);
int    strncasecmp(const char*, const char*, size_t);
char*  strsep     (char**, const char*);
char*  strchrnul  (const char*, int);
void*  mempcpy    (void* __restrict, const void* __restrict, size_t);
void*  memrchr    (const void*, int, size_t);
void*  memmem     (const void*, size_t, const void*, size_t);
char*  stpcpy     (char* __restrict, const char* __restrict);
char*  stpncpy    (char* __restrict, const char* __restrict, size_t);
char*  strcasestr (const char*, const char*);

#ifndef __cplusplus
// In C mode these are declared with non-const return (standard C prototype)
char*  strchr (const char*, int);
char*  strrchr(const char*, int);
char*  strpbrk(const char*, const char*);
char*  strstr (const char*, const char*);
void*  memchr (const void*, int, size_t);
#endif

#ifdef __cplusplus
} // extern "C"

// ── C++ const-qualified overloads ─────────────────────────────────────────────
// These are required by libc++ internals (hash.h, cstring, etc.) and any C++
// code that calls strchr/strstr/memchr with const char* and expects const char*.

extern "C++" {

inline __attribute__((__always_inline__)) const char*
strchr(const char* __s, int __c) { return __builtin_strchr(__s, __c); }
inline __attribute__((__always_inline__)) char*
strchr(      char* __s, int __c) { return __builtin_strchr(__s, __c); }

inline __attribute__((__always_inline__)) const char*
strrchr(const char* __s, int __c) { return __builtin_strrchr(__s, __c); }
inline __attribute__((__always_inline__)) char*
strrchr(      char* __s, int __c) { return __builtin_strrchr(__s, __c); }

inline __attribute__((__always_inline__)) const void*
memchr(const void* __s, int __c, size_t __n) { return __builtin_memchr(__s, __c, __n); }
inline __attribute__((__always_inline__)) void*
memchr(      void* __s, int __c, size_t __n) { return __builtin_memchr(__s, __c, __n); }

inline __attribute__((__always_inline__)) const char*
strpbrk(const char* __s1, const char* __s2) { return __builtin_strpbrk(__s1, __s2); }
inline __attribute__((__always_inline__)) char*
strpbrk(      char* __s1, const char* __s2) { return __builtin_strpbrk(__s1, __s2); }

inline __attribute__((__always_inline__)) const char*
strstr(const char* __s1, const char* __s2) { return __builtin_strstr(__s1, __s2); }
inline __attribute__((__always_inline__)) char*
strstr(      char* __s1, const char* __s2) { return __builtin_strstr(__s1, __s2); }

// strcasestr C++ overloads omitted — the extern "C" declaration above is sufficient.
// C++ callers will use the non-const-qualified char* version from the C scope.

} // extern "C++"
#endif // __cplusplus

#endif // _LIBCPP_STRING_H
