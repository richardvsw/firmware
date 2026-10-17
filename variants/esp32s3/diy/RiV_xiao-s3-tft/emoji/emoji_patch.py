import os
import shutil

Import("env")

# EMOJI: BUILT-IN FONT WITH 33 EMOJI, AN EMOJI KEY ON THE KEYBOARD, MORE EMOJI LOAD FROM /emoji.bin ON THE SD CARD
HERE = env.subst("$PROJECT_DIR/variants/esp32s3/diy/RiV_xiao-s3-tft/emoji")
LIB = env.subst("$PROJECT_DIR/.pio/libdeps/${PIOENV}")
UI = os.path.join(LIB, "meshtastic-device-ui")
LV = os.path.join(LIB, "lvgl")

KEY = "\U0001F642"
ROW1 = ["\U0001F600", "\U0001F602", "\U0001F642", "\U0001F609", "\U0001F60D", "\U0001F622", "\U0001F62E", "\U0001F60E", "\U0001F621", "\U0001F914"]
ROW2 = ["\U0001F44D", "\U0001F44E", "\U0001F44B", "\U0001F64F", "\U0001F44C", "\u270C", "\U0001F4AA", "\u2764", "\U0001F389", "\U0001F37A", "\u2615"]
ROW3 = ["\U0001F525", "\u2B50", "\u2705", "\u274C", "\u26A0", "\u2753", "\U0001F4CD", "\U0001F50B", "\U0001F4E1", "\U0001F697", "\U0001F3E0", "\u26F0"]


def cstr(ch):
    return '"' + "".join("\\x%02X" % b for b in ch.encode("utf-8")) + '"'


def read(p):
    with open(p, "r", encoding="utf-8", newline="") as f:
        s = f.read()
    return s.replace("\r\n", "\n"), "\r\n" in s


def write(p, s, crlf):
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s.replace("\n", "\r\n") if crlf else s)


def patch(path, old, new):
    if not os.path.exists(path):
        return
    s, crlf = read(path)
    if new in s or old not in s:
        return
    write(path, s.replace(old, new, 1), crlf)
    print("Patched", path)


