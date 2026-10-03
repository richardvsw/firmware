import os
from SCons.Script import Import

Import("env")

def patch_encoder_iram(source, target, env):
    # 1. Patch EncoderInputDriver.cpp
    filepath_enc = env.subst("$PROJECT_DIR/.pio/libdeps/${PIOENV}/meshtastic-device-ui/source/input/EncoderInputDriver.cpp")
    if os.path.exists(filepath_enc):
        with open(filepath_enc, 'r', encoding='utf-8') as f:
            content = f.read()
            
        old_init = """#ifdef INPUTDRIVER_ENCODER_LEFT
        pinMode(INPUTDRIVER_ENCODER_LEFT, INPUT_PULLUP);
        attachInterrupt(INPUTDRIVER_ENCODER_LEFT, intLeftHandler, RISING);
#endif
#ifdef INPUTDRIVER_ENCODER_RIGHT
        pinMode(INPUTDRIVER_ENCODER_RIGHT, INPUT_PULLUP);
        attachInterrupt(INPUTDRIVER_ENCODER_RIGHT, intRightHandler, RISING);
#endif"""

        new_init = """#ifdef INPUTDRIVER_ENCODER_LEFT
        pinMode(INPUTDRIVER_ENCODER_LEFT, INPUT_PULLUP);
        attachInterrupt(INPUTDRIVER_ENCODER_LEFT, intLeftHandler, CHANGE);
#endif
#ifdef INPUTDRIVER_ENCODER_RIGHT
        pinMode(INPUTDRIVER_ENCODER_RIGHT, INPUT_PULLUP);
        // Do not attach interrupt on RIGHT pin, it is only read as phase B
#endif"""

        # Set button to INPUT_PULLUP; button is polled in getInputData(), no ISR needed
        old_btn_init_no_irq = """#ifdef INPUTDRIVER_ENCODER_BTN
        pinMode(INPUTDRIVER_ENCODER_BTN, INPUT);
#endif"""

        new_btn_init_with_irq = """#ifdef INPUTDRIVER_ENCODER_BTN
        pinMode(INPUTDRIVER_ENCODER_BTN, INPUT_PULLUP);
#endif"""

        # Pattern A: library without IRAM_ATTR (old upstream)
        old_isr_left = """void EncoderInputDriver::intLeftHandler()
{
    action = TB_ACTION_LEFT;
}"""

        # Pattern B: library already has IRAM_ATTR (newer upstream)
        old_isr_left_iram = """void IRAM_ATTR EncoderInputDriver::intLeftHandler()
{
    action = TB_ACTION_LEFT;
}"""

        new_isr_left = """void IRAM_ATTR EncoderInputDriver::intLeftHandler()
{
    // Quadrature accumulator — fires on both CLK edges.
    // Bounce reverses the accumulator back toward zero, so real detents
    // (two consistent half-steps) reach ±2 and emit an action; glitches don't.
    // No timer needed: this is inherently debounced by the physics of the signal.
    static int8_t acc = 0;
    bool clk = (bool)digitalRead(INPUTDRIVER_ENCODER_LEFT);
    bool dt  = (bool)digitalRead(INPUTDRIVER_ENCODER_RIGHT);
    // Falling CLK: CW if DT=HIGH, CCW if DT=LOW
    // Rising  CLK: CW if DT=LOW,  CCW if DT=HIGH
    acc += (clk ^ dt) ? 1 : -1;
    if (acc >= 2)       { acc = 0; action = TB_ACTION_DOWN; }
    else if (acc <= -2) { acc = 0; action = TB_ACTION_UP;   }
}"""

        # Pattern A: library without IRAM_ATTR (old upstream)
        old_isr_right = """void EncoderInputDriver::intRightHandler()
{
    action = TB_ACTION_RIGHT;
}"""

        # Pattern B: library already has IRAM_ATTR (newer upstream)
        old_isr_right_iram = """void IRAM_ATTR EncoderInputDriver::intRightHandler()
{
    action = TB_ACTION_RIGHT;
}"""

        new_isr_right = """void IRAM_ATTR EncoderInputDriver::intRightHandler()
{
    // ignored
}"""

        # Short-press fix: replace the old simple digitalRead-only button block
        # with an ISR-latched btnPressed flag so brief presses are never missed.
        old_btn_read = """#ifdef INPUTDRIVER_ENCODER_BTN
        if (action == TB_ACTION_NONE) {
            if (!digitalRead(INPUTDRIVER_ENCODER_BTN)) {
                action = TB_ACTION_PRESSED;
            }
        }
#endif
        // slow down repeating key to max. four events per second
        // the button is an exception for LONG_PRESSED monitoring
        if (action != TB_ACTION_NONE && (action == TB_ACTION_PRESSED || millis() > lastPressed + 250)) {
            if (action == TB_ACTION_PRESSED) {
                data->key = LV_KEY_ENTER;
                data->state = LV_INDEV_STATE_PRESSED;
            } else if (action == TB_ACTION_UP) {
                data->enc_diff = -1;
            } else if (action == TB_ACTION_DOWN) {
                data->enc_diff = 1;
            } else if (action == TB_ACTION_LEFT) {
                data->key = LV_KEY_DOWN; // slider widget reacts on UP/DOWN
                data->state = LV_INDEV_STATE_PRESSED;
            } else if (action == TB_ACTION_RIGHT) {
                data->key = LV_KEY_UP; // slider widget reacts on UP/DOWN
                data->state = LV_INDEV_STATE_PRESSED;
            }

            lastPressed = millis();
            prevkey = data->key;
            action = TB_ACTION_NONE;
        } else {
            // this logic is required for LONG_PRESSED event, see lv_indev.c
            if (prevkey != 0) {
                data->state = LV_INDEV_STATE_RELEASED;
                data->key = prevkey;
                prevkey = 0;
            }
        }"""

        new_btn_read = """data->enc_diff = 0;
        data->state = LV_INDEV_STATE_RELEASED;

        // Auto-enter editing mode whenever a keyboard widget is focused so
        // enc_diff routes through lv_group_send_data(KEY_LEFT/RIGHT) instead
        // of cycling focus between group objects.
        {
            lv_group_t *encGroup = lv_group_get_default();
            if (encGroup) {
                lv_obj_t *focusedObj = lv_group_get_focused(encGroup);
                if (focusedObj && lv_obj_check_type(focusedObj, &lv_keyboard_class)
                        && !lv_group_get_editing(encGroup)) {
                    lv_group_set_editing(encGroup, true);
                }
            }
        }

#ifdef INPUTDRIVER_ENCODER_BTN
        // Button mirrors touchscreen: sustain PRESSED while held, RELEASED on release.
        // LVGL decides click vs long_press at its 400 ms threshold — identical to touch.
        // Noise filter: ignore presses shorter than 20 ms.
        bool pinHeld = !digitalRead(INPUTDRIVER_ENCODER_BTN);
        uint32_t now = millis();

        if (pinHeld && !btnWasHeld) {
            btnPressTime = now;
            btnWasHeld   = true;
        } else if (!pinHeld && btnWasHeld) {
            btnWasHeld = false;
            if (now - btnPressTime < 20) {
                prevkey = 0;  // noise: cancel any PRESSED we started reporting
            }
            // RELEASED handled by prevkey block below
        }

        if (btnWasHeld && (now - btnPressTime) >= 20) {
            data->key   = LV_KEY_ENTER;
            data->state = LV_INDEV_STATE_PRESSED;
            prevkey     = LV_KEY_ENTER;
        } else if (!btnWasHeld && prevkey == LV_KEY_ENTER) {
            data->key   = LV_KEY_ENTER;
            data->state = LV_INDEV_STATE_RELEASED;
            prevkey     = 0;
        }
#endif

        // Encoder rotation (rate-limited to 100 ms between steps)
        if (action != TB_ACTION_NONE && millis() > lastPressed + 100) {
            if (action == TB_ACTION_UP) {
                data->enc_diff = -1;
            } else if (action == TB_ACTION_DOWN) {
                data->enc_diff = 1;
            } else if (action == TB_ACTION_RIGHT) {
                data->key   = LV_KEY_UP;
                data->state = LV_INDEV_STATE_PRESSED;
                prevkey     = LV_KEY_UP;
            }
            lastPressed = millis();
            action      = TB_ACTION_NONE;
        } else if (prevkey != 0 && prevkey != LV_KEY_ENTER) {
            // complete RELEASED cycle for RIGHT
            data->key   = prevkey;
            data->state = LV_INDEV_STATE_RELEASED;
            prevkey     = 0;
        }"""

        # The btnPressed latch variable declaration (inserted after lastPressed)
        old_btn_latch_decl = """        static uint32_t prevkey = 0;
        static uint32_t lastPressed = millis();

        data->key = 0;"""

        new_btn_latch_decl = """        static uint32_t prevkey = 0;
        static uint32_t lastPressed = millis();
        static uint32_t btnPressTime = 0;
        static bool btnWasHeld = false;

        data->key = 0;"""

        replacements = [
            (old_init, new_init),
            (old_btn_init_no_irq, new_btn_init_with_irq),  # add BTN attachInterrupt
            (old_isr_left, new_isr_left),        # no-IRAM_ATTR variant
            (old_isr_left_iram, new_isr_left),    # IRAM_ATTR variant (newer lib)
            (old_isr_right, new_isr_right),       # no-IRAM_ATTR variant
            (old_isr_right_iram, new_isr_right),  # IRAM_ATTR variant (newer lib)
            ("void EncoderInputDriver::intPressHandler()", "void IRAM_ATTR EncoderInputDriver::intPressHandler()"),
            ("void EncoderInputDriver::intDownHandler()", "void IRAM_ATTR EncoderInputDriver::intDownHandler()"),
            ("void EncoderInputDriver::intUpHandler()", "void IRAM_ATTR EncoderInputDriver::intUpHandler()"),
            (old_btn_latch_decl, new_btn_latch_decl),  # add btnPressed latch var
            (old_btn_read, new_btn_read),              # fix short-press detection
        ]
        
        changed = False
        for old, new in replacements:
            if old in content and new not in content:
                content = content.replace(old, new)
                changed = True
                
        if changed:
            print(f"Patched {filepath_enc}: CHANGE-edge quadrature accumulator, IRAM_ATTR, short-press fix")
            with open(filepath_enc, 'w', encoding='utf-8') as f:
                f.write(content)

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

    # 3. Patch ServerAPI.cpp — reduce TCP idle timeout from 15 min to 3 min.
    # Upstream: timeout only starts counting after first data packet (lastContactMsec > 0).
    # With keepalive now enabled in sdkconfig (dead sockets detected in ~45s), this is a
    # software fallback for the rare case where the socket looks alive but no data ever flows.
    filepath_server = env.subst("$PROJECT_DIR/src/mesh/api/ServerAPI.cpp")
    if os.path.exists(filepath_server):
        with open(filepath_server, 'r', encoding='utf-8') as f:
            content = f.read()

        old_timeout = "static constexpr uint32_t TCP_IDLE_TIMEOUT_MS = 15 * 60 * 1000UL;"
        new_timeout = "static constexpr uint32_t TCP_IDLE_TIMEOUT_MS = 3 * 60 * 1000UL;"

        if old_timeout in content and new_timeout not in content:
            content = content.replace(old_timeout, new_timeout)
            print(f"Patched {filepath_server}: TCP idle timeout 15min → 3min")
            with open(filepath_server, 'w', encoding='utf-8') as f:
                f.write(content)

    # 4. Patch AdminModule.cpp — use IP presence instead of WL_CONNECTED for WiFi status.
    # WiFi.status() == WL_CONNECTED returns false for 2-3s during MQTT-triggered WiFi reconnects.
    # The device-ui polls every 10s, so a poll landing in that window shows "no signal" even
    # though WiFi is functionally up. WiFi.localIP() holds its address through brief reconnects.
    filepath_admin = env.subst("$PROJECT_DIR/src/modules/AdminModule.cpp")
    if os.path.exists(filepath_admin):
        with open(filepath_admin, 'r', encoding='utf-8') as f:
            content = f.read()

        old_wifi_check = "    conn.wifi.status.is_connected = WiFi.status() == WL_CONNECTED;"
        new_wifi_check = "    conn.wifi.status.is_connected = (WiFi.localIP() != INADDR_NONE);"

        if old_wifi_check in content and new_wifi_check not in content:
            content = content.replace(old_wifi_check, new_wifi_check)
            print(f"Patched {filepath_admin}: WiFi connected check uses localIP() not WL_CONNECTED")
            with open(filepath_admin, 'w', encoding='utf-8') as f:
                f.write(content)

    # 5. Patch TFTDisplay.cpp for custom rotation orientation and offset_rotation
    filepath_tft = env.subst("$PROJECT_DIR/src/graphics/TFTDisplay.cpp")
    if os.path.exists(filepath_tft):
        with open(filepath_tft, 'r', encoding='utf-8') as f:
            content = f.read()
        
        old_rotation = """#else
    tft->setRotation(3); // Orient horizontal and wide underneath the silkscreen name label
#endif"""
        
        new_rotation = """#else
#if defined(MESHNODE_S3_TFT)
    tft->setRotation(1);
#else
    tft->setRotation(3); // Orient horizontal and wide underneath the silkscreen name label
#endif
#endif"""

        old_offset_rot = """            cfg.offset_rotation = 0;       // Rotation direction value offset 0~7 (4~7 is upside down)"""

        new_offset_rot = """#ifdef TFT_OFFSET_ROTATION
            cfg.offset_rotation = TFT_OFFSET_ROTATION;
#else
            cfg.offset_rotation = 0;       // Rotation direction value offset 0~7 (4~7 is upside down)
#endif"""
        
        changed = False
        if old_rotation in content and new_rotation not in content:
            content = content.replace(old_rotation, new_rotation)
            changed = True
        if old_offset_rot in content and new_offset_rot not in content:
            content = content.replace(old_offset_rot, new_offset_rot)
            changed = True

        if changed:
            print(f"Patched {filepath_tft} to respect MESHNODE_S3_TFT screen rotation & offset_rotation")
            with open(filepath_tft, 'w', encoding='utf-8') as f:
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
        ]:
            if old in content and new not in content:
                content = content.replace(old, new)
                changed = True

        if changed:
            print(f"Patched {filepath_tft_view}: encoder focus + editing mode for on-screen keyboard")
            with open(filepath_tft_view, 'w', encoding='utf-8') as f:
                f.write(content)


