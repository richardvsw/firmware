import filecmp
import os, re
import shutil

Import("env")

# MUI EXTRAS, SWITCHABLE PER ENV. ADD TO AN ENV:
#   extra_scripts = ${...extra_scripts}
#     pre:variants/esp32s3/diy/RiV_mui_extras/mui_extras.py
#   custom_riv_mui_features = keyboard emoji chat themes advanced wake   (any subset, default all)
#   custom_riv_mui_emoji = full      (small: 33 emoji, SD pack for the rest; full: 650 colour + 1300 mono in flash)
#   custom_riv_mui_kb_height = 34    (portrait 320x480 only, percent of the screen, empty keeps the stock 45)
HERE = env.subst("$PROJECT_DIR/variants/esp32s3/diy/RiV_mui_extras")
LIB = env.subst("$PROJECT_DIR/.pio/libdeps/${PIOENV}")
UI = os.path.join(LIB, "meshtastic-device-ui")
LV = os.path.join(LIB, "lvgl")

ALL = "keyboard emoji chat themes advanced wake compose screensaver stickman"  # meshbot is switched on per env
feat = set(str(env.GetProjectOption("custom_riv_mui_features", ALL)).replace(",", " ").split())
emoji_set = str(env.GetProjectOption("custom_riv_mui_emoji", "full")).strip()
ina_addr = str(env.GetProjectOption("custom_riv_mui_ina_address", "")).strip()
notify_pin = str(env.GetProjectOption("custom_riv_mui_notify_pin", "48")).strip()
kb_pct = str(env.GetProjectOption("custom_riv_mui_kb_height", "")).strip()
full = "_all" if emoji_set == "full" else ""

KEY = "\U0001F642"
ROW1 = ["\U0001F600", "\U0001F602", "\U0001F642", "\U0001F609", "\U0001F60D", "\U0001F622", "\U0001F62E", "\U0001F60E", "\U0001F621", "\U0001F914"]
ROW2 = ["\U0001F44D", "\U0001F44E", "\U0001F44B", "\U0001F64F", "\U0001F44C", "\u270C", "\U0001F4AA", "\u2764", "\U0001F389", "\U0001F37A", "\u2615"]
ROW3 = ["\U0001F525", "\u2B50", "\u2705", "\u274C", "\u26A0", "\u2753", "\U0001F4CD", "\U0001F50B", "\U0001F4E1", "\U0001F697", "\U0001F3E0", "\u26F0"]

MISSES = []

MENTION_LAMBDA = """    emoji_mention_host([](const char *q, void (*cb)(const char *, const char *, uint32_t)) {
        size_t ql = q ? strlen(q) : 0;
        for (auto &kv : THIS->nodes) {
            if (kv.first == THIS->ownNode)
                continue;
            const char *s = (const char *)&(kv.second->LV_OBJ_IDX(node_lbs_idx)->user_data);
            const char *l = lv_label_get_text(kv.second->LV_OBJ_IDX(node_lbl_idx));
            if (ql == 0 || strncasecmp(s, q, ql) == 0 || (l && strncasecmp(l, q, ql) == 0))
                cb(l, s, kv.first);
        }
    });
"""

MESHBOT_LAMBDA = """    emoji_meshbot_host(
        [](const char *sn, const char *ln) -> uint32_t {
            for (auto &kv : THIS->nodes) {
                const char *s = (const char *)&(kv.second->LV_OBJ_IDX(node_lbs_idx)->user_data);
                const char *l = lv_label_get_text(kv.second->LV_OBJ_IDX(node_lbl_idx));
                if (sn && sn[0] && strncasecmp(s, sn, 4) == 0 && (!ln || !ln[0] || (l && strcasecmp(l, ln) == 0)))
                    return kv.first;
            }
            return 0;
        },
        [](uint32_t num) { THIS->showMessages(num); });
"""

NODES_LAMBDA = """    emoji_nodes_host([](uint32_t days, bool doRemove, uint32_t *st) -> uint32_t {
        time_t now = THIS->actTime;
        if (now < 1700000000)
            time(&now);
        uint32_t limit = days * 86400u, h1 = 0, h24 = 0, h7 = 0;
        std::vector<uint32_t> victims;
        for (auto &kv : THIS->nodes) {
            uint32_t num = kv.first;
            uint32_t lh = (unsigned long)kv.second->LV_OBJ_IDX(node_lh_idx)->user_data;
            uint32_t age = (lh && now > (time_t)lh) ? (uint32_t)(now - lh) : 0;
            if (lh) {
                if (age <= 3600)
                    h1++;
                if (age <= 86400)
                    h24++;
                if (age <= 7 * 86400)
                    h7++;
            }
            bool old = lh == 0 || age >= limit;
            if (old && num != THIS->ownNode && !emoji_node_protected(num) && THIS->chats.find(num) == THIS->chats.end() &&
                THIS->messages.find(num) == THIS->messages.end())
                victims.push_back(num);
        }
        if (st) {
            st[0] = THIS->nodeCount;
            st[1] = h1;
            st[2] = h24;
            st[3] = h7;
            st[4] = MAX_NUM_NODES_VIEW;
        }
        if (doRemove) {
            for (uint32_t num : victims) {
                auto it = THIS->nodes.find(num);
                if (it == THIS->nodes.end())
                    continue;
                lv_obj_t *p = it->second;
                uint32_t lh = (unsigned long)p->LV_OBJ_IDX(node_lh_idx)->user_data;
                if (lh > 0 && now >= (time_t)lh && (now - lh <= THIS->secs_until_offline) && THIS->nodesOnline > 0)
                    THIS->nodesOnline--;
                lv_obj_delete(p);
                THIS->removeFromMap(num);
                THIS->nodes.erase(num);
                if (THIS->nodeCount > 1)
                    THIS->nodeCount--;
                THIS->controller->sendAdminMessage(
                    meshtastic_AdminMessage{.which_payload_variant = meshtastic_AdminMessage_remove_by_nodenum_tag, .remove_by_nodenum = num},
                    THIS->ownNode);
            }
            THIS->nodesChanged = true;
        }
        return (uint32_t)victims.size();
    });
"""

WRAP_MARK = "/*Initialize a public general font descriptor*/"


REC = ["\U0001F44D", "❤", "\U0001F602", "\U0001F64F", "\U0001F525", "\U0001F600", "✅", "\U0001F622", "\U0001F389", "\U0001F62E"]


def cstr(ch):
    return '"' + "".join("\\x%02X" % b for b in ch.encode("utf-8")) + '"'


def read(p):
    with open(p, "r", encoding="utf-8", newline="") as f:
        s = f.read()
    return s.replace("\r\n", "\n"), "\r\n" in s


def write(p, s, crlf):
    data = (s.replace("\n", "\r\n") if crlf else s).encode("utf-8")
    if os.path.exists(p):
        with open(p, "rb") as f:
            if f.read() == data:
                return  # unchanged, keep the timestamp so the build does not recompile it
    with open(p, "wb") as f:
        f.write(data)


def edit(path, anchor, add, mode="after"):
    # insert text after/before an anchor, or replace it; skipped when the added text is already there
    if not os.path.exists(path):
        print("MUI-EXTRAS WARNING: file not found:", path)
        MISSES.append(path)
        return
    s, crlf = read(path)
    if add in s:
        return
    if isinstance(anchor, (list, tuple)):
        match = None
        for a in anchor:
            if a in s:
                match = a
                break
        if not match:
            marks = [ln for ln in add.split("\n") if len(ln.strip()) > 12]
            if marks and marks[0] in s:
                return
            print("MUI-EXTRAS WARNING: anchor not found in %s: %r" % (os.path.basename(path), anchor[0][:80]))
            MISSES.append(os.path.basename(path) + ": " + anchor[0][:60])
            return
        anchor = match
    elif anchor not in s:
        # a later patch may have rewritten the text of this one, then its first real line is still there
        marks = [ln for ln in add.split("\n") if len(ln.strip()) > 12]
        if marks and marks[0] in s:
            return
        print("MUI-EXTRAS WARNING: anchor not found in %s: %r" % (os.path.basename(path), anchor[:80]))
        MISSES.append(os.path.basename(path) + ": " + anchor[:60])
        return
    new = {"after": anchor + add, "before": add + anchor, "replace": add}[mode]
    write(path, s.replace(anchor, new, 1), crlf)
    print("Patched", path)


def copy(name, dst_dir, dst_name=None):
    src = os.path.join(HERE, name)
    dst = os.path.join(dst_dir, dst_name or (name[:-3] if name.endswith(".in") else name))
    if os.path.exists(dst) and filecmp.cmp(src, dst, shallow=False):
        return  # unchanged, keep the timestamp
    shutil.copyfile(src, dst)


def font_files():
    out = [os.path.join(LV, "src", "font", "lv_font_montserrat_%d.c" % n) for n in (12, 14, 16, 20)]
    out += [os.path.join(UI, "generated", d, "ui_font_montserrat_%d.c" % n)
            for d in ("ui_320x240", "ui_240x320") for n in (12, 14, 16, 20)]
    return [p for p in out if os.path.exists(p)]


def patch_fonts():
    for p in font_files():
        s, crlf = read(p)
        if "&ui_emoji_color_font" in s:
            continue
        s = s.replace(".fallback = NULL,", ".fallback = &ui_emoji_color_font,", 1)
        if "&ui_emoji_color_font" not in s:
            # LVGL's own font files have no fallback line
            s = s.replace(".dsc = &font_dsc ", ".dsc = &font_dsc, ", 1)
            s = s.replace("*/\n};", "*/\n    .fallback = &ui_emoji_color_font\n};", 1)
        if WRAP_MARK not in s:
            continue
        s = s.replace(WRAP_MARK, "extern lv_font_t ui_emoji_color_font;\n" + WRAP_MARK, 1)
        write(p, s, crlf)
        print("Patched", p)
    # the UI fonts hold mono glyphs for some code points, skip them when a colour image exists
    wrapper = ("extern bool emoji_color_has(uint32_t cp);\n"
               "static bool emoji_font_dsc_wrapper(const lv_font_t * font, lv_font_glyph_dsc_t * dsc, uint32_t letter, uint32_t letter_next)\n"
               "{\n"
               "    if(emoji_color_has(letter)) return false;\n"
               "    return lv_font_get_glyph_dsc_fmt_txt(font, dsc, letter, letter_next);\n"
               "}\n")
    for d in ("ui_320x240", "ui_240x320"):
        for n in (12, 14, 16, 20):
            p = os.path.join(UI, "generated", d, "ui_font_montserrat_%d.c" % n)
            if not os.path.exists(p):
                continue
            s, crlf = read(p)
            if "emoji_font_dsc_wrapper" in s or WRAP_MARK not in s or ".get_glyph_dsc = lv_font_get_glyph_dsc_fmt_txt," not in s:
                continue
            s = s.replace(WRAP_MARK, wrapper + WRAP_MARK, 1)
            s = s.replace(".get_glyph_dsc = lv_font_get_glyph_dsc_fmt_txt,", ".get_glyph_dsc = emoji_font_dsc_wrapper,", 1)
            write(p, s, crlf)
            print("Patched", p)


def patch_keyboard_emoji(compose):
    kb = os.path.join(LV, "src", "widgets", "keyboard", "lv_keyboard.c")
    if not os.path.exists(kb):
        return
    s, crlf = read(kb)
    if "EMOJI_KEY" in s:
        return
    s = s.replace("#define LV_KB_BTN(width) LV_BUTTONMATRIX_CTRL_POPOVER | width\n",
                  "#define LV_KB_BTN(width) LV_BUTTONMATRIX_CTRL_POPOVER | width\n#define EMOJI_KEY " + cstr(KEY) + "\n", 1)
    if compose:
        s = s.replace("static void lv_keyboard_update_ctrl_map(lv_obj_t * obj);\n",
                      "static void lv_keyboard_update_ctrl_map(lv_obj_t * obj);\n"
                      "extern void emoji_format_key(int kind);\n"
                      "extern void emoji_recent_note(const char * txt);\n", 1)
    bottom = 'LV_SYMBOL_LEFT, " ", LV_SYMBOL_RIGHT, LV_SYMBOL_OK, ""'
    bottom_new = ('"B/I", " ", LV_SYMBOL_BELL, LV_SYMBOL_OK, EMOJI_KEY, ""' if compose
                  else 'LV_SYMBOL_LEFT, " ", LV_SYMBOL_RIGHT, LV_SYMBOL_OK, EMOJI_KEY, ""')
    s = s.replace(bottom, bottom_new, 2)
    old_ctrl = "LV_BUTTONMATRIX_CTRL_CHECKED | 2, 6, LV_BUTTONMATRIX_CTRL_CHECKED | 2, LV_KEYBOARD_CTRL_BUTTON_FLAGS | 2\n};"
    s = s.replace(old_ctrl, old_ctrl.replace("\n};", ", LV_KEYBOARD_CTRL_BUTTON_FLAGS | 2\n};"), 2)
    emoji_map = ("static const char * const default_kb_map_emoji[] = {\"abc\", "
                 + ", ".join(cstr(c) for c in ROW1) + ", LV_SYMBOL_BACKSPACE, \"\\n\", "
                 + ", ".join(cstr(c) for c in ROW2) + ", \"\\n\", "
                 + ", ".join(cstr(c) for c in ROW3) + ", \"\\n\", "
                 + "LV_SYMBOL_KEYBOARD, LV_SYMBOL_LEFT, \" \", LV_SYMBOL_RIGHT, LV_SYMBOL_OK, \"\"};\n"
                 "static const lv_buttonmatrix_ctrl_t default_kb_ctrl_emoji_map[] = {\n"
                 "    LV_KEYBOARD_CTRL_BUTTON_FLAGS | 5, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, LV_BUTTONMATRIX_CTRL_CHECKED | 7,\n"
                 "    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,\n"
                 "    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,\n"
                 "    LV_KEYBOARD_CTRL_BUTTON_FLAGS | 2, LV_BUTTONMATRIX_CTRL_CHECKED | 2, 6, LV_BUTTONMATRIX_CTRL_CHECKED | 2, LV_KEYBOARD_CTRL_BUTTON_FLAGS | 2\n};\n\n")
    s = s.replace("static const char * const * kb_map[10] = {", emoji_map + "static const char * const * kb_map[10] = {", 1)
    s = s.replace("    default_kb_map_spec,\n    default_kb_map_num,\n    default_kb_map_lc,",
                  "    default_kb_map_spec,\n    default_kb_map_num,\n    default_kb_map_emoji,", 1)
    s = s.replace("    default_kb_ctrl_spec_map,\n    default_kb_ctrl_num_map,\n    default_kb_ctrl_lc_map,",
                  "    default_kb_ctrl_spec_map,\n    default_kb_ctrl_num_map,\n    default_kb_ctrl_emoji_map,", 1)
    handler = ("    if(lv_strcmp(txt, EMOJI_KEY) == 0 && keyboard->mode != LV_KEYBOARD_MODE_USER_1) {\n"
               "        keyboard->mode = LV_KEYBOARD_MODE_USER_1;\n"
               "        lv_buttonmatrix_set_map(obj, kb_map[LV_KEYBOARD_MODE_USER_1]);\n"
               "        lv_keyboard_update_ctrl_map(obj);\n"
               "        return;\n"
               "    }\n")
    if compose:
        handler += ("    if(lv_strcmp(txt, \"B/I\") == 0) {\n"
                    "        emoji_format_key(-1);\n"
                    "        return;\n"
                    "    }\n"
                    "    if(lv_strcmp(txt, LV_SYMBOL_BELL) == 0) {\n"
                    "        emoji_format_key(5);\n"
                    "        return;\n"
                    "    }\n")
    s = s.replace('    if(lv_strcmp(txt, "abc") == 0) {', handler + '    if(lv_strcmp(txt, "abc") == 0) {', 1)
    if compose:
        s = s.replace("        lv_textarea_add_text(keyboard->ta, txt);\n    }\n}",
                      "        emoji_recent_note(txt);\n        lv_textarea_add_text(keyboard->ta, txt);\n    }\n}", 1)
    write(kb, s, crlf)
    print("Patched", kb)



