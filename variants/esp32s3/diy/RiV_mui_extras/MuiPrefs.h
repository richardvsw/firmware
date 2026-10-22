#pragma once
#include <Arduino.h>

#if __has_include(<Preferences.h>)
#include <Preferences.h>
#else
#include <map>
#include <string>
#include <fstream>
#include <sstream>
#include <stdlib.h>

class Preferences {
public:
    Preferences() : opened(false), readOnly(true) {}
    ~Preferences() { end(); }

    bool begin(const char *name, bool ro = false) {
        ns = name ? name : "default";
        readOnly = ro;
        opened = true;
        load();
        return true;
    }

    void end() {
        if (opened && !readOnly && dirty) save();
        opened = false;
    }

    bool putBool(const char *key, bool value) { return putString(key, value ? "1" : "0") > 0; }
    bool getBool(const char *key, bool defaultValue = false) {
        std::string val = getVal(key);
        if (val.empty()) return defaultValue;
        return (val == "1" || val == "true");
    }

    size_t putInt(const char *key, int32_t value) {
        char buf[32]; snprintf(buf, sizeof(buf), "%d", (int)value);
        return putString(key, buf);
    }

    int32_t getInt(const char *key, int32_t defaultValue = 0) {
        std::string val = getVal(key);
        if (val.empty()) return defaultValue;
        return atoi(val.c_str());
    }

    size_t putString(const char *key, const char *value) {
        if (!opened || readOnly || !key) return 0;
        store[ns][key] = value ? value : "";
        dirty = true;
        return strlen(value ? value : "");
    }

    size_t putString(const char *key, const String &value) { return putString(key, value.c_str()); }

    String getString(const char *key, const String &defaultValue = String()) {
        std::string val = getVal(key);
        if (val.empty()) return defaultValue;
        return String(val.c_str());
    }

private:
    std::string ns;
    bool opened;
    bool readOnly;
    inline static std::map<std::string, std::map<std::string, std::string>> store;
    inline static bool loaded = false;
    inline static bool dirty = false;

    std::string getVal(const char *key) {
        if (!key) return "";
        auto it_ns = store.find(ns);
        if (it_ns != store.end()) {
            auto it_k = it_ns->second.find(key);
            if (it_k != it_ns->second.end()) return it_k->second;
        }
        return "";
    }

    static void load() {
        if (loaded) return;
        loaded = true;
        FILE *f = fopen("/prefs/chatui.txt", "r");
        if (!f) f = fopen("chatui.txt", "r");
        if (!f) return;
        char line[256];
        while (fgets(line, sizeof(line), f)) {
            char *eq = strchr(line, '=');
            if (!eq) continue;
            *eq = 0;
            char *k = line;
            char *v = eq + 1;
            char *nl = strchr(v, '\r'); if (nl) *nl = 0;
            nl = strchr(v, '\n'); if (nl) *nl = 0;
            char *dot = strchr(k, '.');
            if (dot) {
                *dot = 0;
                store[k][dot + 1] = v;
            } else {
                store["chatui"][k] = v;
            }
        }
        fclose(f);
    }

    static void save() {
        dirty = false;
        FILE *f = fopen("/prefs/chatui.txt", "w");
        if (!f) f = fopen("chatui.txt", "w");
        if (!f) return;
        for (auto const &n : store) {
            for (auto const &kv : n.second) {
                fprintf(f, "%s.%s=%s\n", n.first.c_str(), kv.first.c_str(), kv.second.c_str());
            }
        }
        fclose(f);
    }
};
#endif
