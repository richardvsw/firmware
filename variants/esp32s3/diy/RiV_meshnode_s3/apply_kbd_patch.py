"""
Standalone one-shot patcher: adds lv_group_set_editing calls around keyboard focus.
Run with: python variants/esp32s3/diy/RiV_meshnode_s3/apply_kbd_patch.py
"""
import os, sys

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
filepath = os.path.normpath(os.path.join(
    ROOT, ".pio/libdeps/RiV_meshnode-s3/meshtastic-device-ui/source/graphics/TFT/TFTView_320x240.cpp"))

if not os.path.exists(filepath):
    sys.exit(f"Not found: {filepath}")

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

replacements = [
    # shown_cb: add editing mode after focus (upstream → final)
    (
        "        static auto shown_cb = [](_lv_anim_t *) { kbdSlideState = eKbdShown; };",
        """        static auto shown_cb = [](_lv_anim_t *) {
            kbdSlideState = eKbdShown;
            if (lv_obj_get_group(objects.keyboard) == NULL)
                lv_group_add_obj(lv_group_get_default(), objects.keyboard);
            lv_group_focus_obj(objects.keyboard);
            lv_group_set_editing(lv_group_get_default(), true);
        };"""
    ),
    # shown_cb: upgrade intermediate (focus only) → final (focus + editing)
    (
        """        static auto shown_cb = [](_lv_anim_t *) {
            kbdSlideState = eKbdShown;
            if (lv_obj_get_group(objects.keyboard) == NULL)
                lv_group_add_obj(lv_group_get_default(), objects.keyboard);
            lv_group_focus_obj(objects.keyboard);
        };""",
        """        static auto shown_cb = [](_lv_anim_t *) {
            kbdSlideState = eKbdShown;
            if (lv_obj_get_group(objects.keyboard) == NULL)
                lv_group_add_obj(lv_group_get_default(), objects.keyboard);
            lv_group_focus_obj(objects.keyboard);
            lv_group_set_editing(lv_group_get_default(), true);
        };"""
    ),
    # deleted_cb: add editing=false before restoring focus (intermediate → final)
    (
        """            kbdSlideState = eKbdHidden;
            lv_group_focus_obj(objects.message_input_area);
        };""",
        """            kbdSlideState = eKbdHidden;
            lv_group_set_editing(lv_group_get_default(), false);
            lv_group_focus_obj(objects.message_input_area);
        };"""
    ),
    # deleted_cb: upstream → final (no prior focus call)
    (
        """            lv_obj_add_flag(objects.keyboard, LV_OBJ_FLAG_HIDDEN);
            kbdSlideState = eKbdHidden;
        };""",
        """            lv_obj_add_flag(objects.keyboard, LV_OBJ_FLAG_HIDDEN);
            kbdSlideState = eKbdHidden;
            lv_group_set_editing(lv_group_get_default(), false);
            lv_group_focus_obj(objects.message_input_area);
        };"""
    ),
    # showKeyboard else-branch: add editing mode (intermediate → final)
    (
        """    if (textArea != objects.message_input_area) {
        if (lv_obj_get_group(objects.keyboard) == NULL)
            lv_group_add_obj(lv_group_get_default(), objects.keyboard);
        lv_group_focus_obj(objects.keyboard);
    }
}

void TFTView_320x240::hideKeyboard""",
        """    if (textArea != objects.message_input_area) {
        if (lv_obj_get_group(objects.keyboard) == NULL)
            lv_group_add_obj(lv_group_get_default(), objects.keyboard);
        lv_group_focus_obj(objects.keyboard);
        lv_group_set_editing(lv_group_get_default(), true);
    }
}

void TFTView_320x240::hideKeyboard"""
    ),
    # showKeyboard else-branch: upstream → final (no prior focus call)
    (
        """    lv_keyboard_set_textarea(objects.keyboard, textArea);
}

void TFTView_320x240::hideKeyboard""",
        """    lv_keyboard_set_textarea(objects.keyboard, textArea);
    if (textArea != objects.message_input_area) {
        if (lv_obj_get_group(objects.keyboard) == NULL)
            lv_group_add_obj(lv_group_get_default(), objects.keyboard);
        lv_group_focus_obj(objects.keyboard);
        lv_group_set_editing(lv_group_get_default(), true);
    }
}

void TFTView_320x240::hideKeyboard"""
    ),
]

changed = False
for old, new in replacements:
    if old in content and new not in content:
        content = content.replace(old, new)
        changed = True
        print(f"Applied: {old[:60].strip()!r} ...")

if changed:
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched TFTView_320x240.cpp: keyboard encoder editing mode")
else:
    print("Nothing to patch (already up-to-date or patterns not found)")
