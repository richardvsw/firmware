#pragma once
#include <Arduino.h>

class File {
public:
    File() {}
    operator bool() const { return false; }
    bool isDirectory() { return false; }
    size_t size() { return 0; }
    File openNextFile() { return File(); }
    void close() {}
};

class LittleFSFS {
public:
    LittleFSFS() {}
    File open(const char *path, const char *mode = "r") { (void)path; (void)mode; return File(); }
    File open(const String &path, const char *mode = "r") { (void)path; (void)mode; return File(); }
    bool exists(const char *path) { (void)path; return false; }
    bool exists(const String &path) { (void)path; return false; }
    size_t totalBytes() { return 1024 * 1024 * 64; }
    size_t usedBytes() { return 1024 * 1024 * 10; }
};

extern LittleFSFS LittleFS;