def patch_mui_node_and_channel(tft, UI):
    tft_h = os.path.join(UI, "include", "graphics", "view", "TFT", "TFTView_320x240.h")
    if os.path.exists(tft_h):
        s_h, crlf_h = read(tft_h)
        idx_start = s_h.find('    static void ui_event_NodeButton(lv_event_t *e);\n')
        idx_end = s_h.find('    static void ui_event_ChannelButton(lv_event_t *e);')
        if idx_start != -1 and idx_end != -1 and idx_start < idx_end:
            anchor_len = len('    static void ui_event_NodeButton(lv_event_t *e);\n')
            if idx_start + anchor_len < idx_end:
                s_h = s_h[:idx_start + anchor_len] + s_h[idx_end:]
                write(tft_h, s_h, crlf_h)

    edit(tft_h, "    static void ui_event_NodeButton(lv_event_t *e);\n",
         "public:\n    static void emoji_traceroute(uint32_t to, uint8_t ch);\n    static void emoji_open_node_chat_impl(uint32_t nodeNum);\n    static uint32_t emoji_find_node_by_name_impl(const char *shortName, const char *longName);\n    static void show_failed_message_popup(lv_obj_t *panel);\n    static void failed_popup_retry_cb(lv_event_t *e);\n    static void failed_popup_delete_cb(lv_event_t *e);\n    static void failed_popup_cancel_cb(lv_event_t *e);\n    static void modal_backdrop_cb(lv_event_t *e);\n    static void fail_badge_click_cb(lv_event_t *e);\n    static void attach_failed_message_badge(lv_obj_t *panel, lv_obj_t *textLabel);\n    static void remove_failed_message_badge(lv_obj_t *panel);\nprotected:\n    static void ui_event_search_ta(lv_event_t *e);\n    static void ui_event_search_kb(lv_event_t *e);\n", "after")

    if os.path.exists(tft):
        s_tft, crlf_tft = read(tft)
        idx_start = s_tft.find('extern "C" __attribute__((weak)) void get_node_details_string')
        idx_end = s_tft.find('void TFTView_320x240::ui_set_active(lv_obj_t *b, lv_obj_t *p, lv_obj_t *tp)\n{')
        if idx_start != -1 and idx_end != -1 and idx_start < idx_end:
            s_tft = s_tft[:idx_start] + s_tft[idx_end:]
            write(tft, s_tft, crlf_tft)

        idx_hf_start = s_tft.find('lv_obj_set_size(objects.blank_screen, h, v);\n')
        idx_hf_end = s_tft.find('    // resize buttons on larger display (assuming 480x480)')
        if idx_hf_start != -1 and idx_hf_end != -1 and idx_hf_start < idx_hf_end:
            anchor_len = len('lv_obj_set_size(objects.blank_screen, h, v);\n')
            if idx_hf_start + anchor_len < idx_hf_end:
                s_tft = s_tft[:idx_hf_start + anchor_len] + s_tft[idx_hf_end:]
                write(tft, s_tft, crlf_tft)

    decl_block = (
        'extern "C" __attribute__((weak)) void get_node_details_string(uint32_t nodeNum, char *idStr, size_t idLen,\n'
        '                                                             char *roleModelStr, size_t rmLen,\n'
        '                                                             char *batSigStr, size_t bsLen,\n'
        '                                                             char *gpsStr, size_t gpsLen)\n'
        '{\n'
        '    snprintf(idStr, idLen, "!%08x (%u)", (unsigned)nodeNum, (unsigned)nodeNum);\n'
        '    snprintf(roleModelStr, rmLen, "Role: Client  •  Model: Node");\n'
        '    snprintf(batSigStr, bsLen, "Bat: --  •  No signal data");\n'
        '    snprintf(gpsStr, gpsLen, "GPS: No position data");\n'
        '}\n\n'
        'extern "C" void emoji_channel_open_index(int);\n'
        'static lv_obj_t *g_node_search_bar = nullptr;\n'
        'static lv_obj_t *g_node_search_ta = nullptr;\n\n'
        'void TFTView_320x240::ui_event_search_ta(lv_event_t *e) {\n'
        '    lv_event_code_t code = lv_event_get_code(e);\n'
        '    lv_obj_t *ta = (lv_obj_t *)lv_event_get_target(e);\n'
        '    if (code == LV_EVENT_CLICKED || code == LV_EVENT_FOCUSED) {\n'
        '        if (objects.keyboard) {\n'
        '            lv_obj_remove_flag(objects.keyboard, LV_OBJ_FLAG_HIDDEN);\n'
        '            lv_obj_move_foreground(objects.keyboard);\n'
        '        }\n'
        '        THIS->showKeyboard(ta);\n'
        '    } else if (code == LV_EVENT_VALUE_CHANGED) {\n'
        '        const char *txt = lv_textarea_get_text(ta);\n'
        '        lv_textarea_set_text(objects.nodes_filter_name_area, txt ? txt : "");\n'
        '        THIS->updateNodesFiltered(true);\n'
        '        THIS->updateNodesStatus();\n'
        '    } else if (code == LV_EVENT_READY || code == LV_EVENT_CANCEL) {\n'
        '        if (objects.keyboard)\n'
        '            lv_obj_add_flag(objects.keyboard, LV_OBJ_FLAG_HIDDEN);\n'
        '        lv_obj_remove_state(ta, LV_STATE_FOCUSED);\n'
        '    }\n'
        '}\n\n'
        'void TFTView_320x240::ui_event_search_kb(lv_event_t *e) {\n'
        '    if (lv_event_get_code(e) == LV_EVENT_CLICKED) {\n'
        '        if (objects.keyboard) {\n'
        '            if (lv_obj_has_flag(objects.keyboard, LV_OBJ_FLAG_HIDDEN)) {\n'
        '                lv_obj_remove_flag(objects.keyboard, LV_OBJ_FLAG_HIDDEN);\n'
        '                lv_obj_move_foreground(objects.keyboard);\n'
        '                THIS->showKeyboard(g_node_search_ta);\n'
        '            } else {\n'
        '                lv_obj_add_flag(objects.keyboard, LV_OBJ_FLAG_HIDDEN);\n'
        '                if (g_node_search_ta)\n'
        '                    lv_obj_remove_state(g_node_search_ta, LV_STATE_FOCUSED);\n'
        '            }\n'
        '        }\n'
        '    }\n'
        '}\n\n'
    )
    decl_block += r"""
struct SimplePos {
    uint32_t nodeNum;
    int32_t lat;
    int32_t lon;
};
static SimplePos g_nodePositions[32];
static int g_nodePosCount = 0;
static int32_t g_myLat = 0, g_myLon = 0;

extern "C" void emoji_record_node_pos(uint32_t nodeNum, int32_t lat, int32_t lon, bool isOwn)
{
    if (isOwn) {
        g_myLat = lat;
        g_myLon = lon;
    }
    if (!nodeNum || (lat == 0 && lon == 0)) return;
    for (int i = 0; i < g_nodePosCount; i++) {
        if (g_nodePositions[i].nodeNum == nodeNum) {
            g_nodePositions[i].lat = lat;
            g_nodePositions[i].lon = lon;
            return;
        }
    }
    if (g_nodePosCount < 32) {
        g_nodePositions[g_nodePosCount++] = {nodeNum, lat, lon};
    }
}

extern "C" bool emoji_distance_enabled(void) __attribute__((weak));

extern "C" bool emoji_node_distance_str(uint32_t nodeNum, char *out, size_t outSize)
{
    if (!out || outSize < 16) return false;
    out[0] = 0;
    if (emoji_distance_enabled && !emoji_distance_enabled()) return false;
    if (g_myLat == 0 && g_myLon == 0) return false;
    int32_t tLat = 0, tLon = 0;
    for (int i = 0; i < g_nodePosCount; i++) {
        if (g_nodePositions[i].nodeNum == nodeNum) {
            tLat = g_nodePositions[i].lat;
            tLon = g_nodePositions[i].lon;
            break;
        }
    }
    if (tLat == 0 && tLon == 0) return false;

    float dx = 71.5f * 1e-7f * (float)(tLon - g_myLon);
    float dy = 111.3f * 1e-7f * (float)(tLat - g_myLat);
    float dist = sqrtf(dx * dx + dy * dy);
    float rad = atan2f(dx, dy);
    float deg = rad * 57.29578f;
    if (deg < 0.0f) deg += 360.0f;

    const char *dir = "N";
    if (deg >= 22.5f && deg < 67.5f) dir = "NE";
    else if (deg >= 67.5f && deg < 112.5f) dir = "E";
    else if (deg >= 112.5f && deg < 157.5f) dir = "SE";
    else if (deg >= 157.5f && deg < 202.5f) dir = "S";
    else if (deg >= 202.5f && deg < 247.5f) dir = "SW";
    else if (deg >= 247.5f && deg < 292.5f) dir = "W";
    else if (deg >= 292.5f && deg < 337.5f) dir = "NW";

    if (dist < 1.0f)
        snprintf(out, outSize, "%dm %s", (int)(dist * 1000.0f), dir);
    else
        snprintf(out, outSize, "%.1fkm %s", dist, dir);
    return true;
}

extern "C" bool emoji_logger_enabled(void) __attribute__((weak));

extern "C" void emoji_log_message_to_sd(const char *sender, const char *msg)
{
    if (!msg || !msg[0]) return;
    if (emoji_logger_enabled && !emoji_logger_enabled()) return;
#ifdef HAS_SDCARD
    ISpiLock::Guard bus;
    FsFile f = SDFs.open("/chat_log.txt", O_WRONLY | O_CREAT | O_APPEND);
    if (f) {
        if (sender && sender[0]) {
            f.print("[");
            f.print(sender);
            f.print("]: ");
        } else {
            f.print("[You]: ");
        }
        f.println(msg);
        f.close();
    }
#endif
}

static lv_obj_t *g_topWifiIcon = nullptr;
extern "C" void emoji_top_wifi_update(bool connected, lv_obj_t *parent)
{
    if (!parent) return;
    if (!g_topWifiIcon) {
        g_topWifiIcon = lv_label_create(parent);
        lv_label_set_text(g_topWifiIcon, LV_SYMBOL_WIFI);
        lv_obj_set_style_text_color(g_topWifiIcon, lv_color_hex(0x38bdf8), 0);
        lv_obj_set_style_text_font(g_topWifiIcon, &ui_font_montserrat_12, 0);
        lv_obj_set_style_align(g_topWifiIcon, LV_ALIGN_RIGHT_MID, 0);
        lv_obj_set_pos(g_topWifiIcon, -70, 0);
    }
    if (connected)
        lv_obj_clear_flag(g_topWifiIcon, LV_OBJ_FLAG_HIDDEN);
    else
        lv_obj_add_flag(g_topWifiIcon, LV_OBJ_FLAG_HIDDEN);
}

void TFTView_320x240::emoji_traceroute(uint32_t to, uint8_t ch)
{
    if (!to || !THIS || !THIS->controller) return;
    uint8_t hopLimit = THIS->db.config.lora.hop_limit ? THIS->db.config.lora.hop_limit : 3;
    uint32_t reqId = THIS->requests.addRequest(to, ResponseHandler::TraceRouteRequest);
    THIS->controller->traceRoute(to, ch, hopLimit, reqId);
}

extern "C" void emoji_trigger_traceroute(uint32_t toNode, uint8_t ch)
{
    TFTView_320x240::emoji_traceroute(toNode, ch);
}

void TFTView_320x240::emoji_open_node_chat_impl(uint32_t nodeNum)
{
    if (THIS && nodeNum) {
        THIS->showMessages(nodeNum);
    }
}

uint32_t TFTView_320x240::emoji_find_node_by_name_impl(const char *shortName, const char *longName)
{
    if (!THIS) return 0;
    for (auto const &[num, p] : THIS->nodes) {
        if (!p) continue;
        lv_obj_t *sLbl = p->LV_OBJ_IDX(node_lbs_idx);
        lv_obj_t *lLbl = p->LV_OBJ_IDX(node_lbl_idx);
        const char *s = sLbl ? lv_label_get_text(sLbl) : "";
        const char *l = lLbl ? lv_label_get_text(lLbl) : "";
        if (shortName && s && strcasecmp(s, shortName) == 0) return num;
        if (longName && l && strcasecmp(l, longName) == 0) return num;
    }
    return 0;
}

extern "C" void emoji_open_node_chat(uint32_t nodeNum)
{
    TFTView_320x240::emoji_open_node_chat_impl(nodeNum);
}

extern "C" uint32_t emoji_find_node_by_name(const char *shortName, const char *longName)
{
    return TFTView_320x240::emoji_find_node_by_name_impl(shortName, longName);
}
"""
    edit(tft, "void TFTView_320x240::ui_set_active(lv_obj_t *b, lv_obj_t *p, lv_obj_t *tp)\n{",
         decl_block, "before")

    set_active_sb = (
        '    emoji_top_wifi_update(db.connectionStatus.has_wifi && db.connectionStatus.wifi.has_status && db.connectionStatus.wifi.status.is_connected, objects.battery_panel);\n'
        '    if (g_node_search_bar) {\n'
        '        if (p == objects.nodes_panel)\n'
        '            lv_obj_clear_flag(g_node_search_bar, LV_OBJ_FLAG_HIDDEN);\n'
        '        else {\n'
        '            lv_obj_add_flag(g_node_search_bar, LV_OBJ_FLAG_HIDDEN);\n'
        '            if (objects.keyboard)\n'
        '                lv_obj_add_flag(objects.keyboard, LV_OBJ_FLAG_HIDDEN);\n'
        '        }\n'
        '    }\n'
    )
    edit(tft, "    lv_obj_clear_flag(p, LV_OBJ_FLAG_HIDDEN);\n", set_active_sb, "after")

    hotfix_extras = (
        '    // Responsive scaling for all settings modal dialogs:\n'
        '    // Prevents keyboard buttons from being stripped at x=224 and OK/Cancel colliding with bottom frame\n'
        '    uint32_t dlg_w = (h >= 360) ? ((h * 90) / 100) : (h - 20);\n'
        '    if (dlg_w > 440) dlg_w = 440;\n'
        '    lv_obj_t *dialogs[] = {\n'
        '        objects.settings_reboot_panel, objects.settings_username_panel, objects.settings_region_panel,\n'
        '        objects.settings_modem_preset_panel, objects.settings_device_role_panel, objects.settings_wifi_panel,\n'
        '        objects.settings_brightness_panel, objects.settings_theme_panel, objects.settings_screen_timeout_panel,\n'
        '        objects.settings_screen_lock_panel, objects.settings_input_control_panel, objects.settings_alert_buzzer_panel,\n'
        '        objects.settings_language_panel, objects.settings_backup_restore_panel, objects.settings_reset_panel,\n'
        '        objects.settings_modify_channel_panel\n'
        '    };\n'
        '    for (lv_obj_t *d : dialogs) {\n'
        '        if (!d) continue;\n'
        '        lv_obj_set_width(d, dlg_w);\n'
        '        int32_t cur_h = lv_obj_get_height(d);\n'
        '        if (v >= 600) {\n'
        '            if (cur_h <= 130) lv_obj_set_height(d, 180);\n'
        '            else if (cur_h <= 175) lv_obj_set_height(d, 235);\n'
        '            else if (cur_h <= 185) lv_obj_set_height(d, 255);\n'
        '        }\n'
        '        for (uint32_t i = 0; i < lv_obj_get_child_count(d); i++) {\n'
        '            lv_obj_t *ch = lv_obj_get_child(d, i);\n'
        '            if (ch && lv_obj_check_type(ch, &lv_textarea_class))\n'
        '                lv_obj_set_width(ch, dlg_w - 60);\n'
        '            if (ch && lv_obj_check_type(ch, &lv_button_class)) {\n'
        '                if (lv_obj_get_x(ch) > 180) {\n'
        '                    lv_obj_set_pos(ch, dlg_w - 48, lv_obj_get_y(ch));\n'
        '                    lv_obj_set_size(ch, 36, 30);\n'
        '                }\n'
        '            }\n'
        '        }\n'
        '    }\n'
        '    if (!g_node_search_bar && objects.main_screen) {\n'
        '        uint32_t top_h = objects.top_nodes_panel ? lv_obj_get_height(objects.top_nodes_panel) : 0;\n'
        '        if (top_h == 0) top_h = (v * 10) / 100;\n'
        '        uint32_t sb_h = (v >= 600) ? 46 : ((v >= 360) ? 36 : 28);\n'
        '        g_node_search_bar = lv_obj_create(objects.main_screen);\n'
        '        lv_obj_set_pos(g_node_search_bar, 0, top_h);\n'
        '        lv_obj_set_size(g_node_search_bar, LV_PCT(100), sb_h);\n'
        '        lv_obj_add_flag(g_node_search_bar, LV_OBJ_FLAG_HIDDEN);\n'
        '        lv_obj_clear_flag(g_node_search_bar, LV_OBJ_FLAG_SCROLLABLE);\n'
        '        lv_obj_set_style_bg_color(g_node_search_bar, colorDarkGray, LV_PART_MAIN);\n'
        '        lv_obj_set_style_border_width(g_node_search_bar, 0, LV_PART_MAIN);\n'
        '        lv_obj_set_style_pad_all(g_node_search_bar, 2, LV_PART_MAIN);\n'
        '        lv_obj_set_style_pad_column(g_node_search_bar, 4, LV_PART_MAIN);\n'
        '        lv_obj_set_style_radius(g_node_search_bar, 0, LV_PART_MAIN);\n'
        '        lv_obj_set_layout(g_node_search_bar, LV_LAYOUT_FLEX);\n'
        '        lv_obj_set_flex_flow(g_node_search_bar, LV_FLEX_FLOW_ROW);\n'
        '        lv_obj_set_flex_align(g_node_search_bar, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);\n'
        '        g_node_search_ta = lv_textarea_create(g_node_search_bar);\n'
        '        lv_obj_set_flex_grow(g_node_search_ta, 1);\n'
        '        lv_obj_set_height(g_node_search_ta, sb_h - 4);\n'
        '        lv_textarea_set_placeholder_text(g_node_search_ta, "Search nodes or !id...");\n'
        '        lv_textarea_set_one_line(g_node_search_ta, true);\n'
        '        lv_obj_set_style_text_font(g_node_search_ta, (v >= 600) ? &ui_font_montserrat_14 : &ui_font_montserrat_12, LV_PART_MAIN);\n'
        '        lv_obj_set_style_pad_top(g_node_search_ta, (v >= 600) ? 6 : 2, LV_PART_MAIN);\n'
        '        lv_obj_set_style_pad_left(g_node_search_ta, 8, LV_PART_MAIN);\n'
        '        lv_obj_set_style_pad_bottom(g_node_search_ta, 4, LV_PART_MAIN);\n'
        '        lv_obj_set_style_bg_color(g_node_search_ta, lv_color_hex(0x181818), LV_PART_MAIN);\n'
        '        lv_obj_set_style_text_color(g_node_search_ta, lv_color_hex(0xffffff), LV_PART_MAIN);\n'
        '        lv_obj_set_style_border_color(g_node_search_ta, colorMesh, LV_PART_MAIN);\n'
        '        lv_obj_set_style_border_width(g_node_search_ta, 1, LV_PART_MAIN);\n'
        '        lv_obj_set_style_radius(g_node_search_ta, 6, LV_PART_MAIN);\n'
        '        lv_obj_add_event_cb(g_node_search_ta, ui_event_search_ta, LV_EVENT_ALL, this);\n'
        '        lv_obj_t *btn_kb = lv_button_create(g_node_search_bar);\n'
        '        lv_obj_set_size(btn_kb, (v >= 600) ? 44 : 34, sb_h - 4);\n'
        '        lv_obj_set_style_radius(btn_kb, 6, LV_PART_MAIN);\n'
        '        lv_obj_set_style_bg_color(btn_kb, lv_color_hex(0x2d2d2d), LV_PART_MAIN);\n'
        '        lv_obj_set_style_bg_image_src(btn_kb, &img_keyboard_image, LV_PART_MAIN);\n'
        '        lv_obj_set_style_bg_image_recolor(btn_kb, lv_color_hex(0xffffff), LV_PART_MAIN);\n'
        '        lv_obj_set_style_bg_image_recolor_opa(btn_kb, 255, LV_PART_MAIN);\n'
        '        lv_obj_add_event_cb(btn_kb, ui_event_search_kb, LV_EVENT_CLICKED, this);\n'
        '    }\n'
        '    if (objects.nodes_panel) {\n'
        '        uint32_t top_h = objects.top_nodes_panel ? lv_obj_get_height(objects.top_nodes_panel) : 0;\n'
        '        if (top_h == 0) top_h = (v * 10) / 100;\n'
        '        uint32_t sb_h = (v >= 600) ? 46 : ((v >= 360) ? 36 : 28);\n'
        '        int32_t nav_h = objects.button_panel ? lv_obj_get_height(objects.button_panel) : 0;\n'
        '        if (nav_h <= 0) nav_h = (v * 12) / 100;\n'
        '        lv_obj_set_y(objects.nodes_panel, top_h + sb_h);\n'
        '        int32_t rem_h = v - (top_h + sb_h) - nav_h;\n'
        '        if (rem_h > 60) lv_obj_set_height(objects.nodes_panel, rem_h);\n'
        '    }\n'
        '    if (objects.message_input_area && objects.keyboard_button_0) {\n'
        '        uint32_t bottom_pad = (v >= 600) ? 8 : 4;\n'
        '        uint32_t btn_h = (v >= 600) ? 40 : 28;\n'
        '        uint32_t btn_w = (v >= 600) ? 46 : 34;\n'
        '        int32_t margin_x = (int32_t)bottom_pad + 2;\n'
        '        lv_obj_set_pos(objects.keyboard_button_0, -margin_x, -(int32_t)bottom_pad);\n'
        '        lv_obj_set_size(objects.keyboard_button_0, btn_w, btn_h);\n'
        '        lv_obj_set_style_radius(objects.keyboard_button_0, 6, LV_PART_MAIN);\n'
        '        int32_t ta_w = (int32_t)h - margin_x - 8 - btn_w - margin_x;\n'
        '        if (ta_w > 80) {\n'
        '            lv_obj_set_size(objects.message_input_area, ta_w, btn_h);\n'
        '            lv_obj_set_pos(objects.message_input_area, margin_x, -(int32_t)bottom_pad);\n'
        '            lv_obj_set_style_radius(objects.message_input_area, 6, LV_PART_MAIN);\n'
        '            lv_obj_set_style_max_height(objects.message_input_area, 100, LV_PART_MAIN);\n'
        '            lv_obj_set_style_pad_top(objects.message_input_area, (v >= 600) ? 8 : 3, LV_PART_MAIN);\n'
        '            lv_obj_set_style_pad_left(objects.message_input_area, 8, LV_PART_MAIN);\n'
        '            lv_obj_set_style_pad_bottom(objects.message_input_area, 4, LV_PART_MAIN);\n'
        '            lv_obj_set_style_text_font(objects.message_input_area, (v >= 600) ? &ui_font_montserrat_14 : &ui_font_montserrat_12, LV_PART_MAIN);\n'
        '        }\n'
        '        if (objects.messages_panel && objects.messages_container) {\n'
        '            int32_t p_h = lv_obj_get_height(objects.messages_panel);\n'
        '            if (p_h > (int32_t)(btn_h + bottom_pad + 20))\n'
        '                lv_obj_set_height(objects.messages_container, p_h - (btn_h + bottom_pad + 6));\n'
        '        }\n'
        '    }\n'
    )
    edit(tft, "    if (objects.blank_screen)\n        lv_obj_set_size(objects.blank_screen, h, v);\n",
         hotfix_extras, "after")

    # Own node detail label and max height
    own_add = (
        '    lv_obj_set_style_max_height(objects.node_button, 220, ((lv_style_selector_t)LV_PART_MAIN | (lv_style_selector_t)LV_STATE_DEFAULT));\n'
        '    lv_obj_t *own_detail_lbl = lv_label_create(objects.node_panel);\n'
        '    lv_obj_set_pos(own_detail_lbl, -5, 53);\n'
        '    lv_obj_set_size(own_detail_lbl, LV_PCT(100), LV_SIZE_CONTENT);\n'
        '    lv_label_set_long_mode(own_detail_lbl, LV_LABEL_LONG_WRAP);\n'
        '    lv_obj_set_style_text_font(own_detail_lbl, &ui_font_montserrat_12, ((lv_style_selector_t)LV_PART_MAIN | (lv_style_selector_t)LV_STATE_DEFAULT));\n'
        '    lv_obj_set_style_text_color(own_detail_lbl, lv_color_hex(0xc0c0c0), ((lv_style_selector_t)LV_PART_MAIN | (lv_style_selector_t)LV_STATE_DEFAULT));\n'
        '    lv_obj_set_style_text_line_space(own_detail_lbl, 2, ((lv_style_selector_t)LV_PART_MAIN | (lv_style_selector_t)LV_STATE_DEFAULT));\n'
        '    lv_obj_add_flag(own_detail_lbl, LV_OBJ_FLAG_HIDDEN);\n'
    )
    edit(tft, "lv_obj_add_event_cb(objects.node_button, ui_event_NodeButton, LV_EVENT_ALL, (void *)ownNode);\n",
         own_add, "after")

    # addNode detail label and max height
    edit(tft, (
        "    lv_obj_set_style_max_height(nodeButton, 132, ((lv_style_selector_t)LV_PART_MAIN | (lv_style_selector_t)LV_STATE_DEFAULT));",
        "    lv_obj_set_style_max_height(nodeButton, 132, LV_PART_MAIN | LV_STATE_DEFAULT);"
    ), "    lv_obj_set_style_max_height(nodeButton, 220, ((lv_style_selector_t)LV_PART_MAIN | (lv_style_selector_t)LV_STATE_DEFAULT));", "replace")

    add_detail_block = (
        '    lv_obj_t *detail_lbl = lv_label_create(p);\n'
        '    lv_obj_set_pos(detail_lbl, -5, 53);\n'
        '    lv_obj_set_size(detail_lbl, LV_PCT(100), LV_SIZE_CONTENT);\n'
        '    lv_label_set_long_mode(detail_lbl, LV_LABEL_LONG_WRAP);\n'
        '    lv_obj_set_style_text_font(detail_lbl, &ui_font_montserrat_12, ((lv_style_selector_t)LV_PART_MAIN | (lv_style_selector_t)LV_STATE_DEFAULT));\n'
        '    lv_obj_set_style_text_color(detail_lbl, lv_color_hex(0xc0c0c0), ((lv_style_selector_t)LV_PART_MAIN | (lv_style_selector_t)LV_STATE_DEFAULT));\n'
        '    lv_obj_set_style_text_line_space(detail_lbl, 2, ((lv_style_selector_t)LV_PART_MAIN | (lv_style_selector_t)LV_STATE_DEFAULT));\n'
        '    lv_obj_add_flag(detail_lbl, LV_OBJ_FLAG_HIDDEN);\n'
    )
    edit(tft, "    lv_obj_add_event_cb(nodeButton, ui_event_NodeButton, LV_EVENT_ALL, (void *)nodeNum);\n",
         add_detail_block, "before")

    # ui_event_NodeButton replacement
    old_event_btn = (
        'void TFTView_320x240::ui_event_NodeButton(lv_event_t *e)\n'
        '{\n'
        '    static bool animRunning = false;\n'
        '    static auto deleted_cb = [](_lv_anim_t *) { animRunning = false; };\n'
        '    lv_event_code_t event_code = lv_event_get_code(e);\n'
        '    if (event_code == LV_EVENT_CLICKED && !animRunning) {\n'
        '        uint32_t nodeNum = (unsigned long)e->user_data;\n'
        '        if (!nodeNum) // event-handler for own node has value 0 in user_data\n'
        '            nodeNum = THIS->ownNode;\n'
        '        lv_obj_t *panel = THIS->nodes[nodeNum];\n'
        '        if (currentPanel) {\n'
        '            // create animation to shrink other panel\n'
        '            animRunning = true;\n'
        '            static lv_anim_t a;\n'
        '            int32_t height = lv_obj_get_height(currentPanel);\n'
        '            lv_anim_init(&a);\n'
        '            lv_anim_set_var(&a, currentPanel);\n'
        '            lv_anim_set_values(&a, height, 136 - height);\n'
        '            lv_anim_set_duration(&a, 200);\n'
        '            lv_anim_set_exec_cb(&a, ui_anim_node_panel_cb);\n'
        '            lv_anim_set_path_cb(&a, lv_anim_path_linear);\n'
        '            lv_anim_set_deleted_cb(&a, deleted_cb);\n'
        '            lv_anim_start(&a);\n'
        '        }\n'
        '        if (panel != currentPanel) {\n'
        '            // create animation to enlarge node panel\n'
        '            animRunning = true;\n'
        '            static lv_anim_t a;\n'
        '            int32_t height = lv_obj_get_height(panel);\n'
        '            lv_anim_init(&a);\n'
        '            lv_anim_set_var(&a, panel);\n'
        '            lv_anim_set_values(&a, height, 136 - height);\n'
        '            lv_anim_set_duration(&a, 200);\n'
        '            lv_anim_set_exec_cb(&a, ui_anim_node_panel_cb);\n'
        '            lv_anim_set_path_cb(&a, lv_anim_path_linear);\n'
        '            lv_anim_set_deleted_cb(&a, deleted_cb);\n'
        '            lv_anim_start(&a);\n'
        '            currentPanel = panel;\n'
        '            currentNode = nodeNum;\n'
        '        } else {\n'
        '            currentPanel = nullptr;\n'
        '            currentNode = 0;\n'
        '        }\n'
        '        if (THIS->chooseNodeSignalScanner) {\n'
        '            THIS->chooseNodeSignalScanner = false;\n'
        '            ui_event_signal_scanner(NULL);\n'
        '            // restore previous filter\n'
        '            lv_dropdown_set_selected(objects.nodes_filter_hops_dropdown, THIS->selectedHops);\n'
        '            THIS->updateNodesFiltered(true);\n'
        '            THIS->updateNodesStatus();\n'
        '        } else if (THIS->chooseNodeTraceRoute) {\n'
        '            THIS->chooseNodeTraceRoute = false;\n'
        '            ui_event_trace_route(NULL);\n'
        '        }\n'
        '    } else if (event_code == LV_EVENT_LONG_PRESSED) {\n'
        '        //  set color and text of clicked node\n'
        '        uint32_t nodeNum = (unsigned long)e->user_data;\n'
        '        bool isMessagable = !((unsigned long)(THIS->nodes[nodeNum]->LV_OBJ_IDX(node_img_idx)->user_data) == eRole::unmessagable);\n'
        '        if (nodeNum != THIS->ownNode && isMessagable)\n'
        '            THIS->showMessages(nodeNum);\n'
        '    }\n'
        '}'
    )
    new_event_btn = (
        'void TFTView_320x240::ui_event_NodeButton(lv_event_t *e)\n'
        '{\n'
        '    static bool ignoreClicked = false;\n'
        '    lv_event_code_t event_code = lv_event_get_code(e);\n'
        '    if (event_code == LV_EVENT_CLICKED) {\n'
        '        if (ignoreClicked) {\n'
        '            ignoreClicked = false;\n'
        '            return;\n'
        '        }\n'
        '        uint32_t nodeNum = (unsigned long)e->user_data;\n'
        '        if (!nodeNum)\n'
        '            nodeNum = THIS->ownNode;\n'
        '        auto it = THIS->nodes.find(nodeNum);\n'
        '        lv_obj_t *panel = (it != THIS->nodes.end()) ? it->second : nullptr;\n'
        '        if (!panel) return;\n'
        '        if (currentPanel && currentPanel != panel) {\n'
        '            lv_obj_set_height(currentPanel, 53);\n'
        '            if (lv_obj_get_child_count(currentPanel) > 11)\n'
        '                lv_obj_add_flag(lv_obj_get_child(currentPanel, 11), LV_OBJ_FLAG_HIDDEN);\n'
        '            currentPanel = nullptr;\n'
        '            currentNode = 0;\n'
        '        }\n'
        '        bool isExpanded = (lv_obj_get_height(panel) > 60);\n'
        '        if (isExpanded) {\n'
        '            lv_obj_set_height(panel, 53);\n'
        '            if (lv_obj_get_child_count(panel) > 11)\n'
        '                lv_obj_add_flag(lv_obj_get_child(panel, 11), LV_OBJ_FLAG_HIDDEN);\n'
        '            currentPanel = nullptr;\n'
        '            currentNode = 0;\n'
        '        } else {\n'
        '            currentPanel = panel;\n'
        '            currentNode = nodeNum;\n'
        '            for (int idx = 7; idx <= 10; idx++) {\n'
        '                if (lv_obj_get_child_count(panel) > idx)\n'
        '                    lv_obj_add_flag(lv_obj_get_child(panel, idx), LV_OBJ_FLAG_HIDDEN);\n'
        '            }\n'
        '            if (lv_obj_get_child_count(panel) > 11) {\n'
        '                lv_obj_t *dl = lv_obj_get_child(panel, 11);\n'
        '                char idStr[64] = {0}, rmStr[64] = {0}, bsStr[64] = {0}, gpsStr[64] = {0};\n'
        '                get_node_details_string(nodeNum, idStr, sizeof(idStr), rmStr, sizeof(rmStr), bsStr, sizeof(bsStr), gpsStr, sizeof(gpsStr));\n'
        '                char fullBuf[320];\n'
        '                snprintf(fullBuf, sizeof(fullBuf), "%s\\n%s\\n%s\\n%s", idStr, rmStr, bsStr, gpsStr);\n'
        '                lv_label_set_text(dl, fullBuf);\n'
        '                lv_obj_clear_flag(dl, LV_OBJ_FLAG_HIDDEN);\n'
        '            }\n'
        '            lv_obj_set_height(panel, 142);\n'
        '        }\n'
        '        if (THIS->chooseNodeSignalScanner) {\n'
        '            THIS->chooseNodeSignalScanner = false;\n'
        '            ui_event_signal_scanner(NULL);\n'
        '            lv_dropdown_set_selected(objects.nodes_filter_hops_dropdown, THIS->selectedHops);\n'
        '            THIS->updateNodesFiltered(true);\n'
        '            THIS->updateNodesStatus();\n'
        '        } else if (THIS->chooseNodeTraceRoute) {\n'
        '            THIS->chooseNodeTraceRoute = false;\n'
        '            ui_event_trace_route(NULL);\n'
        '        }\n'
        '    } else if (event_code == LV_EVENT_LONG_PRESSED) {\n'
        '        ignoreClicked = true;\n'
        '        uint32_t nodeNum = (unsigned long)e->user_data;\n'
        '        if (!nodeNum)\n'
        '            nodeNum = THIS->ownNode;\n'
        '        if (nodeNum != THIS->ownNode) {\n'
        '            auto it = THIS->nodes.find(nodeNum);\n'
        '            if (it != THIS->nodes.end()) {\n'
        '                bool isMessagable = !((unsigned long)(it->second->LV_OBJ_IDX(node_img_idx)->user_data) == eRole::unmessagable);\n'
        '                if (isMessagable)\n'
        '                    THIS->showMessages(nodeNum);\n'
        '            }\n'
        '        }\n'
        '    }\n'
        '}'
    )
    edit(tft, old_event_btn, new_event_btn, "replace")

    # Real-time search filter matching
    old_filter = (
        '        const char *name = lv_textarea_get_text(objects.nodes_filter_name_area);\n'
        '        if (name[0] != \'\\0\') {\n'
        '            if (name[0] != \'!\') { // use \'!\' char to negate search result\n'
        '                if (!strcasestr(lv_label_get_text(panel->LV_OBJ_IDX(node_lbl_idx)), name) &&\n'
        '                    !strcasestr(lv_label_get_text(panel->LV_OBJ_IDX(node_lbs_idx)), name)) {\n'
        '                    hide = true;\n'
        '                }\n'
        '            } else {\n'
        '                if (strcasestr(lv_label_get_text(panel->LV_OBJ_IDX(node_lbl_idx)), &name[1]) ||\n'
        '                    strcasestr(lv_label_get_text(panel->LV_OBJ_IDX(node_lbs_idx)), &name[1])) {\n'
        '                    hide = true;\n'
        '                }\n'
        '            }\n'
        '        }'
    )
    new_filter = (
        '        const char *name = lv_textarea_get_text(objects.nodes_filter_name_area);\n'
        '        if (name && name[0] != \'\\0\') {\n'
        '            const char *query = (name[0] == \'!\' && strlen(name) > 1) ? &name[1] : name;\n'
        '            char hexId[16];\n'
        '            snprintf(hexId, sizeof(hexId), "%08x", (unsigned)nodeNum);\n'
        '            char bangHex[16];\n'
        '            snprintf(bangHex, sizeof(bangHex), "!%08x", (unsigned)nodeNum);\n'
        '            char decId[16];\n'
        '            snprintf(decId, sizeof(decId), "%u", (unsigned)nodeNum);\n'
        '            const char *longName = lv_label_get_text(panel->LV_OBJ_IDX(node_lbl_idx));\n'
        '            const char *shortName = lv_label_get_text(panel->LV_OBJ_IDX(node_lbs_idx));\n'
        '            bool match = (longName && strcasestr(longName, name) != nullptr) ||\n'
        '                         (shortName && strcasestr(shortName, name) != nullptr) ||\n'
        '                         (strcasestr(hexId, query) != nullptr) ||\n'
        '                         (strcasestr(bangHex, name) != nullptr) ||\n'
        '                         (strcasestr(decId, name) != nullptr);\n'
        '            if (!match && name[0] == \'!\') {\n'
        '                match = (longName && strcasestr(longName, query) != nullptr) ||\n'
        '                        (shortName && strcasestr(shortName, query) != nullptr);\n'
        '            }\n'
        '            if (!match) {\n'
        '                hide = true;\n'
        '            }\n'
        '        }'
    )
    edit(tft, old_filter, new_filter, "replace")

    # Hook channel click in Settings -> Channels:
    old_ch_click = (
        '        uint32_t btn_id = (unsigned long)e->user_data;\n'
        '        int8_t ch = (signed long)THIS->ch_label[btn_id]->user_data;\n'
        '        if (ch != -1) {'
    )
    new_ch_click = (
        '        // Intercept channel click to open rich Android-style Channel editor\n'
        '        uint32_t btn_id = (unsigned long)e->user_data;\n'
        '        int8_t ch = (signed long)THIS->ch_label[btn_id]->user_data;\n'
        '        if (ch == -1) {\n'
        '            for (int i = 0; i < c_max_channels; i++) {\n'
        '                if (THIS->channel_scratch[i].role == meshtastic_Channel_Role_DISABLED) {\n'
        '                    ch = i;\n'
        '                    break;\n'
        '                }\n'
        '            }\n'
        '            if (ch == -1) ch = btn_id;\n'
        '        }\n'
        '        emoji_channel_open_index(ch);\n'
        '        return;\n'
        '        if (ch != -1) {'
    )
    edit(tft, old_ch_click, new_ch_click, "replace")

        # Hook updatePosition to track node coordinates for distance & bearing
    edit(tft, "void TFTView_320x240::updatePosition(uint32_t nodeNum, int32_t lat, int32_t lon, int32_t alt, uint32_t sats, uint32_t precision)\n{\n",
         "void TFTView_320x240::updatePosition(uint32_t nodeNum, int32_t lat, int32_t lon, int32_t alt, uint32_t sats, uint32_t precision)\n{\n    emoji_record_node_pos(nodeNum, lat, lon, nodeNum == ownNode);\n    emoji_tools_record_pos(nodeNum, lat, lon, alt, nodeNum == ownNode);\n", "replace")

    edit(tft, "void TFTView_320x240::updateMetrics(uint32_t nodeNum, uint32_t bat_level, float voltage, float chUtil, float airUtil)\n{\n",
         "void TFTView_320x240::updateMetrics(uint32_t nodeNum, uint32_t bat_level, float voltage, float chUtil, float airUtil)\n{\n    emoji_tools_record_metrics(chUtil, airUtil);\n", "replace")

    edit(tft, "void TFTView_320x240::updateSignalStrength(uint32_t nodeNum, int32_t rssi, float snr)\n{\n",
         "void TFTView_320x240::updateSignalStrength(uint32_t nodeNum, int32_t rssi, float snr)\n{\n    emoji_tools_record_signal(nodeNum, rssi, snr);\n", "replace")

    edit(tft, "void TFTView_320x240::packetReceived(const meshtastic_MeshPacket &p)\n{\n",
         "void TFTView_320x240::packetReceived(const meshtastic_MeshPacket &p)\n{\n    emoji_tools_record_packet(false, false);\n", "replace")

    edit(tft, "void TFTView_320x240::addNode(uint32_t nodeNum, uint8_t ch, const char *userShort, const char *userLong, uint32_t lastHeard,\n                              eRole role, bool hasKey, bool unmessagable)\n{\n",
         "void TFTView_320x240::addNode(uint32_t nodeNum, uint8_t ch, const char *userShort, const char *userLong, uint32_t lastHeard,\n                              eRole role, bool hasKey, bool unmessagable)\n{\n    emoji_tools_record_node(nodeNum, userShort, userLong, lastHeard);\n", "replace")

    # Auto-capture Wi-Fi into the vault on every save, also when the entered credentials equal the ones already in use
    # (an earlier version of this patch put the call inside the "credentials changed" branch and duplicated the strcpy line)
    _t, _crlf = read(tft)
    _stale = ("strcpy(THIS->db.config.network.wifi_psk, psk);\n"
              "strcpy(THIS->db.config.network.wifi_psk, psk);\n            emoji_wifi_vault_add(ssid, psk);\n")
    if _stale in _t:
        write(tft, _t.replace(_stale, "strcpy(THIS->db.config.network.wifi_psk, psk);\n", 1), _crlf)
        print("Cleaned stale Wi-Fi vault patch in", tft)
    edit(tft, '            lv_snprintf(buf, sizeof(buf), _("WiFi: %s"), ssid[0] ? ssid : _("<not set>"));\n',
         "            emoji_wifi_vault_add(ssid, psk);\n", "before")

        # Log message to SD card if enabled
    edit(tft, "void TFTView_320x240::newMessage(uint32_t from, uint32_t to, uint8_t ch, const char *msg, uint32_t &msgTime, bool restore)\n{\n",
         "void TFTView_320x240::newMessage(uint32_t from, uint32_t to, uint8_t ch, const char *msg, uint32_t &msgTime, bool restore)\n{\n    if (!restore) { auto itlog = nodes.find(from); emoji_log_message_to_sd(itlog != nodes.end() ? lv_label_get_text(itlog->second->LV_OBJ_IDX(node_lbl_idx)) : \"\", msg); }\n", "replace")

    # Top bar Wi-Fi icon status update
    edit(tft, "void TFTView_320x240::updateConnectionStatus(const meshtastic_DeviceConnectionStatus &status)\n{\n    db.connectionStatus = status;\n",
         "void TFTView_320x240::updateConnectionStatus(const meshtastic_DeviceConnectionStatus &status)\n{\n    db.connectionStatus = status;\n    emoji_top_wifi_update(status.has_wifi && status.wifi.has_status && status.wifi.status.is_connected, objects.battery_panel);\n", "replace")

    # Chat message delivery status UX (Green = Acked, Yellow = Delivered to mesh, Red = Failed + [!] retry/delete modal)
    helpers = """// Delivery status frame colors:
// - Green: Delivered / Confirmed ACK (or group broadcast sent)
// - Yellow: Delivered to mesh (relayed / awaiting recipient ACK in direct message)
// - Red: Failed (NAK, max retransmits, timeout) with clickable [!] retry/delete badge
static const lv_color_t colorDeliveryGreen = LV_COLOR_HEX(0x22c55e);  // 0x22C55E
static const lv_color_t colorDeliveryYellow = LV_COLOR_HEX(0xeab308); // 0xEAB308
static const lv_color_t colorDeliveryRed = LV_COLOR_HEX(0xef4444);    // 0xEF4444

void TFTView_320x240::remove_failed_message_badge(lv_obj_t *panel)
{
    if (!panel || !panel->spec_attr) return;
    for (uint32_t c = 1; c < panel->spec_attr->child_cnt; c++) {
        lv_obj_t *child = panel->spec_attr->children[c];
        if (child && (uintptr_t)child->user_data == 0xDEADBEEF) {
            lv_obj_del(child);
            break;
        }
    }
}

void TFTView_320x240::failed_popup_cancel_cb(lv_event_t *e)
{
    lv_obj_t *modal = (lv_obj_t *)lv_event_get_user_data(e);
    if (modal) lv_obj_del(modal);
}

void TFTView_320x240::failed_popup_delete_cb(lv_event_t *e)
{
    lv_obj_t *modal = (lv_obj_t *)lv_event_get_user_data(e);
    if (modal) {
        lv_obj_t *panel = (lv_obj_t *)modal->user_data;
        if (panel) lv_obj_del(panel);
        lv_obj_del(modal);
    }
}

void TFTView_320x240::failed_popup_retry_cb(lv_event_t *e)
{
    lv_obj_t *modal = (lv_obj_t *)lv_event_get_user_data(e);
    if (!modal) return;
    lv_obj_t *panel = (lv_obj_t *)modal->user_data;
    if (!panel) {
        lv_obj_del(modal);
        return;
    }

    lv_obj_t *container = lv_obj_get_parent(panel);
    lv_obj_t *textLabel = (panel->spec_attr && panel->spec_attr->child_cnt > 0) ? panel->spec_attr->children[0] : nullptr;
    const char *full = textLabel ? lv_label_get_text(textLabel) : "";
    const char *body = strchr(full, '\\n');
    body = body ? (body + 1) : full;
    char retryBuf[256];
    snprintf(retryBuf, sizeof(retryBuf), "%s", body);

    lv_obj_del(panel);
    lv_obj_del(modal);

    if (THIS && container && retryBuf[0]) {
        lv_obj_t *prevActive = THIS->activeMsgContainer;
        THIS->activeMsgContainer = container;
        THIS->handleAddMessage(retryBuf);
        THIS->activeMsgContainer = prevActive;
    }
}

void TFTView_320x240::modal_backdrop_cb(lv_event_t *e)
{
    lv_obj_t *target = (lv_obj_t *)lv_event_get_target(e);
    lv_obj_t *modal = (lv_obj_t *)lv_event_get_user_data(e);
    if (target == modal) {
        lv_obj_del(modal);
    }
}

void TFTView_320x240::show_failed_message_popup(lv_obj_t *panel)
{
    lv_obj_t *top = lv_layer_top();
    lv_obj_t *modal = lv_obj_create(top);
    lv_obj_remove_style_all(modal);
    lv_obj_set_size(modal, LV_PCT(100), LV_PCT(100));
    lv_obj_set_style_bg_color(modal, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(modal, LV_OPA_60, 0);
    lv_obj_clear_flag(modal, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(modal, LV_OBJ_FLAG_CLICKABLE);
    modal->user_data = panel;
    lv_obj_add_event_cb(modal, modal_backdrop_cb, LV_EVENT_CLICKED, modal);

    lv_obj_t *card = lv_obj_create(modal);
    lv_obj_set_width(card, 210);
    lv_obj_set_height(card, LV_SIZE_CONTENT);
    lv_obj_center(card);
    lv_obj_set_style_radius(card, 8, 0);
    lv_obj_set_style_bg_color(card, lv_color_hex(0x1E293B), 0);
    lv_obj_set_style_border_color(card, lv_color_hex(0x475569), 0);
    lv_obj_set_style_border_width(card, 1, 0);
    lv_obj_set_style_pad_all(card, 12, 0);
    lv_obj_set_flex_flow(card, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_flex_align(card, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_row(card, 8, 0);

    lv_obj_t *title = lv_label_create(card);
    lv_label_set_text(title, "Message Failed");
    lv_obj_set_style_text_color(title, colorDeliveryRed, 0);
    lv_obj_set_style_text_font(title, &ui_font_montserrat_14, 0);

    // Retry Button
    lv_obj_t *btnRetry = lv_btn_create(card);
    lv_obj_set_size(btnRetry, 180, 32);
    lv_obj_set_style_radius(btnRetry, 6, 0);
    lv_obj_set_style_bg_color(btnRetry, lv_color_hex(0x16A34A), 0);
    lv_obj_t *lblRetry = lv_label_create(btnRetry);
    lv_label_set_text(lblRetry, "Retry");
    lv_obj_center(lblRetry);
    lv_obj_add_event_cb(btnRetry, failed_popup_retry_cb, LV_EVENT_CLICKED, modal);

    // Delete Button
    lv_obj_t *btnDel = lv_btn_create(card);
    lv_obj_set_size(btnDel, 180, 32);
    lv_obj_set_style_radius(btnDel, 6, 0);
    lv_obj_set_style_bg_color(btnDel, lv_color_hex(0xDC2626), 0);
    lv_obj_t *lblDel = lv_label_create(btnDel);
    lv_label_set_text(lblDel, "Delete");
    lv_obj_center(lblDel);
    lv_obj_add_event_cb(btnDel, failed_popup_delete_cb, LV_EVENT_CLICKED, modal);

    // Cancel Button
    lv_obj_t *btnCancel = lv_btn_create(card);
    lv_obj_set_size(btnCancel, 180, 28);
    lv_obj_set_style_radius(btnCancel, 6, 0);
    lv_obj_set_style_bg_color(btnCancel, lv_color_hex(0x4B5563), 0);
    lv_obj_t *lblCancel = lv_label_create(btnCancel);
    lv_label_set_text(lblCancel, "Cancel");
    lv_obj_center(lblCancel);
    lv_obj_add_event_cb(btnCancel, failed_popup_cancel_cb, LV_EVENT_CLICKED, modal);
}

void TFTView_320x240::fail_badge_click_cb(lv_event_t *e)
{
    lv_obj_t *panel = (lv_obj_t *)lv_event_get_user_data(e);
    if (panel) show_failed_message_popup(panel);
}

void TFTView_320x240::attach_failed_message_badge(lv_obj_t *panel, lv_obj_t *textLabel)
{
    if (!panel || !textLabel) return;
    if (panel->spec_attr) {
        for (uint32_t c = 1; c < panel->spec_attr->child_cnt; c++) {
            lv_obj_t *child = panel->spec_attr->children[c];
            if (child && (uintptr_t)child->user_data == 0xDEADBEEF) {
                return;
            }
        }
    }

    lv_obj_t *badge = lv_btn_create(panel);
    badge->user_data = (void *)(uintptr_t)0xDEADBEEF;
    lv_obj_remove_style_all(badge);
    lv_obj_set_size(badge, 22, 22);
    lv_obj_set_style_radius(badge, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_color(badge, colorDeliveryRed, 0);
    lv_obj_set_style_bg_opa(badge, LV_OPA_COVER, 0);
    lv_obj_update_layout(textLabel);
    lv_obj_align_to(badge, textLabel, LV_ALIGN_OUT_LEFT_MID, -6, 0);

    lv_obj_t *bLbl = lv_label_create(badge);
    lv_label_set_text(bLbl, "!");
    lv_obj_set_style_text_color(bLbl, lv_color_white(), 0);
    lv_obj_set_style_text_font(bLbl, &ui_font_montserrat_14, 0);
    lv_obj_center(bLbl);

    lv_obj_add_event_cb(badge, fail_badge_click_cb, LV_EVENT_CLICKED, panel);
}

"""
    if os.path.exists(tft):
        s_tft, crlf_tft = read(tft)
        idx_h_start = s_tft.find('// Delivery status frame colors:')
        idx_h_end = s_tft.find('/**\n * display message that has just been written and sent out\n */\nvoid TFTView_320x240::addMessage(')
        if idx_h_start != -1 and idx_h_end != -1 and idx_h_start < idx_h_end:
            s_tft = s_tft[:idx_h_start] + s_tft[idx_h_end:]
            write(tft, s_tft, crlf_tft)

    edit(tft, "/**\n * display message that has just been written and sent out\n */\nvoid TFTView_320x240::addMessage(", helpers + "/**\n * display message that has just been written and sent out\n */\nvoid TFTView_320x240::addMessage(", "replace")

    # a delivery answer with request id 0 matched the newest received bubble (its panel has no request id) and framed it red
    edit(tft, "        if (requestId == id) {\n            lv_obj_t *textLabel = panel->spec_attr->children[0];",
         "        if (id != 0 && requestId == id) {\n            lv_obj_t *textLabel = panel->spec_attr->children[0];", "replace")

    old_add_switch = """    switch (status) {
    case LogMessage::eHeard:
        lv_obj_set_style_border_color(textLabel, colorYellow,
                                      ((lv_style_selector_t)LV_PART_MAIN | (lv_style_selector_t)LV_STATE_DEFAULT));
        break;
    case LogMessage::eAcked:
        lv_obj_set_style_border_color(textLabel, colorBlueGreen,
                                      ((lv_style_selector_t)LV_PART_MAIN | (lv_style_selector_t)LV_STATE_DEFAULT));
        break;
    case LogMessage::eFailed:
        lv_obj_set_style_border_color(textLabel, colorRed,
                                      ((lv_style_selector_t)LV_PART_MAIN | (lv_style_selector_t)LV_STATE_DEFAULT));
        break;
    default:
        break;
    }"""

    new_add_switch = """    switch (status) {
    case LogMessage::eHeard:
        lv_obj_set_style_border_color(textLabel, colorDeliveryYellow,
                                      ((lv_style_selector_t)LV_PART_MAIN | (lv_style_selector_t)LV_STATE_DEFAULT));
        lv_obj_set_style_border_width(textLabel, 2,
                                      ((lv_style_selector_t)LV_PART_MAIN | (lv_style_selector_t)LV_STATE_DEFAULT));
        break;
    case LogMessage::eAcked:
        lv_obj_set_style_border_color(textLabel, colorDeliveryGreen,
                                      ((lv_style_selector_t)LV_PART_MAIN | (lv_style_selector_t)LV_STATE_DEFAULT));
        lv_obj_set_style_border_width(textLabel, 2,
                                      ((lv_style_selector_t)LV_PART_MAIN | (lv_style_selector_t)LV_STATE_DEFAULT));
        break;
    case LogMessage::eFailed:
        lv_obj_set_style_border_color(textLabel, colorDeliveryRed,
                                      ((lv_style_selector_t)LV_PART_MAIN | (lv_style_selector_t)LV_STATE_DEFAULT));
        lv_obj_set_style_border_width(textLabel, 2,
                                      ((lv_style_selector_t)LV_PART_MAIN | (lv_style_selector_t)LV_STATE_DEFAULT));
        attach_failed_message_badge(hiddenPanel, textLabel);
        break;
    default:
        break;
    }"""
    edit(tft, old_add_switch, new_add_switch, "replace")

    edit(tft, '        ILOG_DEBUG("onTextMessageCallback: timeout!");\n    }',
         '        ILOG_DEBUG("onTextMessageCallback: timeout!");\n        handleTextMessageResponse((unsigned long)req.cookie, req.id, false, true);\n    }', "replace")

    old_handle_loop = """        uint32_t requestId = (unsigned long)panel->user_data;
        if (requestId == id) {
            // now give the textlabel border another color
            lv_obj_t *textLabel = panel->spec_attr->children[0];
            lv_obj_set_style_border_color(textLabel,
                                          err   ? colorRed
                                          : ack ? colorBlueGreen
                                                : colorYellow,
                                          ((lv_style_selector_t)LV_PART_MAIN | (lv_style_selector_t)LV_STATE_DEFAULT));

            // store message
            break;
        }"""

    new_handle_loop = """        uint32_t requestId = (unsigned long)panel->user_data;
        if (requestId == id) {
            lv_obj_t *textLabel = panel->spec_attr->children[0];
            lv_color_t bCol = err ? colorDeliveryRed : (ack ? colorDeliveryGreen : colorDeliveryYellow);
            lv_obj_set_style_border_color(textLabel, bCol,
                                          ((lv_style_selector_t)LV_PART_MAIN | (lv_style_selector_t)LV_STATE_DEFAULT));
            lv_obj_set_style_border_width(textLabel, 2,
                                          ((lv_style_selector_t)LV_PART_MAIN | (lv_style_selector_t)LV_STATE_DEFAULT));

            if (err) {
                attach_failed_message_badge(panel, textLabel);
            } else {
                remove_failed_message_badge(panel);
            }
            break;
        }"""
    edit(tft, old_handle_loop, new_handle_loop, "replace")


