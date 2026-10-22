#pragma once
#include <Arduino.h>
#include <stdint.h>
#include <stddef.h>
#include <map>
#include <string>
#include <fstream>
#include <sstream>

class Preferences {
private:
    std::string current_ns;
    static std::map<std::string, std::string> &store() {
        static std::map<std::string, std::string> s;
        static bool loaded = false;
        if (!loaded) {
            loaded = true;
            std::ifstream f("/usr/data/.portduino/prefs_kv.txt");
            std::string line;
            while (std::getline(f, line)) {
                size_t eq = line.find('=');
                if (eq != std::string::npos) {
                    s[line.substr(0, eq)] = line.substr(eq + 1);
                }
            }
        }
        return s;
    }

    void save() {
        std::ofstream f("/usr/data/.portduino/prefs_kv.txt");
        for (const auto &kv : store()) {
            f << kv.first << "=" << kv.second << "\n";
        }
    }

    std::string make_key(const char *key) {
        return current_ns + "/" + (key ? key : "");
    }

public:
    Preferences() {}
    ~Preferences() {}

    bool begin(const char *name, bool readOnly = false, const char *partition_label = nullptr) {
        (void)readOnly; (void)partition_label;
        current_ns = name ? name : "default";
        store(); // ensure loaded
        return true;
    }
    void end() {}
    bool clear() { return true; }
    bool remove(const char *key) {
        store().erase(make_key(key));
        save();
        return true;
    }

    size_t putInt(const char *key, int32_t value) {
        store()[make_key(key)] = std::to_string(value);
        save();
        return 4;
    }
    int32_t getInt(const char *key, int32_t defaultValue = 0) {
        auto it = store().find(make_key(key));
        if (it != store().end()) {
            try { return std::stoi(it->second); } catch (...) {}
        }
        return defaultValue;
    }

    size_t putBool(const char *key, bool value) {
        store()[make_key(key)] = value ? "1" : "0";
        save();
        return 1;
    }
    bool getBool(const char *key, bool defaultValue = false) {
        auto it = store().find(make_key(key));
        if (it != store().end()) {
            return (it->second == "1" || it->second == "true");
        }
        return defaultValue;
    }

    size_t putString(const char *key, const char *value) {
        store()[make_key(key)] = value ? value : "";
        save();
        return value ? strlen(value) : 0;
    }
    size_t putString(const char *key, const String &value) {
        return putString(key, value.c_str());
    }
    String getString(const char *key, const String &defaultValue = String()) {
        auto it = store().find(make_key(key));
        if (it != store().end()) {
            return String(it->second.c_str());
        }
        return defaultValue;
    }
    size_t getString(const char *key, char *value, size_t maxLen) {
        auto it = store().find(make_key(key));
        if (it != store().end() && value && maxLen > 0) {
            strncpy(value, it->second.c_str(), maxLen - 1);
            value[maxLen - 1] = '\0';
            return strlen(value);
        }
        return 0;
    }

    size_t putChar(const char *key, int8_t value) { return putInt(key, value); }
    size_t putUChar(const char *key, uint8_t value) { return putInt(key, value); }
    size_t putShort(const char *key, int16_t value) { return putInt(key, value); }
    size_t putUShort(const char *key, uint16_t value) { return putInt(key, value); }
    size_t putUInt(const char *key, uint32_t value) { return putInt(key, (int32_t)value); }
    size_t putLong(const char *key, int32_t value) { return putInt(key, value); }
    size_t putULong(const char *key, uint32_t value) { return putInt(key, (int32_t)value); }
    size_t putLong64(const char *key, int64_t value) { return putInt(key, (int32_t)value); }
    size_t putULong64(const char *key, uint64_t value) { return putInt(key, (int32_t)value); }
    size_t putFloat(const char *key, float_t value) { return putInt(key, (int32_t)value); }
    size_t putDouble(const char *key, double_t value) { return putInt(key, (int32_t)value); }
    size_t putBytes(const char *key, const void *value, size_t len) { (void)key; (void)value; return len; }

    int8_t getChar(const char *key, int8_t defaultValue = 0) { return (int8_t)getInt(key, defaultValue); }
    uint8_t getUChar(const char *key, uint8_t defaultValue = 0) { return (uint8_t)getInt(key, defaultValue); }
    int16_t getShort(const char *key, int16_t defaultValue = 0) { return (int16_t)getInt(key, defaultValue); }
    uint16_t getUShort(const char *key, uint16_t defaultValue = 0) { return (uint16_t)getInt(key, defaultValue); }
    uint32_t getUInt(const char *key, uint32_t defaultValue = 0) { return (uint32_t)getInt(key, defaultValue); }
    int32_t getLong(const char *key, int32_t defaultValue = 0) { return getInt(key, defaultValue); }
    uint32_t getULong(const char *key, uint32_t defaultValue = 0) { return (uint32_t)getInt(key, defaultValue); }
    int64_t getLong64(const char *key, int64_t defaultValue = 0) { return getInt(key, defaultValue); }
    uint64_t getULong64(const char *key, uint64_t defaultValue = 0) { return (uint64_t)getInt(key, defaultValue); }
    float_t getFloat(const char *key, float_t defaultValue = 0) { return (float_t)getInt(key, (int32_t)defaultValue); }
    double_t getDouble(const char *key, double_t defaultValue = 0) { return (double_t)getInt(key, (int32_t)defaultValue); }
    size_t getBytesLength(const char *key) { (void)key; return 0; }
    size_t getBytes(const char *key, void *buf, size_t maxLen) { (void)key; (void)buf; (void)maxLen; return 0; }
    bool isKey(const char *key) { return store().find(make_key(key)) != store().end(); }
};
