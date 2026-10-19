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

ALL = "keyboard emoji chat themes advanced wake compose screensaver"  # meshbot is switched on per env
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
    if anchor not in s:
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


def main():
    dst = os.path.join(UI, "source", "graphics", "common")
    tft = os.path.join(UI, "source", "graphics", "TFT", "TFTView_320x240.cpp")
    vc = os.path.join(dst, "ViewController.cpp")
    drv = os.path.join(UI, "include", "graphics", "driver", "LGFXDriver.h")
    drvbase = os.path.join(UI, "include", "graphics", "driver", "DisplayDriver.h")
    conf = os.path.join(UI, "include", "lv_conf.h")
    # anchors that moved between library versions: use the first form that exists
    tft_text = read(tft)[0] if os.path.exists(tft) else ""
    SD_INC = next((a for a in ('#include "util/ILog.h"\n', '#include "graphics/common/SdCard.h"\n', '#include "ui.h"\n') if a in tft_text),
                  '#include "util/ILog.h"\n')
    drv_text = read(drv)[0] if os.path.exists(drv) else ""
    INACT = "lv_display_get_default()" if "lv_display_get_inactive_time(lv_display_get_default()) > screenTimeout" in drv_text else "NULL"
    VC_FN = "void ViewController::sendTextMessage("

    # keyboard height and the gap it leaves above the message box
    if "keyboard" in feat and kb_pct:
        edit(tft, "lv_obj_set_size(objects.keyboard, LV_PCT(100), LV_PCT(45));",
             "lv_obj_set_size(objects.keyboard, LV_PCT(100), LV_PCT(%s));" % kb_pct, "replace")
        edit(tft, "        lv_anim_set_values(&a1, panelY, kbdPanelBaseY - kb_h);\n",
             "        int32_t gapBelow = (int32_t)v - text_coords.y2;\n"
             "        if (gapBelow < 0)\n"
             "            gapBelow = 0;\n"
             "        int32_t slide = (int32_t)kb_h - gapBelow + 2" + (" + emoji_strip_height()" if "compose" in feat else "") + ";\n"
             "        if (slide < 0)\n"
             "            slide = 0;\n"
             "        lv_anim_set_values(&a1, panelY, kbdPanelBaseY - slide);\n", "replace")

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
                     'extern "C" void emoji_set_reply(uint32_t, bool);\n'
                     'extern "C" int emoji_ctx_mode(void);\n'
                     'extern "C" uint32_t emoji_ctx_target(void);\n'
                     'extern "C" void emoji_ctx_done(void);\n'
                     'extern "C" bool emoji_reaction_apply(uint32_t, const char *, size_t);\n')
        vc_decl += ('extern "C" void emoji_quote_record(uint32_t, const char *);\n'
                    'extern "C" size_t emoji_quote_compose(uint32_t, uint32_t, uint32_t, const char *, size_t, char *, size_t);\n'
                    'extern "C" void emoji_pending_id(uint32_t);\n'
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
        recv_old = ("        view->newMessage(p.from, p.to, p.channel, (const char *)p.decoded.payload.bytes, time);\n"
                    "        log.write(LogMessageEnv(p.from, p.to, p.channel, time, LogMessage::eDefault, false, p.decoded.payload.size,\n"
                    "                                (const uint8_t *)p.decoded.payload.bytes));\n")
        recv_new = ("        if (p.decoded.emoji != 0 &&\n"
                    "            emoji_reaction_apply(p.decoded.reply_id, (const char *)p.decoded.payload.bytes, p.decoded.payload.size))\n"
                    "            break;\n"
                    "        char quoted[DATA_PAYLOAD_LEN + 1];\n"
                    "        size_t quotedLen = emoji_quote_compose(p.id, p.decoded.reply_id, p.decoded.emoji,\n"
                    "                                               (const char *)p.decoded.payload.bytes, p.decoded.payload.size, quoted,\n"
                    "                                               sizeof(quoted));\n"
                    "        emoji_pending_id(p.id);\n"
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
             "    });\n", "before")

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
        copy("emoji_advanced.cpp.in", dst)
        tft_decl += ('extern "C" bool emoji_long_names(void);\n'
                     'extern "C" void emoji_settings_init(lv_obj_t *, lv_obj_t *, lv_obj_t *, void *(*)(void), void (*)(void), '
                     'void (*)(lv_obj_t *));\n'
                     'extern "C" void emoji_settings_host(void *(*)(void), void *(*)(void), void *(*)(void), void *(*)(void), '
                     'void (*)(void), void (*)(void), void (*)(void), void (*)(void));\n'
                     'extern "C" void emoji_settings_host2(void *(*)(void), void (*)(void), int, void (*)(const char *));\n')
        vc_decl += 'extern "C" void emoji_gps_record(const void *);\n'
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
             "    emoji_settings_init(\n"
             "        objects.basic_settings_language_button, objects.main_screen, objects.keyboard,\n"
             "        []() -> void * { return &THIS->db.module_config.mqtt; },\n"
             "        []() { THIS->controller->sendConfig(meshtastic_ModuleConfig_MQTTConfig{THIS->db.module_config.mqtt}); },\n"
             "        [](lv_obj_t *ta) {\n"
             "            lv_obj_move_foreground(objects.keyboard);\n"
             "            THIS->showKeyboard(ta);\n"
             "        });\n")

    # a received message wakes the screen for 8 seconds
    if "wake" in feat:
        edit(drvbase, "    virtual void forceWakeup(void) {}\n", "    virtual void wakeForMessage(void) {}\n")
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
        edit(drv, "    if ((screenTimeout > 0 && lv_display_get_inactive_time(%s) > screenTimeout) || powerSaving ||\n" % INACT,
             "    if (msgWakeAt && lv_display_get_inactive_time(NULL) + 1000 < millis() - msgWakeAt)\n"
             "        msgWakeAt = 0; // something touched the screen after the wake, back to the normal timeout\n"
             "    uint32_t effTimeout = (msgWakeAt && screenTimeout > 8000) ? 8000 : screenTimeout;\n"
             "    if ((effTimeout > 0 && lv_display_get_inactive_time(NULL) > effTimeout) || powerSaving ||\n", "replace")
        edit(tft, "    if (!restore) {\n        // display msg popup if not already viewing the messages\n",
             "    if (!restore) {\n"
             "        if (!db.channel[ch].settings.module_settings.is_muted" + (" && !emoji_quiet_now()" if "advanced" in feat else "") + ")\n"
             "            displaydriver->wakeForMessage();\n"
             "        // display msg popup if not already viewing the messages\n", "replace")
        if "advanced" in feat:
            tft_decl += 'extern "C" bool emoji_quiet_now(void);\n'


    # screensaver: dim page with clock and status, double tap to unlock
    if "screensaver" in feat:
        copy("emoji_screensaver.cpp.in", dst)
        copy("mui_font_clock_64.c.in", dst)
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
             "    if (ssStage == 1) {\n"
             "        if (ssBl >= 0 && (int)lgfx->getBrightness() != ssBl)\n"
             "            lgfx->setBrightness(ssBl);\n"
             "    } else if ((%s > 0 && lv_display_get_inactive_time(NULL) > %s) || powerSaving ||\n" % (tmo, tmo, tmo), "replace")

    # declarations, one block per file
    if tft_decl:
        seen = set()
        blk = "".join(l + "\n" for l in tft_decl.split("\n") if l and not (l in seen or seen.add(l)))
        edit(tft, SD_INC, blk)
    if vc_decl:
        edit(vc, VC_FN, vc_decl, "before")


if os.path.isdir(UI) and os.path.isdir(LV):
    main()

if os.path.isdir(UI) and os.path.isdir(LV):
    if MISSES:
        print("MUI-EXTRAS: %d patch anchor(s) NOT found in this library version, those features are missing or broken:" % len(MISSES))
        for m in MISSES:
            print("   -", m)
    else:
        print("MUI-EXTRAS: all patch anchors found")