def main():
    dst = os.path.join(UI, "source", "graphics", "common")
    tft = os.path.join(UI, "source", "graphics", "TFT", "TFTView_320x240.cpp")
    vc = os.path.join(dst, "ViewController.cpp")
    drv = os.path.join(UI, "include", "graphics", "driver", "LGFXDriver.h")
    drvbase = os.path.join(UI, "include", "graphics", "driver", "DisplayDriver.h")
    conf = os.path.join(UI, "include", "lv_conf.h")
    # Ensure LV_USE_TJPGD is 0 to avoid collision with libesp32-camera.a (jd_prepare, jd_decomp) on 2.7.x
    edit(conf, "#define LV_USE_TJPGD 1", "#define LV_USE_TJPGD 0", "replace")
    # anchors that moved between library versions: use the first form that exists
    tft_text = read(tft)[0] if os.path.exists(tft) else ""
    SD_INC = next((a for a in ('#include "util/ILog.h"\n', '#include "graphics/common/SdCard.h"\n', '#include "ui.h"\n') if a in tft_text),
                  '#include "util/ILog.h"\n')
    drv_text = read(drv)[0] if os.path.exists(drv) else ""
    INACT = "lv_display_get_default()" if "lv_display_get_inactive_time(lv_display_get_default()) > screenTimeout" in drv_text else "NULL"
    VC_FN = "void ViewController::sendTextMessage("

    # Provide ISpiLock if missing in older device-ui (e.g. 2.7.x)
    spilock_h = os.path.join(UI, "include", "util", "ISpiLock.h")
    if not os.path.exists(spilock_h):
        os.makedirs(os.path.join(UI, "include", "util"), exist_ok=True)
        os.makedirs(os.path.join(UI, "source", "util"), exist_ok=True)
        copy("ISpiLock.h.in", os.path.join(UI, "include", "util"), "ISpiLock.h")
        copy("ISpiLock.cpp.in", os.path.join(UI, "source", "util"), "ISpiLock.cpp")

    # live screen orientation, portrait or landscape (feature "rotate", set in Advanced settings): the portrait layout is the build's
    # layout and its create function registers every object; riv_layout_gen.py turns the geometry of both generated layouts into
    # riv_apply_layout(), which moves the registered objects when the orientation changes. The display driver turns the panel and the
    # touch, TFTView re-applies its size adjustments.
    if "rotate" in feat:
        gen_p = os.path.join(UI, "generated", "ui_240x320")
        gen_l = os.path.join(UI, "generated", "ui_320x240")
        scr_p = os.path.join(gen_p, "screens.c")
        scr_l = os.path.join(gen_l, "screens.c")
        ui_c = os.path.join(gen_p, "ui.c")
        if os.path.isdir(gen_p) and os.path.exists(scr_l) and os.path.exists(scr_p) and os.path.exists(ui_c):
            import importlib.util
            spec = importlib.util.spec_from_file_location("riv_layout_gen", os.path.join(HERE, "riv_layout_gen.py"))
            gen = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(gen)
            old_land = os.path.join(gen_p, "screens_land.c")
            if os.path.exists(old_land):
                os.remove(old_land)
            sp, crlf_p = read(scr_p)
            sl = read(scr_l)[0]
            try:
                c_txt, patched, stats = gen.generate(sp, sl)
            except Exception as ex:
                print("MUI-EXTRAS WARNING: rotate layout not generated:", ex)
                MISSES.append("rotate: layout")
            else:
                write(scr_p, patched, crlf_p)
                lay_c = os.path.join(gen_p, "riv_layout.c")
                if not os.path.exists(lay_c) or read(lay_c)[0] != c_txt:
                    write(lay_c, c_txt, False)
                    print("Generated", lay_c, stats)
                # ui_init: normalise what earlier builds put there, then add the orientation hooks once
                ui_s, crlf_u = read(ui_c)
                ui_n = re.sub(r"extern int riv_landscape\(void\);\n(extern void (create_screen_main_screen_land\(void\)|riv_apply_layout\(int land\));\n)?\n?", "", ui_s)
                ui_n = ui_n.replace("    if (riv_landscape())\n        create_screen_main_screen_land();\n    else\n        create_screen_main_screen();\n",
                                    "    create_screen_main_screen();\n")
                ui_n = ui_n.replace("    if (riv_landscape())\n        riv_apply_layout(1);\n", "")
                ui_n = ui_n.replace("void ui_init() {\n", "extern int riv_landscape(void);\nextern void riv_apply_layout(int land);\n\nvoid ui_init() {\n", 1)
                ui_n = ui_n.replace("    create_screen_main_screen();\n    create_screen_lock_screen();\n",
                                    "    create_screen_main_screen();\n    if (riv_landscape())\n        riv_apply_layout(1);\n    create_screen_lock_screen();\n", 1)
                if ui_n != ui_s:
                    write(ui_c, ui_n, crlf_u)
                    print("Patched", ui_c)
                # display driver and view
                disp_h = os.path.join(UI, "include", "graphics", "driver", "DisplayDriver.h")
                lgfxd = os.path.join(UI, "include", "graphics", "driver", "LGFXDriver.h")
                tft_h2 = os.path.join(UI, "include", "graphics", "view", "TFT", "TFTView_320x240.h")
                edit(disp_h, "    virtual void setScreenTimeout(uint16_t timeout) {}\n", "    virtual void rivSetOrientation(bool land) {}\n", "after")
                # the declaration used to be put inside an unrelated #ifdef: take that copy out, then add it at file level
                lg_s, crlf_g = read(lgfxd)
                stray = '#ifdef RIV_ROTATE\nextern "C" int riv_landscape(void);\n#endif\n#ifndef LGFX_BUFFER_LINES\n'
                if stray in lg_s:
                    write(lgfxd, lg_s.replace(stray, "#ifndef LGFX_BUFFER_LINES\n", 1), crlf_g)
                edit(lgfxd, "constexpr uint32_t defaultLongPressTime", '#ifdef RIV_ROTATE\nextern "C" int riv_landscape(void);\n#endif\n\n', "before")
                # earlier runs may have added the method more than once or in an older form: remove every copy, the edit below adds one
                lg_c, crlf_c = read(lgfxd)
                lg_n = re.sub(r"#ifdef RIV_ROTATE\n    void rivSetOrientation\(bool land\) override\n    \{\n.*?\n    \}\n#endif\n", "", lg_c, flags=re.S)
                if lg_n != lg_c:
                    write(lgfxd, lg_n, crlf_c)
                edit(lgfxd, "    void setScreenTimeout(uint16_t timeout) override { screenTimeout = timeout * 1000; };\n",
                     "#ifdef RIV_ROTATE\n    void rivSetOrientation(bool land) override\n    {\n        lgfx->rivApplyOrientation(land);\n"
                     "        ILOG_DEBUG(\"RIV orientation %s\", land ? \"landscape\" : \"portrait\");\n"
                     "        lv_display_set_resolution(this->display, lgfx->screenWidth, lgfx->screenHeight);\n    }\n#endif\n", "after")
                edit(lgfxd, "    init_lgfx();\n    TFTDriver<LGFX>::init(gui);\n",
                     "#ifdef RIV_ROTATE\n    if (riv_landscape())\n        lgfx->rivApplyOrientation(true);\n#endif\n", "after")
                # touch and canvas sizes in the log while the orientation work is being checked
                edit(lgfxd, "        count = lgfx->getTouch(tp, maxPoints);\n    }\n",
                     "#ifdef RIV_ROTATE\n    {\n        static uint32_t riv_lastLog = 0;\n        if (count && millis() - riv_lastLog > 250) {\n"
                     "            riv_lastLog = millis();\n"
                     "            ILOG_DEBUG(\"RIV touch %d/%d lgfx %dx%d lv %dx%d\", (int)tp[0].x, (int)tp[0].y, (int)lgfx->width(), (int)lgfx->height(),\n"
                     "                       (int)lv_display_get_horizontal_resolution(lv_display_get_default()),\n"
                     "                       (int)lv_display_get_vertical_resolution(lv_display_get_default()));\n"
                     "        }\n    }\n#endif\n", "after")
                # same touch log for the plain (non gesture) touch read, and one line when the orientation changes
                edit(lgfxd, "        touched = lgfx->getTouch(&touchX, &touchY);\n    }\n",
                     "#ifdef RIV_ROTATE\n    {\n        static uint32_t riv_lastLog2 = 0;\n        if (touched && millis() - riv_lastLog2 > 250) {\n"
                     "            riv_lastLog2 = millis();\n"
                     "            ILOG_DEBUG(\"RIV touch %d/%d lgfx %dx%d lv %dx%d\", (int)touchX, (int)touchY, (int)lgfx->width(), (int)lgfx->height(),\n"
                     "                       (int)lv_display_get_horizontal_resolution(lv_display_get_default()),\n"
                     "                       (int)lv_display_get_vertical_resolution(lv_display_get_default()));\n"
                     "        }\n    }\n#endif\n", "after")
                edit(tft_h2, "    virtual void apply_hotfix(void);\n", "public:\n    void rivSetOrientation(bool land);\nprotected:\n", "after")
                edit(tft, "void TFTView_320x240::apply_hotfix(void)\n{\n",
                     'extern "C" void riv_apply_layout(int land);\n\n'
                     "// turn the screen between portrait and landscape without a restart\n"
                     "void TFTView_320x240::rivSetOrientation(bool land)\n{\n"
                     "    resetKeyboardSlide();\n"
                     "    displaydriver->rivSetOrientation(land);\n"
                     "    riv_apply_layout(land ? 1 : 0);\n"
                     "    apply_hotfix();\n"
                     "    lv_obj_update_layout(objects.main_screen);\n"
                     "    lv_obj_invalidate(objects.main_screen);\n"
                     "}\n\n", "before")

    # keyboard height and the gap it leaves above the message box
    if "keyboard" in feat and kb_pct:
        # an earlier build may have patched another percentage already, so every value found in the library is an anchor too
        s_kb, _ = read(tft)
        seen_pct = set(re.findall(r"lv_obj_set_size\(objects\.keyboard, LV_PCT\(100\), LV_PCT\((\d+)\)\);", s_kb))
        for def_pct in sorted(seen_pct or {"45", "34"}):
            edit(tft, "lv_obj_set_size(objects.keyboard, LV_PCT(100), LV_PCT(%s));" % def_pct,
                 "lv_obj_set_size(objects.keyboard, LV_PCT(100), LV_PCT(%s));" % kb_pct, "replace")
        # the stock code only sizes the keyboard on screens 480 high or more, a 320 high screen keeps the 50 % of the generated
        # layout, so the setting did nothing there: size it for every screen
        s_k, crlf_k = read(tft)
        kb_marker = "    // riv keyboard height\n"
        kb_line = kb_marker + "    lv_obj_set_size(objects.keyboard, LV_PCT(100), LV_PCT(%s));\n" % kb_pct
        kb_old = re.search(re.escape(kb_marker) + r"    lv_obj_set_size\(objects\.keyboard, LV_PCT\(100\), LV_PCT\(\d+\)\);\n", s_k)
        if kb_old:
            if kb_old.group(0) != kb_line:
                write(tft, s_k.replace(kb_old.group(0), kb_line, 1), crlf_k)
        else:
            edit(tft, "    // fix size for 480 pixel height displays\n", kb_line, "before")
        strip_extra = (" + emoji_strip_height()" if "compose" in feat else "")
        s_tft, _ = read(tft)
        if "kbdPanelBaseY" in s_tft:
            edit(tft, "        lv_anim_set_values(&a1, panelY, kbdPanelBaseY - kb_h);\n",
                 "        int32_t gapBelow = (int32_t)v - text_coords.y2;\n"
                 "        if (gapBelow < 0)\n"
                 "            gapBelow = 0;\n"
                 "        int32_t slide = (int32_t)kb_h - gapBelow + 2" + strip_extra + ";\n"
                 "        if (slide < 0)\n"
                 "            slide = 0;\n"
                 "        lv_anim_set_values(&a1, panelY, kbdPanelBaseY - slide);\n", "replace")
        else:
            edit(tft, "        lv_anim_set_values(&a1, panel_coords.y1, panel_coords.y1 - kb_h);\n",
                 "        int32_t gapBelow = (int32_t)v - text_coords.y2;\n"
                 "        if (gapBelow < 0)\n"
                 "            gapBelow = 0;\n"
                 "        int32_t slide = (int32_t)kb_h - gapBelow + 2" + strip_extra + ";\n"
                 "        if (slide < 0)\n"
                 "            slide = 0;\n"
                 "        lv_anim_set_values(&a1, panel_coords.y1, panel_coords.y1 - slide);\n", "replace")
        old_show_kb = ("    } else {\n"
                       "        if (text_coords.y1 > kb_h + 30) {\n"
                       "            // if enough place above put under top panel\n"
                       "            lv_obj_set_pos(objects.keyboard, 0, 28);\n"
                       "        } else if ((text_coords.y1 + 10) > v / 2) {\n"
                       "            // if text area is at lower half then place above text area\n"
                       "            lv_obj_set_pos(objects.keyboard, 0, text_coords.y1 - kb_h - 2);\n"
                       "        } else {\n"
                       "            // place below text area\n"
                       "            lv_obj_set_pos(objects.keyboard, 0, text_coords.y2 + 3);\n"
                       "        }\n"
                       "    }\n")
        new_show_kb = ("    } else {\n"
                       "        // In portrait mode, always dock virtual keyboard to bottom of screen\n"
                       "        lv_obj_set_pos(objects.keyboard, 0, v - kb_h);\n"
                       "    }\n")
        edit(tft, old_show_kb, new_show_kb, "replace")

    edit(tft,
         "void TFTView_320x240::apply_hotfix(void)\n{\n    // adapt screens to custom display resolution\n    uint32_t h = lv_display_get_horizontal_resolution(displaydriver->getDisplay());\n    uint32_t v = lv_display_get_vertical_resolution(displaydriver->getDisplay());\n",
         "void TFTView_320x240::apply_hotfix(void)\n{\n    // adapt screens to custom display resolution\n    uint32_t h = lv_display_get_horizontal_resolution(displaydriver->getDisplay());\n    uint32_t v = lv_display_get_vertical_resolution(displaydriver->getDisplay());\n    if (objects.main_screen)\n        lv_obj_set_size(objects.main_screen, h, v);\n    if (objects.boot_screen)\n        lv_obj_set_size(objects.boot_screen, h, v);\n    if (objects.blank_screen)\n        lv_obj_set_size(objects.blank_screen, h, v);\n",
         "replace")

    tft_decl = ""
    vc_decl = ""

    # battery INA I2C address forced to a fixed value, pushed to the node when it differs
    if ina_addr:
        pw_old = "    db.config.power = cfg;" + chr(10) + "    db.config.has_power = true;" + chr(10)
        pw_new = (
            "    if (cfg.device_battery_ina_address != %s) {" + chr(10)
            + "        meshtastic_Config_PowerConfig fixedPower = cfg;" + chr(10)
            + "        fixedPower.device_battery_ina_address = %s;" + chr(10)
            + "        db.config.power = fixedPower;" + chr(10)
            + "        controller->sendConfig(std::move(fixedPower));" + chr(10)
            + "    }" + chr(10)
        ) % (ina_addr, ina_addr)
        edit(tft, pw_old, pw_new)

    # colour emoji, emoji key and page on the keyboard, SD pack
    if "emoji" in feat:
        copy("emoji_font%s.c.in" % full, dst, "emoji_font.c")
        copy("emoji_sd.cpp.in", dst)
        copy("emoji_color.cpp.in", dst)
        inc, _ = read(os.path.join(HERE, "emoji_color_builtin%s.inc" % full))
        write(os.path.join(dst, "emoji_color_builtin.inc"), inc.replace("static const uint8_t builtin_data[]", "alignas(4) static const uint8_t builtin_data[]"), False)
        patch_fonts()
        patch_keyboard_emoji("compose" in feat)
        edit(conf, "#define LV_USE_IMGFONT 0", "#define LV_USE_IMGFONT 1", "replace")
        edit(conf, "#define LV_USE_FS_MEMFS 0", "#define LV_USE_FS_MEMFS 1", "replace")
        edit(conf, "#define LV_FS_MEMFS_LETTER '" + chr(92) + "0'", "#define LV_FS_MEMFS_LETTER 'M'", "replace")
        tft_decl += 'extern "C" void emoji_load_from_sd(void);\nextern "C" void emoji_color_init(void);\n'
        edit(tft, '        ILOG_DEBUG("SdCard init successful, card type: %d", sdCard->cardType());',
             '\n        emoji_load_from_sd();')
        edit(tft, "bool TFTView_320x240::updateSDCard(void)\n{\n    formatSD = false;",
             "bool TFTView_320x240::updateSDCard(void)\n{\n    emoji_color_init();\n    formatSD = false;", "replace")

    # :name suggestions, quote header, reaction chips, long press to react or reply, long chat names
    if "chat" in feat or "advanced" in feat:
        copy("MuiPrefs.h", dst)
        copy("emoji_suggest.cpp.in", dst)
        copy("emoji_names.inc", dst)
    if "chat" in feat:
        copy("emoji_bubbles.cpp.in", dst)
        # pinned chats (max 5), unread and total counts on the chat buttons
        copy("emoji_chatlist.cpp.in", dst)
        # the bot chat is recognised when its first message is built, not only while it is open
        tft_decl += 'extern "C" void emoji_chat_hint(lv_obj_t *, const char *, const char *);\n'
        edit(tft, "    newMessage(from, container, ch, buf);\n",
             "    if (to != UINT32_MAX) {\n        auto itn = nodes.find(from);\n        if (itn != nodes.end())\n            emoji_chat_hint(container, lv_label_get_text(itn->second->LV_OBJ_IDX(node_lbs_idx)), lv_label_get_text(itn->second->LV_OBJ_IDX(node_lbl_idx)));\n    }\n", "before")
        # @mention suggestions: the lookup was declared but never given the node list
        tft_decl += 'extern "C" void emoji_mention_host(void (*)(const char *, void (*)(const char *, const char *, uint32_t)));\n'
        edit(tft, "    lv_obj_add_event_cb(objects.message_input_area, ui_event_message_ready, LV_EVENT_ALL, NULL);\n", MENTION_LAMBDA, "before")
        tft_decl += ('extern "C" void emoji_chat_decorate(lv_obj_t *, lv_obj_t *, uint32_t);\n'
                     'extern "C" void emoji_chat_count(uint32_t, bool, lv_obj_t *);\n'
                     'extern "C" void emoji_chat_seen(uint32_t, lv_obj_t *);\n')
        edit(tft, "    lv_obj_add_event_cb(chatDelBtn, ui_event_ChatDelButton, LV_EVENT_CLICKED, (void *)index);\n",
             "    emoji_chat_decorate(chatBtn, chatDelBtn, index);\n")
        edit(tft, "    newMessage(from, container, ch, buf);\n",
             "    {\n        uint32_t ci = (to == UINT32_MAX || from == 0) ? ch : from;\n        auto itc = chats.find(ci);\n        emoji_chat_count(ci, !restore && (container != activeMsgContainer || activePanel != objects.messages_panel), itc != chats.end() ? itc->second : nullptr);\n    }\n")
        edit(tft, "void TFTView_320x240::showMessages(uint8_t ch)\n{\n",
             "    { auto itc = chats.find(ch); emoji_chat_seen(ch, itc != chats.end() ? itc->second : nullptr); }\n")
        edit(tft, "void TFTView_320x240::showMessages(uint32_t nodeNum)\n{\n",
             "    { auto itc = chats.find(nodeNum); emoji_chat_seen(nodeNum, itc != chats.end() ? itc->second : nullptr); }\n")
        if "meshbot" in feat:
            # B-48 / RiV-meshBot chat: white background with the bot logo and solid bubbles
            copy("meshbot_bg.cpp.in", dst)
            copy("meshbot_logo.inc", dst)
            stale = os.path.join(dst, "emoji_bot_stub.cpp")
            if os.path.exists(stale):
                try: os.remove(stale)
                except: pass
            tft_decl += ('extern "C" void emoji_wifi_vault_add(const char *, const char *);\n'
'extern "C" void emoji_mention_host(void (*)(const char *, void (*)(const char *, const char *, uint32_t)));\n'
                         'extern "C" void emoji_chat_style(lv_obj_t *, const char *, const char *);\n'
                         'extern "C" void emoji_bubble_style(lv_obj_t *, lv_obj_t *, bool);\n')
            shown = ("    lv_obj_t *p = nodes[nodeNum];\n    if (p) {\n"
                     "        lv_label_set_text(objects.top_messages_node_label, lv_label_get_text(p->LV_OBJ_IDX(node_lbl_idx)));\n")
            edit(tft, shown, "        emoji_chat_style(activeMsgContainer, lv_label_get_text(p->LV_OBJ_IDX(node_lbs_idx)),\n"
                             "                         lv_label_get_text(p->LV_OBJ_IDX(node_lbl_idx)));\n")
            group = "    lv_label_set_text(objects.top_group_chat_label, lv_label_get_text(channel[ch]));\n"
            edit(tft, group, "    emoji_chat_style(nullptr, nullptr, nullptr);\n")
        else:
            copy("bot_stub.cpp.in", dst, "emoji_bot_stub.cpp")
            stale = os.path.join(dst, "meshbot_bg.cpp")
            if os.path.exists(stale):
                try: os.remove(stale)
                except: pass
        old_adv = os.path.join(dst, "emoji_advanced.cpp")
        if os.path.exists(old_adv):
            try: os.remove(old_adv)
            except: pass
        tft_decl += ('extern "C" void emoji_record_node_pos(uint32_t, int32_t, int32_t, bool);\n'
                     'extern "C" bool emoji_node_distance_str(uint32_t, char *, size_t);\n'
                     'extern "C" void emoji_top_wifi_update(bool, lv_obj_t *);\n'
                     'extern "C" void emoji_trigger_traceroute(uint32_t, uint8_t);\n'
                     'extern "C" void emoji_log_message_to_sd(const char *, const char *);\n'
                     'extern "C" void emoji_suggest_init(lv_obj_t *);\n'
                     'extern "C" void emoji_suggest_init(lv_obj_t *);\n'
                     'extern "C" bool emoji_long_names(void);\n'
                     'extern "C" void emoji_bubble_register(lv_obj_t *, uint32_t);\n'
                     'extern "C" void emoji_chip_expect(bool);\n'
                     'extern "C" void emoji_name_chip(lv_obj_t *, uint32_t, const char *);\n'
                     'extern "C" void emoji_open_node_chat(uint32_t);\n'
                     'extern "C" uint32_t emoji_find_node_by_name(const char *, const char *);\n'
                     'extern "C" void emoji_set_reply(uint32_t, bool);\n'
                     'extern "C" int emoji_ctx_mode(void);\n'
                     'extern "C" uint32_t emoji_ctx_target(void);\n'
                     'extern "C" void emoji_ctx_done(void);\n'
                     'extern "C" bool emoji_reaction_apply(uint32_t, const char *, size_t);\n')
        vc_decl += ('extern "C" void emoji_quote_record(uint32_t, const char *);\n'
                    'extern "C" size_t emoji_quote_compose(uint32_t, uint32_t, uint32_t, const char *, size_t, char *, size_t);\n'
                    'extern "C" void emoji_pending_id(uint32_t);\n'
                    'extern "C" void emoji_record_hops(uint32_t, bool);\n'
                    'extern "C" void emoji_record_rx_stats(uint32_t, bool, float, int32_t);\n'
                    'extern "C" bool emoji_reaction_apply(uint32_t, const char *, size_t);\n'
                    'extern "C" int emoji_ctx_mode(void);\n'
                    'extern "C" uint32_t emoji_send_reply_id(void);\n'
                    'extern "C" uint32_t emoji_send_emoji_flag(void);\n'
                    'extern "C" size_t emoji_log_text(const char *, size_t, char *, size_t);\n')
        edit(tft, "    lv_obj_add_event_cb(objects.message_input_area, ui_event_message_ready, LV_EVENT_ALL, NULL);\n",
             "    emoji_suggest_init(objects.message_input_area);\n")
        # chat bubbles register for reactions
        sent_anchor = "    add_style_chat_message_style(textLabel);\n"
        recv_anchor = "    add_style_new_message_style(msgLabel);\n"
        if "meshbot" in feat:
            edit(tft, sent_anchor, "    emoji_bubble_style(textLabel, container, true);\n")
            edit(tft, recv_anchor, "    emoji_bubble_style(msgLabel, container, false);\n")
            sent_anchor = "    emoji_bubble_style(textLabel, container, true);\n"
            recv_anchor = "    emoji_bubble_style(msgLabel, container, false);\n"
        edit(tft, sent_anchor, "    emoji_bubble_register(textLabel, requestId);\n")
        edit(tft, recv_anchor, "    emoji_bubble_register(msgLabel, 0);\n")
        # coloured short name chip on group messages, and the group flag set by the caller
        edit(tft, "    emoji_bubble_register(msgLabel, 0);\n",
             "    {\n"
             "        char chipShort[5] = {0};\n"
             "        auto itc = nodes.find(nodeNum);\n"
             "        if (itc != nodes.end()) {\n"
             "            const char *ud = (const char *)&(itc->second->LV_OBJ_IDX(node_lbs_idx)->user_data);\n"
             "            for (int ci = 0; ci < 4 && ud[ci]; ci++)\n"
             "                chipShort[ci] = ud[ci];\n"
             "        } else\n"
             "            snprintf(chipShort, sizeof(chipShort), \"%04x\", (unsigned)(nodeNum & 0xffff));\n"
             "        emoji_name_chip(msgLabel, nodeNum, chipShort);\n"
             "    }\n"
             "    emoji_bubble_register(msgLabel, 0);\n", "replace")
        edit(tft, "    // place message into container\n    newMessage(from, container, ch, buf);\n",
             "    // place message into container\n    emoji_chip_expect(to == UINT32_MAX);\n    newMessage(from, container, ch, buf);\n", "replace")
        # group bubbles show the long name when the setting is on
        names_old = ("            char *userData = (char *)&(nodes[from]->LV_OBJ_IDX(node_lbs_idx)->user_data);\n"
                     "            while (pos < 4 && userData[pos] != 0) {\n"
                     "                buf[pos] = userData[pos];\n"
                     "                pos++;\n"
                     "            }\n")
        names_new = ("            char *userData = (char *)&(nodes[from]->LV_OBJ_IDX(node_lbs_idx)->user_data);\n"
                     "            const char *longName = lv_label_get_text(nodes[from]->LV_OBJ_IDX(node_lbl_idx));\n"
                     "            if (emoji_long_names() && longName && longName[0]) {\n"
                     "                while (pos < 18 && longName[pos] != 0) {\n"
                     "                    buf[pos] = longName[pos];\n"
                     "                    pos++;\n"
                     "                }\n"
                     "                while (pos > 0 && longName[pos] != 0 && ((unsigned char)longName[pos] & 0xC0) == 0x80)\n"
                     "                    pos--;\n"
                     "            } else {\n"
                     "                while (pos < 4 && userData[pos] != 0) {\n"
                     "                    buf[pos] = userData[pos];\n"
                     "                    pos++;\n"
                     "                }\n"
                     "            }\n")
        edit(tft, names_old, names_new, "replace")
        # long press: reply id and reaction flag into the packet, reactions land on the bubble
        edit(vc, "    size_t msgLen = strlen(textmsg);\n    assert(msgLen <= (size_t)DATA_PAYLOAD_LEN);\n",
             "    emoji_quote_record(requestId, textmsg);\n")
        recv_old = [
            ("        if (p.decoded.emoji != 0 &&\n"
             "            emoji_reaction_apply(p.decoded.reply_id, (const char *)p.decoded.payload.bytes, p.decoded.payload.size))\n"
             "            break;\n"
             "        char quoted[DATA_PAYLOAD_LEN + 1];\n"
             "        size_t quotedLen = emoji_quote_compose(p.id, p.decoded.reply_id, p.decoded.emoji,\n"
             "                                               (const char *)p.decoded.payload.bytes, p.decoded.payload.size, quoted,\n"
             "                                               sizeof(quoted));\n"
             "        emoji_pending_id(p.id);\n"
             "        uint32_t pHops = (p.hop_start > p.hop_limit) ? (p.hop_start - p.hop_limit) : 0;\n"
             "        emoji_record_hops(pHops, p.via_mqtt);\n"
             "        emoji_message_alert();\n"
             "        view->newMessage(p.from, p.to, p.channel, quoted, time);\n"
             "        log.write(LogMessageEnv(p.from, p.to, p.channel, time, LogMessage::eDefault, false, quotedLen,\n"
             "                                (const uint8_t *)quoted));\n"),
            ("        view->newMessage(p.from, p.to, p.channel, (const char *)p.decoded.payload.bytes, time);\n"
             "        log.write(LogMessageEnv(p.from, p.to, p.channel, time, LogMessage::eDefault, false, p.decoded.payload.size,\n"
             "                                (const uint8_t *)p.decoded.payload.bytes));\n"),
        ]
        recv_new = ("        if (p.decoded.emoji != 0 &&\n"
                    "            emoji_reaction_apply(p.decoded.reply_id, (const char *)p.decoded.payload.bytes, p.decoded.payload.size))\n"
                    "            break;\n"
                    "        char quoted[DATA_PAYLOAD_LEN + 1];\n"
                    "        size_t quotedLen = emoji_quote_compose(p.id, p.decoded.reply_id, p.decoded.emoji,\n"
                    "                                               (const char *)p.decoded.payload.bytes, p.decoded.payload.size, quoted,\n"
                    "                                               sizeof(quoted));\n"
                    "        emoji_pending_id(p.id);\n"
                    "        uint32_t pHops = (p.hop_start > p.hop_limit) ? (p.hop_start - p.hop_limit) : 0;\n"
                    "        emoji_record_hops(pHops, p.via_mqtt);\n"
                    "        view->newMessage(p.from, p.to, p.channel, quoted, time);\n"
                    "        log.write(LogMessageEnv(p.from, p.to, p.channel, time, LogMessage::eDefault, false, quotedLen,\n"
                    "                                (const uint8_t *)quoted));\n")
        edit(vc, recv_old, recv_new, "replace")
        edit(vc, "                .want_response = wantRsp}, // FIXME: traceRoute, requestPosition, remote config: true\n",
             "                .want_response = wantRsp,\n"
             "                .reply_id = emoji_send_reply_id(),\n"
             "                .emoji = emoji_send_emoji_flag()},\n", "replace")
        log_old = "        log.write(LogMessageEnv(myNodeNum, to, ch, msgTime, LogMessage::eDefault, false, msgLen, (const uint8_t *)textmsg));\n"
        log_new = ("        if (emoji_ctx_mode() != 1) {\n"
                   "            char logText[DATA_PAYLOAD_LEN + 1];\n"
                   "            size_t logLen = emoji_log_text(textmsg, msgLen, logText, sizeof(logText));\n"
                   "            log.write(LogMessageEnv(myNodeNum, to, ch, msgTime, LogMessage::eDefault, false, logLen, (const uint8_t *)logText));\n"
                   "        }\n")
        edit(vc, log_old, log_new, "replace")
        add_old = ("    controller->sendTextMessage(to, ch, hopLimit, actTime, requestId, usePkc, msg);\n"
                   "    addMessage(activeMsgContainer, actTime, requestId, msg, LogMessage::eNone);\n")
        add_new = ("    emoji_set_reply(emoji_ctx_target(), emoji_ctx_mode() == 1);\n"
                   "    controller->sendTextMessage(to, ch, hopLimit, actTime, requestId, usePkc, msg);\n"
                   "    emoji_set_reply(0, false);\n"
                   "    if (emoji_ctx_mode() == 1) {\n"
                   "        // a reaction goes onto the bubble it answers, there is no bubble of its own\n"
                   "        emoji_reaction_apply(emoji_ctx_target(), msg, strlen(msg));\n"
                   "        emoji_ctx_done();\n"
                   "        return;\n"
                   "    }\n"
                   "    addMessage(activeMsgContainer, actTime, requestId, msg, LogMessage::eNone);\n"
                   "    emoji_ctx_done();\n")
        edit(tft, add_old, add_new, "replace")

    # recent emoji strip, format bar, alert bell, copy and paste, formatted bubbles, theme coloured keyboard
    if "compose" in feat:
        copy("emoji_compose.cpp.in", dst)
        for style in ("bold", "italic"):
            for size in (14,):
                fname = "mui_font_%s_%d" % (style, size)
                ftxt, _ = read(os.path.join(HERE, fname + ".c.in"))
                if "emoji" in feat:
                    ftxt = ftxt.replace(".fallback = NULL,", ".fallback = &ui_emoji_color_font,", 1)
                    ftxt = ftxt.replace("#ifdef LV_LVGL_H_INCLUDE_SIMPLE",
                                        "#include \"lvgl.h\"\nextern lv_font_t ui_emoji_color_font;\n#ifdef LV_LVGL_H_INCLUDE_SIMPLE", 1)
                write(os.path.join(dst, fname + ".c"), ftxt, False)
        edit(conf, "#define LV_USE_SPAN       0", "#define LV_USE_SPAN       1", "replace")
        tft_decl += ('extern "C" void emoji_wifi_vault_add(const char *, const char *);\n'
'extern "C" void emoji_compose_init(lv_obj_t *, lv_obj_t *, lv_obj_t *, void (*)(lv_obj_t *));\n'
                     'extern "C" int emoji_strip_height(void);\n')
        edit(tft, "    lv_obj_add_event_cb(objects.message_input_area, ui_event_message_ready, LV_EVENT_ALL, NULL);\n",
             "    emoji_compose_init(objects.message_input_area, objects.main_screen, objects.keyboard, [](lv_obj_t *ta) {\n"
             "        lv_obj_move_foreground(objects.keyboard);\n"
             "        THIS->showKeyboard(ta);\n"
             "    });\n"
             "    lv_obj_add_event_cb(objects.message_input_area, [](lv_event_t *e) {\n"
             "        lv_event_code_t code = lv_event_get_code(e);\n"
             "        if (code == LV_EVENT_CLICKED || code == LV_EVENT_FOCUSED) {\n"
             "            lv_obj_remove_flag(objects.keyboard, LV_OBJ_FLAG_HIDDEN);\n"
             "            lv_obj_move_foreground(objects.keyboard);\n"
             "            THIS->showKeyboard(objects.message_input_area);\n"
             "        }\n"
             "    }, LV_EVENT_ALL, NULL);\n", "before")

    # extra themes
    if "themes" in feat:
        copy("themes_extra.inc.in", os.path.join(UI, "source", "graphics", "TFT"), "themes_extra.inc")
        themes_cpp = os.path.join(UI, "source", "graphics", "TFT", "Themes.cpp")
        edit(themes_cpp, "#define THEME(COLOR) (themeColor[COLOR][theme])\n",
             '#include "themes_extra.inc"\n'
             "#define THEME(COLOR) (theme < 2 ? themeColor[COLOR][theme] : themeXform(themeColor[COLOR][0], (int)theme))\n", "replace")
        edit(themes_cpp, "switch (theme) {", "switch (theme < 2 ? theme : eDark) {", "replace")
        edit(os.path.join(UI, "include", "graphics", "view", "TFT", "Themes.h"),
             "enum Theme { eDark, eLight, eRed };", "enum Theme { eDark, eLight, eRed, eOled, eOcean, eAmber, ePurple };", "replace")
        for d in ("ui_320x240", "ui_240x320"):
            edit(os.path.join(UI, "generated", d, "screens.c"), r'_("Dark\nLight")', r'_("Dark\nLight\nRed\nOLED\nOcean\nAmber\nPurple")', "replace")

    if "compose" in feat:
        themes_cpp2 = os.path.join(UI, "source", "graphics", "TFT", "Themes.cpp")
        edit(themes_cpp2, "void Themes::set(enum Theme th)\n{",
             'extern "C" void emoji_keyboard_theme(uint32_t, uint32_t, uint32_t, uint32_t, uint32_t);\n', "before")
        edit(themes_cpp2, "    apply_style_statistics_table_style_ITEMS_DEFAULT();\n}\n\nvoid Themes::initStyles(void)",
             "    apply_style_statistics_table_style_ITEMS_DEFAULT();\n"
             "    emoji_keyboard_theme(THEME(ePanelBg), THEME(eNodePanelBg), THEME(ePanelText), THEME(eTopPanelBg), THEME(ePanelPressedBg));\n"
             "}\n\nvoid Themes::initStyles(void)", "replace")

    # advanced settings with the chat names switch and the MQTT form
    if "advanced" in feat:
        copy("MuiPrefs.h", dst)
        copy("mui_advanced.cpp.in", dst)
        copy("mui_tools_extras.cpp.in", dst)
        themes_cpp3 = os.path.join(UI, "source", "graphics", "TFT", "Themes.cpp")
        edit(themes_cpp3, "void Themes::set(enum Theme th)\n{",
             'extern "C" void emoji_advanced_theme(uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t);\nextern "C" void emoji_tools_theme(uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t);\n', "before")
        edit(themes_cpp3, "apply_style_statistics_table_style_ITEMS_DEFAULT();\n",
             "apply_style_statistics_table_style_ITEMS_DEFAULT();\n"
             "    emoji_advanced_theme(THEME(ePanelBg), THEME(eTopPanelBg), THEME(eTopPanelText), THEME(eNodePanelBg), THEME(eNodePanelText), THEME(eSettingsButtonBg), THEME(eSettingsButtonText), THEME(eColorTextLabel), THEME(eNodePanelBorder), THEME(ePanelPressedBg));\n"
             "    emoji_tools_theme(THEME(ePanelBg), THEME(eTopPanelBg), THEME(eTopPanelText), THEME(eNodePanelBg), THEME(eNodePanelText), THEME(eSettingsButtonBg), THEME(eSettingsButtonText), THEME(eColorTextLabel), THEME(eNodePanelBorder), THEME(ePanelPressedBg));\n")
        tft_decl += ('extern "C" void emoji_wifi_vault_add(const char *, const char *);\n'
'extern "C" bool emoji_long_names(void);\n'
                     'extern "C" void emoji_settings_init(lv_obj_t *, lv_obj_t *, lv_obj_t *, void *(*)(void), void (*)(void), '
                     'void (*)(lv_obj_t *));\n'
                     'extern "C" void emoji_settings_host(void *(*)(void), void *(*)(void), void *(*)(void), void *(*)(void), '
                     'void (*)(void), void (*)(void), void (*)(void), void (*)(void));\n'
                     'extern "C" void emoji_settings_host2(void *(*)(void), void (*)(void), int, void (*)(const char *));\n'
                     'extern "C" void emoji_settings_host3(void *(*)(void), void (*)(void), void *(*)(void), void (*)(void));\n'
                     'extern "C" void emoji_settings_channels(void *(*)(int), void (*)(int), int (*)(void));\n'
                     'extern "C" void emoji_tools_extras_init(lv_obj_t *, lv_obj_t *, lv_obj_t *, void (*)(lv_obj_t *));\n'
                     'extern "C" void emoji_tools_record_pos(uint32_t, int32_t, int32_t, int32_t, bool);\n'
                     'extern "C" void emoji_tools_record_sats(uint32_t);\n'
                     'extern "C" void emoji_tools_record_node(uint32_t, const char *, const char *, uint32_t);\n'
                     'extern "C" void emoji_tools_record_signal(uint32_t, int32_t, float);\n'
                     'extern "C" void emoji_tools_record_metrics(float, float);\n'
                     'extern "C" void emoji_tools_record_packet(bool, bool);\n'
                     'extern "C" void emoji_tools_theme(uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t);\n')
        if "rotate" in feat:
            tft_decl += 'extern "C" void emoji_rotate_host(void (*)(bool));\n'
            edit(tft, "    lv_obj_add_event_cb(objects.message_input_area, ui_event_message_ready, LV_EVENT_ALL, NULL);\n",
                 "    emoji_rotate_host([](bool land) { THIS->rivSetOrientation(land); });\n", "before")
        vc_decl += 'extern "C" void emoji_gps_record(const void *);\n'
        # renaming the node shows "Rebooting ..." but nothing asks the node to reboot, so the screen would wait for ever
        edit(tft, '                THIS->controller->sendConfig(user, THIS->ownNode);\n                THIS->notifyReboot(true);\n',
             '                THIS->controller->sendConfig(user, THIS->ownNode);\n                THIS->controller->requestReboot(3, THIS->ownNode);\n                THIS->notifyReboot(true);\n', "replace")
        vc_decl += 'extern "C" void emoji_node_flags(uint32_t, bool, bool);\n'
        tft_decl += ('extern "C" void emoji_wifi_vault_add(const char *, const char *);\n'
'extern "C" void emoji_nodes_host(uint32_t (*)(uint32_t, bool, uint32_t *));\n'
                     'extern "C" bool emoji_node_protected(uint32_t);\n'
                     '#include <vector>\n')
        edit(vc, '                const meshtastic_NodeInfo &node = from.node_info;\n',
             '                emoji_node_flags(node.num, node.is_favorite, node.is_ignored);\n', "after")
        edit(tft, "    lv_obj_add_event_cb(objects.message_input_area, ui_event_message_ready, LV_EVENT_ALL, NULL);\n", NODES_LAMBDA, "before")
        if "meshbot" in feat:
            tft_decl += 'extern "C" void emoji_meshbot_host(uint32_t (*)(const char *, const char *), void (*)(uint32_t));\n'
            edit(tft, "    lv_obj_add_event_cb(objects.message_input_area, ui_event_message_ready, LV_EVENT_ALL, NULL);\n", MESHBOT_LAMBDA, "before")
        edit(vc, '            // if "to" is our node then this is a reply to a requestPosition request\n',
             "            if (p.from == myNodeNum)\n"
             "                emoji_gps_record(&position);\n", "before")
        edit(tft, "    lv_obj_add_event_cb(objects.message_input_area, ui_event_message_ready, LV_EVENT_ALL, NULL);\n",
             "    emoji_settings_host(\n"
             "        []() -> void * { return &THIS->db.config.lora; }, []() -> void * { return &THIS->db.config.position; },\n"
             "        []() -> void * { return &THIS->db.config.security; }, []() -> void * { return &THIS->db.config.power; },\n"
             "        []() { THIS->controller->sendConfig(meshtastic_Config_LoRaConfig{THIS->db.config.lora}); },\n"
             "        []() { THIS->controller->sendConfig(meshtastic_Config_PositionConfig{THIS->db.config.position}); },\n"
             "        []() { THIS->controller->sendConfig(meshtastic_Config_SecurityConfig{THIS->db.config.security}); },\n"
             "        []() { THIS->controller->sendConfig(meshtastic_Config_PowerConfig{THIS->db.config.power}); });\n"
             "    emoji_settings_host2(\n"
             "        []() -> void * { return &THIS->db.module_config.external_notification; },\n"
             "        []() {\n"
             "            THIS->controller->sendConfig(\n"
             "                meshtastic_ModuleConfig_ExternalNotificationConfig{THIS->db.module_config.external_notification});\n"
             "        },\n"
             "        " + notify_pin + "," + chr(10) +
             "        [](const char *ring) {" + chr(10) +
             "            char buf[231];" + chr(10) +
             "            strncpy(buf, ring, sizeof(buf) - 1);" + chr(10) +
             "            buf[sizeof(buf) - 1] = 0;" + chr(10) +
             "            THIS->controller->sendConfig(buf);" + chr(10) +
             "        });" + chr(10))
        edit(tft, "    lv_obj_add_event_cb(objects.message_input_area, ui_event_message_ready, LV_EVENT_ALL, NULL);\n",
             "    emoji_settings_host3(\n"
             "        []() -> void * { return &THIS->db.config.network; },\n"
             "        []() { THIS->controller->sendConfig(meshtastic_Config_NetworkConfig{THIS->db.config.network}); },\n"
             "        []() -> void * { return &THIS->db.config.device; },\n"
             "        []() { THIS->controller->sendConfig(meshtastic_Config_DeviceConfig{THIS->db.config.device}); });\n")
        edit(tft, "    lv_obj_add_event_cb(objects.message_input_area, ui_event_message_ready, LV_EVENT_ALL, NULL);\n",
             "    emoji_settings_channels(\n"
             "        [](int ch) -> void * {\n"
             "            if (ch < 0 || ch >= c_max_channels) return nullptr;\n"
             "            if (THIS->channel_scratch) return &THIS->channel_scratch[ch];\n"
             "            return &THIS->db.channel[ch];\n"
             "        },\n"
             "        [](int ch) {\n"
             "            if (ch < 0 || ch >= c_max_channels) return;\n"
             "            if (THIS->channel_scratch) THIS->db.channel[ch] = THIS->channel_scratch[ch];\n"
             "            THIS->updateChannelConfig(THIS->db.channel[ch]);\n"
             "            THIS->controller->sendConfig(THIS->db.channel[ch], THIS->ownNode);\n"
             "            for (int b = 0; b < c_max_channels; b++) {\n"
             "                if ((signed long)THIS->ch_label[b]->user_data == ch) {\n"
             "                    lv_label_set_text(THIS->ch_label[b], THIS->db.channel[ch].settings.name[0] ? THIS->db.channel[ch].settings.name : _(\"<unset>\"));\n"
             "                }\n"
             "            }\n"
             "        },\n"
             "        []() -> int { return c_max_channels; });\n")
        edit(tft, "    lv_obj_add_event_cb(objects.message_input_area, ui_event_message_ready, LV_EVENT_ALL, NULL);\n",
             "    lv_obj_set_style_pad_left(objects.tab_page_basic_settings, 0, LV_PART_MAIN | LV_STATE_DEFAULT);\n"
             "    lv_obj_set_style_pad_right(objects.tab_page_basic_settings, 0, LV_PART_MAIN | LV_STATE_DEFAULT);\n"
             "    lv_obj_set_flex_align(objects.tab_page_basic_settings, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);\n"
             "    for (uint32_t i = 0; i < lv_obj_get_child_count(objects.home_container); i++) {\n"
             "        lv_obj_t *hc = lv_obj_get_child(objects.home_container, i);\n"
             "        if (hc && hc->class_p == &lv_button_class) lv_obj_add_flag(hc, LV_OBJ_FLAG_FLEX_IN_NEW_TRACK);\n"
             "    }\n"
             "    emoji_settings_init(\n"
             "        objects.basic_settings_language_button, objects.main_screen, objects.keyboard,\n"
             "        []() -> void * { return &THIS->db.module_config.mqtt; },\n"
             "        []() { THIS->controller->sendConfig(meshtastic_ModuleConfig_MQTTConfig{THIS->db.module_config.mqtt}); },\n"
             "        [](lv_obj_t *ta) {\n"
             "            lv_obj_remove_flag(objects.keyboard, LV_OBJ_FLAG_HIDDEN);\n"
             "            lv_obj_move_foreground(objects.keyboard);\n"
             "            THIS->showKeyboard(ta);\n"
             "        });\n"
             "    emoji_tools_extras_init(\n"
             "        objects.tab_page_tools, objects.main_screen, objects.keyboard,\n"
             "        [](lv_obj_t *ta) {\n"
             "            lv_obj_remove_flag(objects.keyboard, LV_OBJ_FLAG_HIDDEN);\n"
             "            lv_obj_move_foreground(objects.keyboard);\n"
             "            THIS->showKeyboard(ta);\n"
             "        });\n")

    # DISABLE_MUI_PROGRAMMING_MODE only silenced the notice of the packet API, a tap on the boot logo still entered programming mode
    # (the hold time is checked against a start that is only set by a long press). With the flag a tap or a hold just ends the boot logo.
    edit(tft,
         "    if (state <= MeshtasticView::eBootScreenDone && state != MeshtasticView::eWaitingForReboot) {\n        enterProgrammingMode();\n    }\n",
         "#ifndef DISABLE_MUI_PROGRAMMING_MODE\n    if (state == MeshtasticView::eEnterProgrammingMode) {\n        enterProgrammingMode();\n    }\n#endif\n",
         "replace")
    edit(tft,
         "    if (state == MeshtasticView::eEnterProgrammingMode || state == MeshtasticView::eProgrammingMode ||\n        state == MeshtasticView::eWaitingForReboot) {\n        enterProgrammingMode();\n        return false;\n    }\n",
         "#ifndef DISABLE_MUI_PROGRAMMING_MODE\n    if (state == MeshtasticView::eEnterProgrammingMode || state == MeshtasticView::eProgrammingMode ||\n        state == MeshtasticView::eWaitingForReboot) {\n        enterProgrammingMode();\n        return false;\n    }\n#endif\n",
         "replace")
    edit(tft,
         "    lv_obj_remove_event_cb(objects.boot_logo_button, ui_event_LogoButton);\n",
         "    lv_obj_remove_event_cb(objects.boot_logo_button, ui_event_LogoButton);\n    if (objects.main_screen)\n        lv_screen_load_anim(objects.main_screen, LV_SCR_LOAD_ANIM_NONE, 0, 0, false);\n",
         "replace")
    edit(tft,
         "            lv_obj_add_flag(objects.boot_logo_arc, LV_OBJ_FLAG_HIDDEN);\n            THIS->state = MeshtasticView::eBootScreenDone;\n        }\n    } else if (event_code == LV_EVENT_LONG_PRESSED) {",
         "            lv_obj_add_flag(objects.boot_logo_arc, LV_OBJ_FLAG_HIDDEN);\n            THIS->state = MeshtasticView::eBootScreenDone;\n            if (objects.main_screen)\n                lv_screen_load_anim(objects.main_screen, LV_SCR_LOAD_ANIM_NONE, 0, 0, false);\n        }\n    } else if (event_code == LV_EVENT_LONG_PRESSED) {",
         "replace")
    edit(tft, "        if (millis() - start > 800) {\n            THIS->state = MeshtasticView::eEnterProgrammingMode;\n            THIS->enterProgrammingMode();\n        } else {\n",
         "#ifdef DISABLE_MUI_PROGRAMMING_MODE\n        if (false) {\n#else\n        if (millis() - start > 800) {\n#endif\n            THIS->state = MeshtasticView::eEnterProgrammingMode;\n            THIS->enterProgrammingMode();\n        } else {\n", "replace")
    edit(tft, "        THIS->state = MeshtasticView::eEnterProgrammingMode;\n        THIS->enterProgrammingMode();\n    }\n    lv_obj_remove_event_cb(objects.boot_logo_button, ui_event_LogoButton);\n",
         "#ifdef DISABLE_MUI_PROGRAMMING_MODE\n        THIS->state = MeshtasticView::eBootScreenDone;\n#else\n        THIS->state = MeshtasticView::eEnterProgrammingMode;\n        THIS->enterProgrammingMode();\n#endif\n    }\n    lv_obj_remove_event_cb(objects.boot_logo_button, ui_event_LogoButton);\n", "replace")

    # a received message wakes the screen for 8 seconds
    if "wake" in feat:
        drvbase_text = read(drvbase)[0] if os.path.exists(drvbase) else ""
        if "wakeForMessage" not in drvbase_text:
            if "virtual void forceWakeup(void) {}" in drvbase_text:
                edit(drvbase, "    virtual void forceWakeup(void) {}\n", "    virtual void wakeForMessage(void) {}\n")
            else:
                edit(drvbase, "    virtual bool isPowersaving() { return false; }\n", "    virtual void wakeForMessage(void) {}\n")

        drv_curr = read(drv)[0] if os.path.exists(drv) else ""
        if "wakeForMessage" not in drv_curr:
            if "void forceWakeup(void) override" in drv_text:
                edit(drv, "    void forceWakeup(void) override { forcedWakeup = true; }\n",
                     "    void wakeForMessage(void) override\n"
                     "    {\n"
                     "        if (screenTimeout > 0) {\n"
                     "            msgWakeAt = millis();\n"
                     "            if (powerSaving)\n"
                     "                forcedWakeup = true;\n"
                     "            lv_display_trigger_activity(NULL);\n"
                     "        }\n"
                     "    }\n")
                edit(drv, "    bool forcedWakeup;\n", "    uint32_t msgWakeAt = 0;\n")
            else:
                edit(drv, "    bool isPowersaving(void) override { return powerSaving; }\n",
                     "    void wakeForMessage(void) override\n"
                     "    {\n"
                     "        if (screenTimeout > 0) {\n"
                     "            msgWakeAt = millis();\n"
                     "            if (powerSaving) {\n"
                     "                powerSaving = false;\n"
                     "                lgfx->powerSaveOff();\n"
                     "                lgfx->wakeup();\n"
                     "            }\n"
                     "            lv_display_trigger_activity(NULL);\n"
                     "        }\n"
                     "    }\n")
                edit(drv, "    bool powerSaving;\n", "    uint32_t msgWakeAt = 0;\n")

        edit(drv, "    if ((screenTimeout > 0 && lv_display_get_inactive_time(%s) > screenTimeout) || powerSaving ||\n" % INACT,
             "    if (msgWakeAt && lv_display_get_inactive_time(NULL) + 1000 < millis() - msgWakeAt)\n"
             "        msgWakeAt = 0; // something touched the screen after the wake, back to the normal timeout\n"
             "    uint32_t effTimeout = (msgWakeAt && screenTimeout > 8000) ? 8000 : screenTimeout;\n"
             "    if ((effTimeout > 0 && lv_display_get_inactive_time(NULL) > effTimeout) || powerSaving ||\n", "replace")
        msg_alert = ""
        if "advanced" in feat:
            tft_decl += 'extern "C" void emoji_message_alert(void);\n'
            tft_decl += 'extern "C" bool emoji_quiet_now(void);\n'
            msg_alert = "        if (!db.silent && (!db.channel[ch].settings.module_settings.is_muted || to != UINT32_MAX) && !emoji_quiet_now())\n            emoji_message_alert();\n"

        anchor_wake = [
            "    if (!restore) {\n        if (!db.channel[ch].settings.module_settings.is_muted && !emoji_quiet_now())\n            displaydriver->wakeForMessage();\n        // display msg popup if not already viewing the messages\n",
            "    if (!restore) {\n        if (!db.channel[ch].settings.module_settings.is_muted)\n            displaydriver->wakeForMessage();\n        // display msg popup if not already viewing the messages\n",
            "    if (!restore) {\n        // display msg popup if not already viewing the messages\n",
        ]
        edit(tft, anchor_wake,
             "    if (!restore) {\n"
             + msg_alert +
             "        if (!db.channel[ch].settings.module_settings.is_muted" + (" && !emoji_quiet_now()" if "advanced" in feat else "") + ")\n"
             "            displaydriver->wakeForMessage();\n"
             "        // display msg popup if not already viewing the messages\n", "replace")


    # screensaver: dim page with clock and status, double tap to unlock
    if "screensaver" in feat:
        copy("emoji_screensaver.cpp.in", dst)
        copy("mui_font_clock_64.c.in", dst)
        inc = os.path.join(dst, "emoji_stickman.inc")
        if "stickman" in feat:
            copy("emoji_stickman.cpp.in", dst, "emoji_stickman.inc")
        elif os.path.exists(inc):
            os.remove(inc)
        # the TJPGD wrapper only accepts JFIF files from memory; EXIF files (phones, most downloads) start FF D8 FF E1
        edit(os.path.join(LV, "src", "libs", "tjpgd", "lv_tjpgd.c"),
             "    const uint8_t jpg_signature[] = {0xFF, 0xD8, 0xFF,  0xE0,  0x00,  0x10, 0x4A,  0x46, 0x49, 0x46};\n",
             "    const uint8_t jpg_signature[] = {0xFF, 0xD8, 0xFF};\n", "replace")
        tft_decl += ('extern "C" void emoji_wifi_vault_add(const char *, const char *);\n'
'extern "C" void emoji_ss_init(void (*)(uint32_t *));\n'
                     'extern "C" void emoji_ss_metrics(uint32_t, float, float);\n'
                     'extern "C" void emoji_ss_message(const char *, const char *);\n')
        edit(tft, "    lv_obj_add_event_cb(objects.message_input_area, ui_event_message_ready, LV_EVENT_ALL, NULL);\n",
             "    emoji_ss_init([](uint32_t *d) {\n"
             "        d[0] = THIS->nodesOnline;\n"
             "        d[1] = THIS->nodeCount;\n"
             "        d[2] = THIS->unreadMessages;\n"
             "        d[3] = THIS->db.module_config.mqtt.enabled;\n"
             "        d[4] = THIS->db.config.network.wifi_enabled;\n"
             "    });\n", "before")
        edit(tft, "        if (it->first == ownNode) {\n            sprintf(buf, _(\"Util %0.1f%%  Air %0.1f%%\"), chUtil, airUtil);\n",
             "        if (it->first == ownNode) {\n"
             "            emoji_ss_metrics(bat_level, chUtil, airUtil);\n"
             "            sprintf(buf, _(\"Util %0.1f%%  Air %0.1f%%\"), chUtil, airUtil);\n", "replace")
        edit(tft, "void TFTView_320x240::newMessage(uint32_t from, uint32_t to, uint8_t ch, const char *msg, uint32_t &msgTime, bool restore)\n{\n",
             "    if (!restore) {\n"
             "        auto itn = nodes.find(from);\n"
             "        emoji_ss_message(itn != nodes.end() ? lv_label_get_text(itn->second->LV_OBJ_IDX(node_lbl_idx)) : \"\", msg);\n"
             "    }\n")
        tmo = "effTimeout" if "wake" in feat else "screenTimeout"
        edit(drv, "template <class LGFX> void LGFXDriver<LGFX>::task_handler(void)\n{",
             'extern "C" int emoji_ss_poll(uint32_t, uint32_t, bool, uint32_t, int *);\n', "before")
        ia = "NULL" if "wake" in feat else INACT
        edit(drv, "    if ((%s > 0 && lv_display_get_inactive_time(%s) > %s) || powerSaving ||\n" % (tmo, ia, tmo),
             "    int ssBl = -1;\n"
             "    int ssStage = emoji_ss_poll(lv_display_get_inactive_time(NULL), %s, powerSaving, lastBrightness, &ssBl);\n"
             "    if (ssStage == 3) {\n"
             "        lgfx->setBrightness(lastBrightness);\n"
             "        lv_display_trigger_activity(NULL);\n"
             "    }\n"
             "    if (ssStage == 1 && !powerSaving) { // while the panel sleeps, the driver wake code must still run\n"
             "        if (ssBl >= 0 && (int)lgfx->getBrightness() != ssBl)\n"
             "            lgfx->setBrightness(ssBl);\n"
             "    } else if ((%s > 0 && lv_display_get_inactive_time(NULL) > %s) || powerSaving ||\n" % (tmo, tmo, tmo), "replace")

    # a panel that glitches when put to sleep (green screen and noise after waking) can stay awake and only lose its backlight:
    # add -D RIV_NO_PANEL_SLEEP=1 to the env, the default keeps the stock sleep and wake
    s_drv, c_drv = read(drv)
    if "RIV_NO_PANEL_SLEEP" not in s_drv:
        for call in ("lgfx->sleep();", "lgfx->powerSaveOn();", "lgfx->powerSaveOff();", "lgfx->wakeup();"):
            s_drv = s_drv.replace(call, "if (!RIV_NO_PANEL_SLEEP) " + call)
        s_drv = "#ifndef RIV_NO_PANEL_SLEEP\n#define RIV_NO_PANEL_SLEEP 0\n#endif\n" + s_drv
        write(drv, s_drv, c_drv)

    # touch wake for boards without touch interrupt pin (XPT2046 on SPI with pin_int = -1):
    # record driver instance so touchpad_read can request wake when touched during sleep
    s_drv, c_drv = read(drv)
    if "s_instance" not in s_drv or "touchWakeArmed" not in s_drv:
        if "s_instance" not in s_drv:
            s_drv = s_drv.replace("    static LGFX *lgfx;\n",
                                  "    static LGFX *lgfx;\n    static LGFXDriver<LGFX> *s_instance;\n")
            s_drv = s_drv.replace("template <class LGFX> LGFX *LGFXDriver<LGFX>::lgfx = nullptr;\n",
                                  "template <class LGFX> LGFX *LGFXDriver<LGFX>::lgfx = nullptr;\n"
                                  "template <class LGFX> LGFXDriver<LGFX> *LGFXDriver<LGFX>::s_instance = nullptr;\n")
            s_drv = s_drv.replace("    lgfx = this->tft;\n",
                                  "    lgfx = this->tft;\n    s_instance = this;\n")

        # instant sleep on manual screen lock (Settings button long press)
        if "isScreenLocked())\n                        lgfx->setBrightness(0);" not in s_drv:
            s_drv = s_drv.replace(
                "                if (!powerSaving) {\n                    // dim display brightness slowly down\n",
                "                if (!powerSaving) {\n"
                "                    if (DisplayDriver::view->isScreenLocked())\n"
                "                        lgfx->setBrightness(0);\n"
                "                    // dim display brightness slowly down\n"
            )

        # single-touch touchpad_read with armed wake
        old_touch_p1 = (
            "    if (!touched) {\n        data->state = LV_INDEV_STATE_REL;\n    } else {\n"
            "        if (s_instance && s_instance->powerSaving) {\n"
            "            s_instance->forcedWakeup = true;\n"
            "            lv_display_trigger_activity(NULL);\n"
            "        }\n"
        )
        old_touch_p2 = "    if (!touched) {\n        data->state = LV_INDEV_STATE_REL;\n    } else {\n"

        new_touch = (
            "    static bool touchWakeArmed = false;\n"
            "    if (!touched) {\n"
            "        data->state = LV_INDEV_STATE_REL;\n"
            "        touchWakeArmed = true;\n"
            "    } else {\n"
            "        if (s_instance && s_instance->powerSaving) {\n"
            "            if (touchWakeArmed) {\n"
            "                touchWakeArmed = false;\n"
            "                s_instance->forcedWakeup = true;\n"
            "                lv_display_trigger_activity(NULL);\n"
            "            }\n"
            "        } else {\n"
            "            touchWakeArmed = false;\n"
            "        }\n"
        )
        if old_touch_p1 in s_drv:
            s_drv = s_drv.replace(old_touch_p1, new_touch)
        elif old_touch_p2 in s_drv:
            s_drv = s_drv.replace(old_touch_p2, new_touch)

        # multi-touch / gesture touchpad_read with armed wake
        old_multi_p1 = (
            "    prevCount = count;\n"
            "    if (count > 0 && s_instance && s_instance->powerSaving) {\n"
            "        s_instance->forcedWakeup = true;\n"
            "        lv_display_trigger_activity(NULL);\n"
            "    }\n\n    lv_indev_gesture_recognizers_update"
        )
        old_multi_p2 = "    prevCount = count;\n\n    lv_indev_gesture_recognizers_update"

        new_multi = (
            "    prevCount = count;\n"
            "    static bool touchWakeArmed = false;\n"
            "    if (count == 0) {\n"
            "        touchWakeArmed = true;\n"
            "    } else {\n"
            "        if (s_instance && s_instance->powerSaving) {\n"
            "            if (touchWakeArmed) {\n"
            "                touchWakeArmed = false;\n"
            "                s_instance->forcedWakeup = true;\n"
            "                lv_display_trigger_activity(NULL);\n"
            "            }\n"
            "        } else {\n"
            "            touchWakeArmed = false;\n"
            "        }\n"
            "    }\n\n    lv_indev_gesture_recognizers_update"
        )
        if old_multi_p1 in s_drv:
            s_drv = s_drv.replace(old_multi_p1, new_multi)
        elif old_multi_p2 in s_drv:
            s_drv = s_drv.replace(old_multi_p2, new_multi)

        # restore !isScreenLocked() if it was stripped
        wake_target = "                        (screenTimeout + 50 > lv_display_get_inactive_time(lv_display_get_default()))) {\n"
        if wake_target in s_drv:
            s_drv = s_drv.replace(
                wake_target,
                "                        (screenTimeout + 50 > lv_display_get_inactive_time(lv_display_get_default()) &&\n"
                "                         !DisplayDriver::view->isScreenLocked())) {\n"
            )

        if "screensaver" in feat and "uint32_t wakeBl" not in s_drv:
            s_drv = s_drv.replace(
                "                            lgfx->setBrightness(lastBrightness);\n",
                "                            uint32_t wakeBl = (ssStage == 1 && ssBl >= 0) ? (uint32_t)ssBl : lastBrightness;\n"
                "                            lgfx->setBrightness(wakeBl);\n"
            )
        write(drv, s_drv, c_drv)
        print("Patched LGFXDriver touch wake and instant lock")

    # The node list keeps raw pointers into the input group's linked list (to order the buttons) and moves list entries with them for
    # every packet. Removing objects from the group (Advanced menu, screensaver) frees those entries, so the next packet from a node writes
    # through a stale pointer: the node panics (StoreProhibited) a few seconds or minutes later. Look the entries up each time instead.
    if "advanced" in feat or "screensaver" in feat:
        tft_decl += "static void *emojiLLFind(lv_ll_t *ll, void *obj) { for (void *n = _lv_ll_get_head(ll); n; n = _lv_ll_get_next(ll, n)) if (*(void **)n == obj) return n; return nullptr; }\n"
        edit(tft, "            void *after = children[i + 1]->LV_OBJ_IDX(node_btn_idx)->user_data;\n            _lv_ll_move_before(lv_group_ll, nodeButton->user_data, after);\n",
             "            void *after = emojiLLFind(lv_group_ll, children[i + 1]->LV_OBJ_IDX(node_btn_idx));\n"
             "            void *mine = emojiLLFind(lv_group_ll, nodeButton);\n"
             "            if (after && mine)\n"
             "                _lv_ll_move_before(lv_group_ll, mine, after);\n", "replace")
        edit(tft, "            void *act = it->second->LV_OBJ_IDX(node_btn_idx)->user_data;\n            if (lv_group_ll && act)\n                _lv_ll_move_before(lv_group_ll, act, _lv_ll_get_next(lv_group_ll, topNodeLL));\n",
             "            void *act = emojiLLFind(lv_group_ll, it->second->LV_OBJ_IDX(node_btn_idx));\n"
             "            void *top = emojiLLFind(lv_group_ll, objects.node_button);\n"
             "            if (lv_group_ll && act && top)\n"
             "                _lv_ll_move_before(lv_group_ll, act, _lv_ll_get_next(lv_group_ll, top));\n", "replace")

    # declarations, one block per file
    if tft_decl:
        seen = set()
        for l in tft_decl.split("\n"):
            if l and not (l in seen or seen.add(l)):
                edit(tft, SD_INC, l + "\n")  # one line at a time, so a changed block is not injected a second time
    if vc_decl:
        edit(vc, VC_FN, vc_decl, "before")

    patch_mui_node_and_channel(tft, UI)


