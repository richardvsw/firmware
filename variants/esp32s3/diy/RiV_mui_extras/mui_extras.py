import filecmp
import os
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
    edit(tft_h, "    static void ui_event_NodeButton(lv_event_t *e);\n",
         "    static void ui_event_search_ta(lv_event_t *e);\n    static void ui_event_search_kb(lv_event_t *e);\n", "after")

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
    edit(tft, "void TFTView_320x240::ui_set_active(lv_obj_t *b, lv_obj_t *p, lv_obj_t *tp)\n{",
         decl_block, "before")

    set_active_sb = (
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

    # keyboard height and the gap it leaves above the message box
    if "keyboard" in feat and kb_pct:
        for def_pct in ("45", "34"):
            edit(tft, "lv_obj_set_size(objects.keyboard, LV_PCT(100), LV_PCT(%s));" % def_pct,
                 "lv_obj_set_size(objects.keyboard, LV_PCT(100), LV_PCT(%s));" % kb_pct, "replace")
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
        if "meshbot" in feat:
            # B-48 / RiV-meshBot chat: white background with the bot logo and solid bubbles
            copy("meshbot_bg.cpp.in", dst)
            copy("meshbot_logo.inc", dst)
            tft_decl += ('extern "C" void emoji_chat_style(lv_obj_t *, const char *, const char *);\n'
                         'extern "C" void emoji_bubble_style(lv_obj_t *, lv_obj_t *, bool);\n')
            shown = ("    lv_obj_t *p = nodes[nodeNum];\n    if (p) {\n"
                     "        lv_label_set_text(objects.top_messages_node_label, lv_label_get_text(p->LV_OBJ_IDX(node_lbl_idx)));\n")
            edit(tft, shown, "        emoji_chat_style(activeMsgContainer, lv_label_get_text(p->LV_OBJ_IDX(node_lbs_idx)),\n"
                             "                         lv_label_get_text(p->LV_OBJ_IDX(node_lbl_idx)));\n")
            group = "    lv_label_set_text(objects.top_group_chat_label, lv_label_get_text(channel[ch]));\n"
            edit(tft, group, "    emoji_chat_style(nullptr, nullptr, nullptr);\n")
        else:
            copy("bot_stub.cpp.in", dst, "emoji_bot_stub.cpp")
        tft_decl += ('extern "C" void emoji_suggest_init(lv_obj_t *);\n'
                     'extern "C" bool emoji_long_names(void);\n'
                     'extern "C" void emoji_bubble_register(lv_obj_t *, uint32_t);\n'
                     'extern "C" void emoji_chip_expect(bool);\n'
                     'extern "C" void emoji_name_chip(lv_obj_t *, uint32_t, const char *);\n'
                     'extern "C" void emoji_set_reply(uint32_t, bool);\n'
                     'extern "C" int emoji_ctx_mode(void);\n'
                     'extern "C" uint32_t emoji_ctx_target(void);\n'
                     'extern "C" void emoji_ctx_done(void);\n'
                     'extern "C" bool emoji_reaction_apply(uint32_t, const char *, size_t);\n')
        vc_decl += ('extern "C" void emoji_quote_record(uint32_t, const char *);\n'
                    'extern "C" size_t emoji_quote_compose(uint32_t, uint32_t, uint32_t, const char *, size_t, char *, size_t);\n'
                    'extern "C" void emoji_pending_id(uint32_t);\n'
                    'extern "C" void emoji_record_hops(uint32_t, bool);\n'
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
        tft_decl += ('extern "C" void emoji_compose_init(lv_obj_t *, lv_obj_t *, lv_obj_t *, void (*)(lv_obj_t *));\n'
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
        copy("emoji_advanced.cpp.in", dst)
        themes_cpp3 = os.path.join(UI, "source", "graphics", "TFT", "Themes.cpp")
        edit(themes_cpp3, "void Themes::set(enum Theme th)\n{",
             'extern "C" void emoji_advanced_theme(uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t);\n', "before")
        edit(themes_cpp3, "apply_style_statistics_table_style_ITEMS_DEFAULT();\n",
             "apply_style_statistics_table_style_ITEMS_DEFAULT();\n"
             "    emoji_advanced_theme(THEME(ePanelBg), THEME(eTopPanelBg), THEME(eTopPanelText), THEME(eNodePanelBg), THEME(eNodePanelText), THEME(eSettingsButtonBg), THEME(eSettingsButtonText), THEME(eColorTextLabel), THEME(eNodePanelBorder), THEME(ePanelPressedBg));\n")
        tft_decl += ('extern "C" bool emoji_long_names(void);\n'
                     'extern "C" void emoji_settings_init(lv_obj_t *, lv_obj_t *, lv_obj_t *, void *(*)(void), void (*)(void), '
                     'void (*)(lv_obj_t *));\n'
                     'extern "C" void emoji_settings_host(void *(*)(void), void *(*)(void), void *(*)(void), void *(*)(void), '
                     'void (*)(void), void (*)(void), void (*)(void), void (*)(void));\n'
                     'extern "C" void emoji_settings_host2(void *(*)(void), void (*)(void), int, void (*)(const char *));\n'
                     'extern "C" void emoji_settings_host3(void *(*)(void), void (*)(void), void *(*)(void), void (*)(void));\n'
                     'extern "C" void emoji_settings_channels(void *(*)(int), void (*)(int), int (*)(void));\n')
        vc_decl += 'extern "C" void emoji_gps_record(const void *);\n'
        # renaming the node shows "Rebooting ..." but nothing asks the node to reboot, so the screen would wait for ever
        edit(tft, '                THIS->controller->sendConfig(user, THIS->ownNode);\n                THIS->notifyReboot(true);\n',
             '                THIS->controller->sendConfig(user, THIS->ownNode);\n                THIS->controller->requestReboot(3, THIS->ownNode);\n                THIS->notifyReboot(true);\n', "replace")
        vc_decl += 'extern "C" void emoji_node_flags(uint32_t, bool, bool);\n'
        tft_decl += ('extern "C" void emoji_nodes_host(uint32_t (*)(uint32_t, bool, uint32_t *));\n'
                     'extern "C" bool emoji_node_protected(uint32_t);\n'
                     '#include <vector>\n')
        edit(vc, '                const meshtastic_NodeInfo &node = from.node_info;\n',
             '                emoji_node_flags(node.num, node.is_favorite, node.is_ignored);\n', "after")
        edit(tft, "    lv_obj_add_event_cb(objects.message_input_area, ui_event_message_ready, LV_EVENT_ALL, NULL);\n", NODES_LAMBDA, "before")
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
        tft_decl += ('extern "C" void emoji_ss_init(void (*)(uint32_t *));\n'
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
