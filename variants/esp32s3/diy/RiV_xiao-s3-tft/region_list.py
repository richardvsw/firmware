import os

Import("env")

# DROPDOWN LIST MUST MATCH THE REGION TABLE IN TFTView_320x240.cpp, THE GENERATED LISTS ARE SHORTER
OLD = r"US\nEU_433\nEU_868\nCN\nJP\nANZ\nKR\nTW\nRU\nIN\nNZ_865\nTH\nLORA_24\nUA_433\nUA_868\nMY_433\nMY_919\nSG_923\nPH_433\nPH_868\nPH_915\nANZ_433"
NEW = r"US\nEU_433\nEU_868\nEU_866\nEU_868_NARROW\nCN\nJP\nANZ\nKR\nTW\nRU\nIN\nNZ_865\nTH\nLORA_24\nUA_433\nMY_433\nMY_919\nSG_923\nPH_433\nPH_868\nPH_915\nANZ_433\nKZ_433\nKZ_863\nNP_865\nBR_902"

for ui in ("ui_240x320", "ui_320x240"):
    path = env.subst("$PROJECT_DIR/.pio/libdeps/${PIOENV}/meshtastic-device-ui/generated/" + ui + "/screens.c")
    if not os.path.exists(path):
        continue
    with open(path, "r", encoding="utf-8", newline="") as f:
        content = f.read()
    if OLD in content:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content.replace('"' + OLD + '"', '"' + NEW + '"'))
        print(f"Patched {path}: region list")