if os.path.isdir(UI) and os.path.isdir(LV):
    main()

if os.path.isdir(UI) and os.path.isdir(LV):
    if MISSES:
        print("MUI-EXTRAS: %d patch anchor(s) NOT found in this library version, those features are missing or broken:" % len(MISSES))
        for m in MISSES:
            print("   -", m)
    else:
        print("MUI-EXTRAS: all patch anchors found")

    # MQTT proxy safeguard & force override
    mqtt_src = env.subst("$PROJECT_DIR/src/mqtt/MQTT.cpp")
    if os.path.exists(mqtt_src):
        decl = ('extern "C" bool emoji_effective_mqtt_proxy(bool, bool) __attribute__((weak));\n'
                '#define EFFECTIVE_MQTT_PROXY (emoji_effective_mqtt_proxy ? '
                'emoji_effective_mqtt_proxy(moduleConfig.mqtt.proxy_to_client_enabled, isConnectedToNetwork()) : '
                'moduleConfig.mqtt.proxy_to_client_enabled)\n')
        edit(mqtt_src, '#include "MQTT.h"\n', decl, "after")
        edit(mqtt_src, "moduleConfig.mqtt.proxy_to_client_enabled || isConnectedToNetwork()",
             "EFFECTIVE_MQTT_PROXY || isConnectedToNetwork()", "replace")
        edit(mqtt_src, "if (!moduleConfig.mqtt.proxy_to_client_enabled)",
             "if (!EFFECTIVE_MQTT_PROXY)", "replace")
        edit(mqtt_src, "if (moduleConfig.mqtt.proxy_to_client_enabled) {",
             "if (EFFECTIVE_MQTT_PROXY) {", "replace")
        edit(mqtt_src, "if (moduleConfig.mqtt.proxy_to_client_enabled || this->isConnectedDirectly())",
             "if (EFFECTIVE_MQTT_PROXY || this->isConnectedDirectly())", "replace")
        edit(mqtt_src, "        if (mqttQueue.enqueue(entry, 0) == false) {\n            LOG_CRIT(\"Can't add msg to mqttQueue\");\n            abort();\n        }",
             "        if (mqttQueue.enqueue(entry, 0) == false) {\n            LOG_WARN(\"Can't add msg to mqttQueue, packet dropped\");\n            delete entry;\n        }", "replace")
        edit(mqtt_src, "bool MQTT::publish(const char *topic, const char *payload, bool retained)\n{\n    if (moduleConfig.mqtt.proxy_to_client_enabled) {",
             "bool MQTT::publish(const char *topic, const char *payload, bool retained)\n{\n    if (EFFECTIVE_MQTT_PROXY) {", "replace")
        edit(mqtt_src, "bool MQTT::publish(const char *topic, const uint8_t *payload, size_t length, bool retained)\n{\n    if (moduleConfig.mqtt.proxy_to_client_enabled) {",
             "bool MQTT::publish(const char *topic, const uint8_t *payload, size_t length, bool retained)\n{\n    if (EFFECTIVE_MQTT_PROXY) {", "replace")
        edit(mqtt_src, "void MQTT::reconnect()\n{\n    isConnected = false;\n    if (wantsLink()) {\n        if (moduleConfig.mqtt.proxy_to_client_enabled) {",
             "void MQTT::reconnect()\n{\n    isConnected = false;\n    if (wantsLink()) {\n        if (EFFECTIVE_MQTT_PROXY) {", "replace")
        edit(mqtt_src, "int32_t MQTT::runOnce()\n{\n    perhapsReportToMap();\n\n    // If connected poll rapidly, otherwise only occasionally check for a wifi connection change and ability to contact server\n    if (moduleConfig.mqtt.proxy_to_client_enabled) {",
             "int32_t MQTT::runOnce()\n{\n    perhapsReportToMap();\n\n    // If connected poll rapidly, otherwise only occasionally check for a wifi connection change and ability to contact server\n    if (EFFECTIVE_MQTT_PROXY) {", "replace")
        edit(mqtt_src, "void MQTT::publishQueuedMessages()\n{\n    if (mqttQueue.isEmpty())\n        return;\n\n    if (!moduleConfig.mqtt.proxy_to_client_enabled && !isConnected)",
             "void MQTT::publishQueuedMessages()\n{\n    if (mqttQueue.isEmpty())\n        return;\n\n    if (!EFFECTIVE_MQTT_PROXY && !isConnected)", "replace")
        edit(mqtt_src, "    if (!moduleConfig.mqtt.map_reporting_enabled || !moduleConfig.mqtt.map_report_settings.should_report_location ||\n        !(moduleConfig.mqtt.proxy_to_client_enabled || isConnectedDirectly()))",
             "    if (!moduleConfig.mqtt.map_reporting_enabled || !moduleConfig.mqtt.map_report_settings.should_report_location ||\n        !(EFFECTIVE_MQTT_PROXY || isConnectedDirectly()))", "replace")

    # the phone-API file manifest walks the whole data folder; with the full offline tile pack in /maps that took about
    # 10 s per config request, longer than the screen waits, so the UI never finished starting. Tiles are not manifest files.
    fs_src = env.subst("$PROJECT_DIR/src/FSCommon.cpp")
    if os.path.exists(fs_src):
        edit(fs_src, "            if (levels && hasSubDirPath) {\n                collectFiles(pathBuffer, levels - 1, maxCount, filenames, wasLimited);\n",
             "            if (levels && hasSubDirPath && strcmp(pathBuffer, \"maps\") != 0 && strcmp(pathBuffer, \"/maps\") != 0) {\n                collectFiles(pathBuffer, levels - 1, maxCount, filenames, wasLimited);\n", "replace")

    # ExternalNotificationModule ringtone fix
    ext_src = env.subst("$PROJECT_DIR/src/modules/ExternalNotificationModule.cpp")
    if os.path.exists(ext_src):
        edit(ext_src, "this->handleSetRingtone(request->set_canned_message_module_messages);",
             "this->handleSetRingtone(request->set_ringtone_message);", "replace")
        # fast tunes (b=565, d=32 is ~13 ms per note) were stretched by the 10 ms task poll and 25 ms thread: poll at 1-2 ms
        edit(ext_src, "            vTaskDelay(pdMS_TO_TICKS(10));\n        } else {", "            vTaskDelay(pdMS_TO_TICKS(1));\n        } else {", "replace")
        edit(ext_src, "#define EXT_NOTIFICATION_FAST_THREAD_MS 25", "#define EXT_NOTIFICATION_FAST_THREAD_MS 2", "replace")

    # buzzer volume for the RTTTL library that plays message alerts: shorten the duty of the LEDC tone
    rtttl_lib = LIB + "/NonBlockingRTTTL/src/NonBlockingRtttl.cpp"
    if os.path.exists(rtttl_lib):
        edit(rtttl_lib, '#include "NonBlockingRtttl.h"\n', 'extern "C" uint8_t emoji_buzzer_volume(void) __attribute__((weak));\nextern "C" float emoji_buzzer_duty(float) __attribute__((weak));\n')
        orig_tone = "    void tone(uint8_t pin, unsigned int frq, unsigned long duration) {\n      ledcWriteTone(pin, frq);\n    }"
        old_tone = "    void tone(uint8_t pin, unsigned int frq, unsigned long duration) {\n      ledcWriteTone(pin, frq);\n      if (emoji_buzzer_volume && emoji_buzzer_volume() < 100)\n        ledcWrite(pin, (uint32_t)(((1u << LEDC_RESOLUTION) - 1) * emoji_buzzer_volume() / 200));\n    }"
        edit(rtttl_lib, [orig_tone, old_tone],
             "    void tone(uint8_t pin, unsigned int frq, unsigned long duration) {\n      ledcWriteTone(pin, frq);\n      if (emoji_buzzer_duty && emoji_buzzer_volume && emoji_buzzer_volume() < 100)\n        ledcWrite(pin, (uint32_t)(((1u << LEDC_RESOLUTION) - 1) * emoji_buzzer_duty((float)frq)));\n    }", "replace")

    # the satellite count of the own position for the compass screen
    edit(os.path.join(UI, "source", "graphics", "TFT", "TFTView_320x240.cpp"), "    emoji_tools_record_pos(nodeNum, lat, lon, alt, nodeNum == ownNode);\n",
         "    if (nodeNum == ownNode)\n        emoji_tools_record_sats(sats);\n", "after")

    # a GPS wired receive-only cannot answer the probe commands, so the module was never detected and nothing was read
    gps_src = env.subst("$PROJECT_DIR/src/gps/GPS.cpp")
    if os.path.exists(gps_src):
        edit(gps_src, "    new_gps->tx_gpio = _tx_gpio;\n",
             "#if defined(GPS_RX_ONLY)\n    new_gps->gnssModel = GNSS_MODEL_GENERIC_NMEA; // only the module's TX is wired, nothing answers a probe\n#endif\n", "after")

    phone_src = env.subst("$PROJECT_DIR/src/mesh/PhoneAPI.cpp")
    if os.path.exists(phone_src):
        pdecl = 'extern "C" bool emoji_effective_mqtt_proxy(bool, bool) __attribute__((weak));\n#if HAS_WIFI && !defined(ARCH_PORTDUINO)\n#include <WiFi.h>\n#endif\n'
        edit(phone_src, '#include "PhoneAPI.h"\n', pdecl, "after")
        safe_chk = ("#if HAS_WIFI && !defined(ARCH_PORTDUINO)\n"
                    "            bool netConnected = (WiFi.getMode() != WIFI_OFF && WiFi.isConnected());\n"
                    "#else\n"
                    "            bool netConnected = false;\n"
                    "#endif\n"
                    "            if (mqtt && (emoji_effective_mqtt_proxy ? emoji_effective_mqtt_proxy(moduleConfig.mqtt.proxy_to_client_enabled, netConnected) : moduleConfig.mqtt.proxy_to_client_enabled) && moduleConfig.mqtt.enabled &&")
        edit(phone_src, "if (mqtt && moduleConfig.mqtt.proxy_to_client_enabled && moduleConfig.mqtt.enabled &&",
             safe_chk, "replace")
        phone_old = ("        case meshtastic_ToRadio_mqttClientProxyMessage_tag:\n"
                     "            LOG_TRACE(\"Got MqttClientProxy message\");")
        phone_new = ("        case meshtastic_ToRadio_mqttClientProxyMessage_tag: {\n"
                     "            LOG_TRACE(\"Got MqttClientProxy message\");")
        edit(phone_src, phone_old, phone_new, "replace")
        phone_end_old = ("                LOG_WARN(\"MqttClientProxy received but proxy disabled, no up/downlink channels, or map reporting off\");\n"
                         "            }\n"
                         "            break;\n"
                         "#endif")
        phone_end_new = ("                LOG_WARN(\"MqttClientProxy received but proxy disabled, no up/downlink channels, or map reporting off\");\n"
                         "            }\n"
                         "            break;\n"
                         "        }\n"
                         "#endif")
        edit(phone_src, phone_end_old, phone_end_new, "replace")