if os.path.isdir(UI) and os.path.isdir(LV):
    dst = os.path.join(UI, "source", "graphics", "common")
    # envs ending in -emoji carry the whole colour set and the whole monochrome font in flash, no SD card needed
    full = "_all" if env.subst("${PIOENV}").endswith("-emoji") else ""
    shutil.copyfile(os.path.join(HERE, "emoji_font%s.c.in" % full), os.path.join(dst, "emoji_font.c"))
    shutil.copyfile(os.path.join(HERE, "emoji_sd.cpp.in"), os.path.join(dst, "emoji_sd.cpp"))
    shutil.copyfile(os.path.join(HERE, "emoji_color.cpp.in"), os.path.join(dst, "emoji_color.cpp"))
    inc, _ = read(os.path.join(HERE, "emoji_color_builtin%s.inc" % full))
    write(os.path.join(dst, "emoji_color_builtin.inc"), inc.replace("static const uint8_t builtin_data[]", "alignas(4) static const uint8_t builtin_data[]"), False)

    # every Montserrat size falls back to the emoji font
    fonts = [os.path.join(LV, "src", "font", "lv_font_montserrat_%d.c" % n) for n in (12, 14, 16, 20)]
    fonts += [os.path.join(UI, "generated", d, "ui_font_montserrat_%d.c" % n)
              for d in ("ui_320x240", "ui_240x320") for n in (12, 14, 16, 20)]
    for p in fonts:
        if not os.path.exists(p):
            continue
        s, crlf = read(p)
        if "&ui_emoji_color_font" in s:
            continue
        if "&ui_emoji_font" in s:
            # upgrade a file patched for the monochrome-only build
            s = s.replace("&ui_emoji_font", "&ui_emoji_color_font").replace("extern lv_font_t ui_emoji_font;", "extern lv_font_t ui_emoji_color_font;")
            write(p, s, crlf)
            print("Patched", p)
            continue
        s = s.replace(".fallback = NULL,", ".fallback = &ui_emoji_color_font,", 1)
        if "&ui_emoji_color_font" not in s:
            # LVGL's own font files have no fallback line
            s = s.replace(".dsc = &font_dsc ", ".dsc = &font_dsc, ", 1)
            s = s.replace("*/\n};", "*/\n    .fallback = &ui_emoji_color_font\n};", 1)
        marker = "/*Initialize a public general font descriptor*/"
        if marker not in s:
            continue
        s = s.replace(marker, "extern lv_font_t ui_emoji_color_font;\n" + marker, 1)
        write(p, s, crlf)
        print("Patched", p)

    # keyboard: emoji key after OK on the text pages, emoji page as user mode 1
    kb = os.path.join(LV, "src", "widgets", "keyboard", "lv_keyboard.c")
    if os.path.exists(kb):
        s, crlf = read(kb)
        if "EMOJI_KEY" not in s:
            s = s.replace("#define LV_KB_BTN(width) LV_BUTTONMATRIX_CTRL_POPOVER | width\n",
                          "#define LV_KB_BTN(width) LV_BUTTONMATRIX_CTRL_POPOVER | width\n#define EMOJI_KEY " + cstr(KEY) + "\n", 1)
            s = s.replace('LV_SYMBOL_LEFT, " ", LV_SYMBOL_RIGHT, LV_SYMBOL_OK, ""',
                          'LV_SYMBOL_LEFT, " ", LV_SYMBOL_RIGHT, LV_SYMBOL_OK, EMOJI_KEY, ""', 2)
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
            s = s.replace('    if(lv_strcmp(txt, "abc") == 0) {',
                          "    if(lv_strcmp(txt, EMOJI_KEY) == 0 && keyboard->mode != LV_KEYBOARD_MODE_USER_1) {\n"
                          "        keyboard->mode = LV_KEYBOARD_MODE_USER_1;\n"
                          "        lv_buttonmatrix_set_map(obj, kb_map[LV_KEYBOARD_MODE_USER_1]);\n"
                          "        lv_keyboard_update_ctrl_map(obj);\n"
                          "        return;\n"
                          "    }\n"
                          '    if(lv_strcmp(txt, "abc") == 0) {', 1)
            write(kb, s, crlf)
            print("Patched", kb)

    # the image font draws the colour emoji
    patch(os.path.join(UI, "include", "lv_conf.h"), "#define LV_USE_IMGFONT 0", "#define LV_USE_IMGFONT 1")
    # lv_binfont_create_from_buffer needs the memory file system
    patch(os.path.join(UI, "include", "lv_conf.h"), "#define LV_USE_FS_MEMFS 0", "#define LV_USE_FS_MEMFS 1")
    patch(os.path.join(UI, "include", "lv_conf.h"), "#define LV_FS_MEMFS_LETTER '" + chr(92) + "0'", "#define LV_FS_MEMFS_LETTER 'M'")

    # load the SD font once the card is mounted
    tft = os.path.join(UI, "source", "graphics", "TFT", "TFTView_320x240.cpp")
    patch(tft, '        ILOG_DEBUG("SdCard init successful, card type: %d", sdCard->cardType());',
          '        ILOG_DEBUG("SdCard init successful, card type: %d", sdCard->cardType());\n        emoji_load_from_sd();')
    patch(tft, "bool TFTView_320x240::updateSDCard(void)",
          'extern "C" void emoji_load_from_sd(void);\nbool TFTView_320x240::updateSDCard(void)')
    patch(tft, 'extern "C" void emoji_load_from_sd(void);\n',
          'extern "C" void emoji_load_from_sd(void);\nextern "C" void emoji_color_init(void);\n')
    patch(tft, "bool TFTView_320x240::updateSDCard(void)\n{\n    formatSD = false;",
          "bool TFTView_320x240::updateSDCard(void)\n{\n    emoji_color_init();\n    formatSD = false;")

    # backlight diagnostic: with -DBL_FIXED_TEST the dimming logic is off, brightness is set once and every change request is logged
    drv = os.path.join(UI, "include", "graphics", "driver", "LGFXDriver.h")
    patch(drv, "template <class LGFX> void LGFXDriver<LGFX>::task_handler(void)\n{\n",
          "template <class LGFX> void LGFXDriver<LGFX>::task_handler(void)\n{\n"
          "#ifdef BL_FIXED_TEST\n"
          "    {\n"
          "        static bool blDone = false;\n"
          "        if (!blDone) {\n"
          "            blDone = true;\n"
          "            ILOG_INFO(\"BL fixed test: brightness 180, dimming logic off\");\n"
          "            lgfx->setBrightness(180);\n"
          "        }\n"
          "        if (!calibrating)\n"
          "            DisplayDriver::task_handler();\n"
          "        return;\n"
          "    }\n"
          "#endif\n")
    patch(drv, "template <class LGFX> void LGFXDriver<LGFX>::setBrightness(uint8_t brightness)\n{\n",
          "template <class LGFX> void LGFXDriver<LGFX>::setBrightness(uint8_t brightness)\n{\n"
          "#ifdef BL_FIXED_TEST\n"
          "    ILOG_INFO(\"BL set request %d ignored\", brightness);\n"
          "    return;\n"
          "#endif\n")

    # the UI fonts already hold monochrome glyphs for these code points; skip them when a colour image exists so the colour font wins
    for d in ("ui_320x240", "ui_240x320"):
        for n in (12, 14, 16, 20):
            p = os.path.join(UI, "generated", d, "ui_font_montserrat_%d.c" % n)
            if not os.path.exists(p):
                continue
            s, crlf = read(p)
            if "emoji_font_dsc_wrapper" in s:
                continue
            marker = "/*Initialize a public general font descriptor*/"
            wrapper = ("extern bool emoji_color_has(uint32_t cp);\n"
                       "static bool emoji_font_dsc_wrapper(const lv_font_t * font, lv_font_glyph_dsc_t * dsc, uint32_t letter, uint32_t letter_next)\n"
                       "{\n"
                       "    if(emoji_color_has(letter)) return false;\n"
                       "    return lv_font_get_glyph_dsc_fmt_txt(font, dsc, letter, letter_next);\n"
                       "}\n")
            if marker in s and ".get_glyph_dsc = lv_font_get_glyph_dsc_fmt_txt," in s:
                s = s.replace(marker, wrapper + marker, 1)
                s = s.replace(".get_glyph_dsc = lv_font_get_glyph_dsc_fmt_txt,", ".get_glyph_dsc = emoji_font_dsc_wrapper,", 1)
                write(p, s, crlf)
                print("Patched", p)

    # colon suggestions in the message box (:fi shows matching emoji above the box)
    shutil.copyfile(os.path.join(HERE, "emoji_suggest.cpp.in"), os.path.join(dst, "emoji_suggest.cpp"))
    shutil.copyfile(os.path.join(HERE, "emoji_names.inc"), os.path.join(dst, "emoji_names.inc"))
    patch(tft, "    lv_obj_add_event_cb(objects.message_input_area, ui_event_message_ready, LV_EVENT_ALL, NULL);\n",
          "    lv_obj_add_event_cb(objects.message_input_area, ui_event_message_ready, LV_EVENT_ALL, NULL);\n"
          "    emoji_suggest_init(objects.message_input_area);\n")
    patch(tft, '#include "graphics/common/SdCard.h"\n',
          '#include "graphics/common/SdCard.h"\nextern "C" void emoji_suggest_init(lv_obj_t *);\n')

    # with the shorter keyboard the message box slid up by the full keyboard height and left a gap above it
    patch(tft, "        lv_anim_set_values(&a1, panelY, kbdPanelBaseY - kb_h);\n",
          "        int32_t gapBelow = (int32_t)v - text_coords.y2;\n"
          "        if (gapBelow < 0)\n"
          "            gapBelow = 0;\n"
          "        int32_t slide = (int32_t)kb_h - gapBelow + 2;\n"
          "        if (slide < 0)\n"
          "            slide = 0;\n"
          "        lv_anim_set_values(&a1, panelY, kbdPanelBaseY - slide);\n")

    # B-48 / RiV-meshBot chat: white background with the bot logo, solid bubbles
    shutil.copyfile(os.path.join(HERE, "meshbot_bg.cpp.in"), os.path.join(dst, "meshbot_bg.cpp"))
    shutil.copyfile(os.path.join(HERE, "meshbot_logo.inc"), os.path.join(dst, "meshbot_logo.inc"))
    patch(tft, 'extern "C" void emoji_suggest_init(lv_obj_t *);\n',
          'extern "C" void emoji_suggest_init(lv_obj_t *);\n'
          'extern "C" void emoji_chat_style(lv_obj_t *, const char *, const char *);\n'
          'extern "C" void emoji_bubble_style(lv_obj_t *, lv_obj_t *, bool);\n')
    shown = ("    lv_obj_t *p = nodes[nodeNum];\n    if (p) {\n"
             "        lv_label_set_text(objects.top_messages_node_label, lv_label_get_text(p->LV_OBJ_IDX(node_lbl_idx)));\n")
    patch(tft, shown,
          shown + "        emoji_chat_style(activeMsgContainer, lv_label_get_text(p->LV_OBJ_IDX(node_lbs_idx)),\n"
                  "                         lv_label_get_text(p->LV_OBJ_IDX(node_lbl_idx)));\n")
    group = "    lv_label_set_text(objects.top_group_chat_label, lv_label_get_text(channel[ch]));\n"
    patch(tft, group, group + "    emoji_chat_style(nullptr, nullptr, nullptr);\n")
    sent = "    add_style_chat_message_style(textLabel);\n"
    patch(tft, sent, sent + "    emoji_bubble_style(textLabel, container, true);\n")
    recv = "    add_style_new_message_style(msgLabel);\n"
    patch(tft, recv, recv + "    emoji_bubble_style(msgLabel, container, false);\n")

    # chat names setting: a settings entry below Language, and the group bubbles use the long name when it is on
    patch(tft, 'extern "C" void emoji_suggest_init(lv_obj_t *);\n',
          'extern "C" void emoji_suggest_init(lv_obj_t *);\n'
          'extern "C" bool emoji_long_names(void);\n'
          'extern "C" void emoji_settings_init(lv_obj_t *);\n')
    patch(tft, "    emoji_suggest_init(objects.message_input_area);\n",
          "    emoji_suggest_init(objects.message_input_area);\n"
          "    emoji_settings_init(objects.basic_settings_language_button);\n")
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
    patch(tft, names_old, names_new)
