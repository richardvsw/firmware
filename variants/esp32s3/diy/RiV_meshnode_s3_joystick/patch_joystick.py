import os
from SCons.Script import Import

Import("env")

DRIVER = os.path.join(env.subst("$PROJECT_DIR"), "variants", "esp32s3", "diy", "RiV_meshnode_s3_joystick", "EncoderInputDriver.cpp.in")


def patch_joystick(source, target, env):
    # 1. DPAD NAVIGATION DRIVER
    filepath_enc = env.subst("$PROJECT_DIR/.pio/libdeps/${PIOENV}/meshtastic-device-ui/source/input/EncoderInputDriver.cpp")
    if os.path.exists(filepath_enc) and os.path.exists(DRIVER):
        with open(DRIVER, "r", encoding="utf-8", newline="") as f:
            new = f.read()
        with open(filepath_enc, "r", encoding="utf-8", newline="") as f:
            old = f.read()
        if new != old:
            with open(filepath_enc, "w", encoding="utf-8", newline="") as f:
                f.write(new)
            print(f"Patched {filepath_enc}")

    # 2. Patch lv_dropdown.c to prevent auto-opening on rotary focus turn and keyboard navigation when not editing
    filepath_drop = env.subst("$PROJECT_DIR/.pio/libdeps/${PIOENV}/lvgl/src/widgets/dropdown/lv_dropdown.c")
    if os.path.exists(filepath_drop):
        with open(filepath_drop, 'r', encoding='utf-8') as f:
            content = f.read()
            
        old_rotary = """    else if(code == LV_EVENT_ROTARY) {
        if(!lv_dropdown_is_open(obj)) {
            lv_dropdown_open(obj);
        }"""

        new_rotary = """    else if(code == LV_EVENT_ROTARY) {
        lv_group_t * g = lv_obj_get_group(obj);
        if(g && !lv_group_get_editing(g)) {
            return;
        }
        if(!lv_dropdown_is_open(obj)) {
            lv_dropdown_open(obj);
        }"""

        old_key = """    else if(code == LV_EVENT_KEY) {
        uint32_t c = lv_event_get_key(e);
        if(c == LV_KEY_RIGHT || c == LV_KEY_DOWN) {"""

        new_key = """    else if(code == LV_EVENT_KEY) {
        lv_group_t * g             = lv_obj_get_group(obj);
        bool editing               = g ? lv_group_get_editing(g) : true;
        lv_indev_type_t indev_type = lv_indev_get_type(lv_indev_active());
        uint32_t c = lv_event_get_key(e);
        if(indev_type == LV_INDEV_TYPE_ENCODER && !editing) {
            if(c != LV_KEY_ENTER) return;
        }
        if(c == LV_KEY_RIGHT || c == LV_KEY_DOWN) {"""

        old_release = """            lv_indev_type_t indev_type = lv_indev_get_type(indev);
            if(indev_type == LV_INDEV_TYPE_ENCODER) {
                lv_group_set_editing(lv_obj_get_group(obj), false);
            }
        }
        else {
            lv_dropdown_open(obj);
        }"""

        new_release = """            lv_indev_type_t indev_type = lv_indev_get_type(indev);
            if(indev_type == LV_INDEV_TYPE_ENCODER) {
                lv_group_set_editing(lv_obj_get_group(obj), false);
            }
        }
        else {
            lv_dropdown_open(obj);
            lv_indev_type_t indev_type = lv_indev_get_type(indev);
            if(indev_type == LV_INDEV_TYPE_ENCODER) {
                lv_group_set_editing(lv_obj_get_group(obj), true);
            }
        }"""

        changed = False
        if old_rotary in content and new_rotary not in content:
            content = content.replace(old_rotary, new_rotary)
            changed = True
        if old_key in content and new_key not in content:
            content = content.replace(old_key, new_key)
            changed = True
        if old_release in content and new_release not in content:
            content = content.replace(old_release, new_release)
            changed = True
            
        if changed:
            print(f"Patched {filepath_drop} (rotary, keys, release) for clean encoder navigation")
            with open(filepath_drop, 'w', encoding='utf-8') as f:
                f.write(content)

    # 6. Patch TFTView_320x240.cpp — shift LVGL encoder focus + editing mode to the
    # on-screen keyboard when it becomes visible, so enc_diff routes LV_KEY_RIGHT/LEFT
    # into the keyboard widget (requires editing mode, not just focus).
    filepath_tft_view = env.subst("$PROJECT_DIR/.pio/libdeps/${PIOENV}/meshtastic-device-ui/source/graphics/TFT/TFTView_320x240.cpp")
    if os.path.exists(filepath_tft_view):
        with open(filepath_tft_view, 'r', encoding='utf-8') as f:
            content = f.read()

        # shown_cb final state (upstream → final, single-pass)
        old_shown_cb = """        static auto shown_cb = [](_lv_anim_t *) { kbdSlideState = eKbdShown; };"""
        new_shown_cb = """        static auto shown_cb = [](_lv_anim_t *) {
            kbdSlideState = eKbdShown;
            if (lv_obj_get_group(objects.keyboard) == NULL)
                lv_group_add_obj(lv_group_get_default(), objects.keyboard);
            lv_group_focus_obj(objects.keyboard);
            lv_group_set_editing(lv_group_get_default(), true);
        };"""

        # shown_cb intermediate → final (TFTView already patched once without editing mode)
        old_shown_cb_v1 = """        static auto shown_cb = [](_lv_anim_t *) {
            kbdSlideState = eKbdShown;
            if (lv_obj_get_group(objects.keyboard) == NULL)
                lv_group_add_obj(lv_group_get_default(), objects.keyboard);
            lv_group_focus_obj(objects.keyboard);
        };"""
        # new_shown_cb is the same final target

        # deleted_cb final state (upstream → final)
        old_deleted_cb = """            lv_obj_add_flag(objects.keyboard, LV_OBJ_FLAG_HIDDEN);
            kbdSlideState = eKbdHidden;
        };"""
        new_deleted_cb = """            lv_obj_add_flag(objects.keyboard, LV_OBJ_FLAG_HIDDEN);
            kbdSlideState = eKbdHidden;
            lv_group_set_editing(lv_group_get_default(), false);
            lv_group_focus_obj(objects.message_input_area);
        };"""

        # deleted_cb intermediate → final (has focus call but no editing=false)
        old_deleted_cb_v1 = """            lv_obj_add_flag(objects.keyboard, LV_OBJ_FLAG_HIDDEN);
            kbdSlideState = eKbdHidden;
            lv_group_focus_obj(objects.message_input_area);
        };"""
        # new_deleted_cb is the same final target

        # showKeyboard else-branch upstream → final
        old_set_textarea = """    lv_keyboard_set_textarea(objects.keyboard, textArea);
}

void TFTView_320x240::hideKeyboard"""
        new_set_textarea = """    lv_keyboard_set_textarea(objects.keyboard, textArea);
    if (textArea != objects.message_input_area) {
        if (lv_obj_get_group(objects.keyboard) == NULL)
            lv_group_add_obj(lv_group_get_default(), objects.keyboard);
        lv_group_focus_obj(objects.keyboard);
        lv_group_set_editing(lv_group_get_default(), true);
    }
}

void TFTView_320x240::hideKeyboard"""

        # showKeyboard else-branch intermediate → final (has focus but no editing mode)
        old_set_textarea_v1 = """    lv_keyboard_set_textarea(objects.keyboard, textArea);
    if (textArea != objects.message_input_area) {
        if (lv_obj_get_group(objects.keyboard) == NULL)
            lv_group_add_obj(lv_group_get_default(), objects.keyboard);
        lv_group_focus_obj(objects.keyboard);
    }
}

void TFTView_320x240::hideKeyboard"""
        # new_set_textarea is the same final target

        changed = False
        for old, new in [
            (old_shown_cb,       new_shown_cb),
            (old_shown_cb_v1,    new_shown_cb),
            (old_deleted_cb,     new_deleted_cb),
            (old_deleted_cb_v1,  new_deleted_cb),
            (old_set_textarea,   new_set_textarea),
            (old_set_textarea_v1, new_set_textarea),
            (
                '#include "graphics/view/TFT/TFTView_320x240.h"\n',
                '#include "graphics/view/TFT/TFTView_320x240.h"\n'
                "extern lv_obj_t *joyMessagesPanel;\n"
                "extern lv_obj_t *joyMessageInput;\n"
                "extern lv_obj_t *joyKeyboardButton;\n"
                "extern \"C\" int emoji_strip_height(void);\n",
            ),
            (
                "    setInputButtonLabel();\n    lv_group_focus_obj(objects.home_button);\n",
                "    setInputButtonLabel();\n"
                "    joyMessagesPanel = objects.messages_panel;\n"
                "    joyMessageInput = objects.message_input_area;\n"
                "    joyKeyboardButton = objects.keyboard_button_0;\n"
                "    lv_group_focus_obj(objects.home_button);\n",
            ),
        ]:
            if old in content and new not in content:
                content = content.replace(old, new)
                changed = True

        # NAVIGATION BAR HOOK
        if "extern lv_obj_t *joyHomeButton;" not in content and "extern lv_obj_t *joyMessagesPanel;\n" in content:
            content = content.replace("extern lv_obj_t *joyMessagesPanel;\n", "extern lv_obj_t *joyHomeButton;\nextern lv_obj_t *joyMessagesPanel;\n", 1)
            changed = True
        if "joyHomeButton = objects.home_button;" not in content and "    joyMessagesPanel = objects.messages_panel;\n" in content:
            content = content.replace("    joyMessagesPanel = objects.messages_panel;\n", "    joyHomeButton = objects.home_button;\n    joyMessagesPanel = objects.messages_panel;\n", 1)
            changed = True
        if "extern lv_obj_t *joyChatsPanel;" not in content and "extern lv_obj_t *joyHomeButton;\n" in content:
            content = content.replace("extern lv_obj_t *joyHomeButton;\n", "extern lv_obj_t *joyHomeButton;\nextern lv_obj_t *joyChatsPanel;\n", 1)
            changed = True
        if "joyChatsPanel = objects.chats_panel;" not in content and "    joyHomeButton = objects.home_button;\n" in content:
            content = content.replace("    joyHomeButton = objects.home_button;\n", "    joyHomeButton = objects.home_button;\n    joyChatsPanel = objects.chats_panel;\n", 1)
            changed = True
        if "extern lv_obj_t *joyMapPanel;" not in content and "extern lv_obj_t *joyChatsPanel;\n" in content:
            content = content.replace("extern lv_obj_t *joyChatsPanel;\n",
                "extern lv_obj_t *joyChatsPanel;\n"
                "extern lv_obj_t *joyMapPanel;\n"
                "extern lv_obj_t *joyArrowUpButton;\n"
                "extern lv_obj_t *joyArrowDownButton;\n"
                "extern lv_obj_t *joyArrowLeftButton;\n"
                "extern lv_obj_t *joyArrowRightButton;\n"
                "extern lv_obj_t *joyZoomInButton;\n"
                "extern lv_obj_t *joyZoomOutButton;\n", 1)
            changed = True
        if "lv_group_add_obj(g, objects.nav_button);" in content and "lv_group_add_obj(g, objects.arrow_up_button);" not in content:
            # nav_button was added alone before; add the rest of the map buttons
            content = content.replace(
                "        lv_group_add_obj(g, objects.nav_button);\n",
                "        lv_group_add_obj(g, objects.nav_button);\n"
                "        lv_group_add_obj(g, objects.arrow_up_button);\n"
                "        lv_group_add_obj(g, objects.arrow_left_button);\n"
                "        lv_group_add_obj(g, objects.arrow_right_button);\n"
                "        lv_group_add_obj(g, objects.arrow_down_button);\n", 1)
            changed = True
        if "joyMapPanel = objects.map_panel;" not in content and "    joyChatsPanel = objects.chats_panel;\n" in content:
            content = content.replace("    joyChatsPanel = objects.chats_panel;\n",
                "    joyChatsPanel = objects.chats_panel;\n"
                "    joyMapPanel = objects.map_panel;\n"
                "    joyArrowUpButton = objects.arrow_up_button;\n"
                "    joyArrowDownButton = objects.arrow_down_button;\n"
                "    joyArrowLeftButton = objects.arrow_left_button;\n"
                "    joyArrowRightButton = objects.arrow_right_button;\n"
                "    joyZoomInButton = objects.zoom_in_button;\n"
                "    joyZoomOutButton = objects.zoom_out_button;\n", 1)
            changed = True
        if "lv_group_add_obj(g, objects.zoom_in_button);" not in content and "    joyZoomInButton = objects.zoom_in_button;\n" in content:
            content = content.replace("    joyZoomInButton = objects.zoom_in_button;\n",
                "    joyZoomInButton = objects.zoom_in_button;\n"
                "    { lv_group_t *g = lv_group_get_default(); if (g) {\n"
                "        lv_group_add_obj(g, objects.zoom_in_button);\n"
                "        lv_group_add_obj(g, objects.zoom_out_button);\n"
                "        lv_group_add_obj(g, objects.nav_button);\n"
                "        lv_group_add_obj(g, objects.arrow_up_button);\n"
                "        lv_group_add_obj(g, objects.arrow_left_button);\n"
                "        lv_group_add_obj(g, objects.arrow_right_button);\n"
                "        lv_group_add_obj(g, objects.arrow_down_button);\n"
                "    } }\n", 1)
            changed = True
        # focus highlight style for map imagebuttons — theme does not cover imagebutton, keep explicit
        map_focus_style_add = (
            "    { static lv_style_t _mfs; lv_style_init(&_mfs);"
            " lv_style_set_outline_width(&_mfs, 2);"
            " lv_style_set_outline_color(&_mfs, lv_color_make(255,255,255));"
            " lv_style_set_outline_opa(&_mfs, LV_OPA_80);"
            " lv_obj_t *_mb[] = {objects.zoom_in_button, objects.zoom_out_button, objects.nav_button,"
            " objects.arrow_up_button, objects.arrow_left_button, objects.arrow_right_button, objects.arrow_down_button};"
            " for (int _i = 0; _i < 7; _i++) lv_obj_add_style(_mb[_i], &_mfs, LV_STATE_FOCUSED); }\n"
        )
        if "lv_group_add_obj(g, objects.arrow_down_button);" in content and map_focus_style_add not in content:
            idx = content.find("    lv_group_add_obj(g, objects.arrow_down_button);\n    } }\n")
            if idx != -1:
                end = idx + len("    lv_group_add_obj(g, objects.arrow_down_button);\n    } }\n")
                content = content[:end] + map_focus_style_add + content[end:]
                changed = True

        # smaller keyboard for joystick-only variant (no touch needed for key sizing)
        old_kb_size = "lv_obj_set_size(objects.keyboard, LV_PCT(100), LV_PCT(45));"
        new_kb_size = "lv_obj_set_size(objects.keyboard, LV_PCT(100), LV_PCT(33));"
        if old_kb_size in content and new_kb_size not in content:
            content = content.replace(old_kb_size, new_kb_size, 1)
            changed = True

        # scroll messages_panel up enough to keep textarea visible above the emoji strip
        old_panel_anim = "lv_anim_set_values(&a1, panelY, kbdPanelBaseY - kb_h);"
        new_panel_anim = "lv_anim_set_values(&a1, panelY, kbdPanelBaseY - kb_h - emoji_strip_height());"
        if old_panel_anim in content and new_panel_anim not in content:
            content = content.replace(old_panel_anim, new_panel_anim, 1)
            changed = True

        # setGroupFocus for map_panel: focus nav_button
        old_map_focus = "    } else if (panel == objects.map_panel) {\n\n    } else if (panel == objects.settings_screen_lock_panel) {"
        new_map_focus = "    } else if (panel == objects.map_panel) {\n        lv_group_focus_obj(objects.nav_button);\n    } else if (panel == objects.settings_screen_lock_panel) {"
        if old_map_focus in content and new_map_focus not in content:
            content = content.replace(old_map_focus, new_map_focus, 1)
            changed = True

        if changed:
            print(f"Patched {filepath_tft_view}: encoder focus + editing mode for on-screen keyboard")
            with open(filepath_tft_view, 'w', encoding='utf-8') as f:
                f.write(content)


patch_joystick(None, None, env)

env.AddPreAction("buildprog", patch_joystick)