# Run immediately when PlatformIO loads this script (ensures files are patched BEFORE dependency checking/compilation)
patch_encoder_iram(None, None, env)

env.AddPreAction("buildprog", patch_encoder_iram)
env.AddPreAction("$PROJECT_DIR/.pio/libdeps/${PIOENV}/meshtastic-device-ui/source/input/EncoderInputDriver.cpp.o", patch_encoder_iram)
env.AddPreAction("$PROJECT_DIR/.pio/libdeps/${PIOENV}/lvgl/src/widgets/dropdown/lv_dropdown.c.o", patch_encoder_iram)
env.AddPreAction("$PROJECT_DIR/.pio/libdeps/${PIOENV}/meshtastic-device-ui/source/graphics/TFT/TFTView_320x240.cpp.o", patch_encoder_iram)
env.AddPreAction("$PROJECT_DIR/src/graphics/TFTDisplay.cpp", patch_encoder_iram)
env.AddPreAction("$PROJECT_DIR/src/graphics/TFTDisplay.cpp.o", patch_encoder_iram)
env.AddPreAction("$PROJECT_DIR/src/mesh/api/ServerAPI.cpp", patch_encoder_iram)
env.AddPreAction("$PROJECT_DIR/src/mesh/api/ServerAPI.cpp.o", patch_encoder_iram)
