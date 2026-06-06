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
        attachInterrupt(INPUTDRIVER_ENCODER_LEFT, intLeftHandler, FALLING);
#endif
#ifdef INPUTDRIVER_ENCODER_RIGHT
        pinMode(INPUTDRIVER_ENCODER_RIGHT, INPUT_PULLUP);
        // Do not attach interrupt on RIGHT pin, it is only read as phase B
#endif"""

        # Wire up BTN interrupt (upstream only calls pinMode, no attachInterrupt for BTN)
        old_btn_init_no_irq = """#ifdef INPUTDRIVER_ENCODER_BTN
        pinMode(INPUTDRIVER_ENCODER_BTN, INPUT);
#endif"""

        new_btn_init_with_irq = """#ifdef INPUTDRIVER_ENCODER_BTN
        pinMode(INPUTDRIVER_ENCODER_BTN, INPUT_PULLUP);
        attachInterrupt(INPUTDRIVER_ENCODER_BTN, intPressHandler, FALLING);
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
    static uint64_t lastInterruptTime = 0;
    uint64_t interruptTime = esp_timer_get_time();
    if (interruptTime - lastInterruptTime > 30000) { // 30ms debounce
        if (digitalRead(INPUTDRIVER_ENCODER_RIGHT)) {
            action = TB_ACTION_DOWN;
        } else {
            action = TB_ACTION_UP;
        }
        lastInterruptTime = interruptTime;
    }
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

        new_btn_read = """#ifdef INPUTDRIVER_ENCODER_BTN
        bool pinHeld = !digitalRead(INPUTDRIVER_ENCODER_BTN); // LOW = pressed (INPUT_PULLUP)
        uint32_t now = millis();
        if (pinHeld && !btnWasHeld) {
            // Falling edge detected by polling
            btnPressTime = now;
            btnWasHeld = true;
        } else if (!pinHeld && btnWasHeld) {
            // Rising edge - button released, decide action
            uint32_t held = now - btnPressTime;
            btnWasHeld = false;
            if (held >= 600) {
                // Long press -> back
                data->key   = LV_KEY_ESC;
                data->state = LV_INDEV_STATE_PRESSED;
                prevkey = LV_KEY_ESC;
            } else if (held >= 20) {
                // Short press -> select
                data->key   = LV_KEY_ENTER;
                data->state = LV_INDEV_STATE_PRESSED;
                prevkey = LV_KEY_ENTER;
            }
            // else: < 20 ms, ignore as noise
        }
#endif

        // slow down repeating key to max. four events per second
        if (action != TB_ACTION_NONE && millis() > lastPressed + 250) {
            if (action == TB_ACTION_UP) {
                data->enc_diff = -1;
            } else if (action == TB_ACTION_DOWN) {
                data->enc_diff = 1;
            } else if (action == TB_ACTION_LEFT) {
                data->key = LV_KEY_DOWN; // slider widget reacts on UP/DOWN
                data->state = LV_INDEV_STATE_PRESSED;
                prevkey = LV_KEY_DOWN;
            } else if (action == TB_ACTION_RIGHT) {
                data->key = LV_KEY_UP; // slider widget reacts on UP/DOWN
                data->state = LV_INDEV_STATE_PRESSED;
                prevkey = LV_KEY_UP;
            }

            lastPressed = millis();
            action = TB_ACTION_NONE;
        } else {
            // this logic is required for LONG_PRESSED event, see lv_indev.c
            if (prevkey != 0) {
                data->state = LV_INDEV_STATE_RELEASED;
                data->key = prevkey;
                prevkey = 0;
            }
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
            print(f"Patched {filepath_enc} with Quadrature Encoder decoding, IRAM_ATTR, and short-press fix")
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

    # 3. Patch TFTDisplay.cpp for custom rotation orientation and offset_rotation
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

# Run immediately when PlatformIO loads this script (ensures files are patched BEFORE dependency checking/compilation)
patch_encoder_iram(None, None, env)

env.AddPreAction("buildprog", patch_encoder_iram)
env.AddPreAction("$PROJECT_DIR/.pio/libdeps/${PIOENV}/meshtastic-device-ui/source/input/EncoderInputDriver.cpp.o", patch_encoder_iram)
env.AddPreAction("$PROJECT_DIR/.pio/libdeps/${PIOENV}/lvgl/src/widgets/dropdown/lv_dropdown.c.o", patch_encoder_iram)
env.AddPreAction("$PROJECT_DIR/src/graphics/TFTDisplay.cpp", patch_encoder_iram)
env.AddPreAction("$PROJECT_DIR/src/graphics/TFTDisplay.cpp.o", patch_encoder_iram)
