#include "configuration.h"

#ifdef _VARIANT_HIBY_R1

#include "HiByR1_Battery.h"
#include "HiByR1_LED.h"
#include "Power.h"
#include "mesh/NodeDB.h"
#include <cstdlib>
#include <cstdio>

static const char *get_hw_model_name(int model) {
    switch (model) {
        case meshtastic_HardwareModel_UNSET: return "Unset";
        case meshtastic_HardwareModel_TLORA_V2: return "TLora V2";
        case meshtastic_HardwareModel_TLORA_V1: return "TLora V1";
        case meshtastic_HardwareModel_TLORA_V2_1_1P6: return "TLora V2.1";
        case meshtastic_HardwareModel_TBEAM: return "T-Beam";
        case meshtastic_HardwareModel_HELTEC_V2_0: return "Heltec V2.0";
        case meshtastic_HardwareModel_TBEAM_V0P7: return "T-Beam V0.7";
        case meshtastic_HardwareModel_T_ECHO: return "T-Echo";
        case meshtastic_HardwareModel_TLORA_V1_1P3: return "TLora V1.1";
        case meshtastic_HardwareModel_RAK4631: return "RAK4631";
        case meshtastic_HardwareModel_HELTEC_V2_1: return "Heltec V2.1";
        case meshtastic_HardwareModel_HELTEC_V1: return "Heltec V1";
        case meshtastic_HardwareModel_LILYGO_TBEAM_S3_CORE: return "T-Beam S3";
        case meshtastic_HardwareModel_RAK11200: return "RAK11200";
        case meshtastic_HardwareModel_NANO_G1: return "Nano G1";
        case meshtastic_HardwareModel_TLORA_V2_1_1P8: return "TLora V2.1";
        case meshtastic_HardwareModel_TLORA_T3_S3: return "TLora T3S3";
        case meshtastic_HardwareModel_NANO_G1_EXPLORER: return "Nano G1 Explorer";
        case meshtastic_HardwareModel_NANO_G2_ULTRA: return "Nano G2 Ultra";
        case meshtastic_HardwareModel_LORA_TYPE: return "LoRa Type";
        case meshtastic_HardwareModel_WIPHONE: return "WiPhone";
        case meshtastic_HardwareModel_WIO_WM1110: return "Wio WM1110";
        case meshtastic_HardwareModel_RAK2560: return "RAK2560";
        case meshtastic_HardwareModel_HELTEC_HRU_3601: return "Heltec HRU-3601";
        case meshtastic_HardwareModel_HELTEC_WIRELESS_BRIDGE: return "Heltec Wireless Bridge";
        case meshtastic_HardwareModel_STATION_G1: return "Station G1";
        case meshtastic_HardwareModel_RAK11310: return "RAK11310";
        case meshtastic_HardwareModel_MAKERFABS_TRACKER: return "Makerfabs Tracker";
        case meshtastic_HardwareModel_MAKERFABS_RESERVED: return "Makerfabs";
        case meshtastic_HardwareModel_CANARYONE: return "CanaryOne";
        case meshtastic_HardwareModel_RP2040_LORA: return "RP2040 LoRa";
        case meshtastic_HardwareModel_STATION_G2: return "Station G2";
        case meshtastic_HardwareModel_LORA_RELAY_V1: return "LoRa Relay V1";
        case meshtastic_HardwareModel_T_ECHO_PLUS: return "T-Echo Plus";
        case meshtastic_HardwareModel_PPR: return "PPR";
        case meshtastic_HardwareModel_GENIEBLOCKS: return "GenieBlocks";
        case meshtastic_HardwareModel_NRF52_UNKNOWN: return "nRF52";
        case meshtastic_HardwareModel_PORTDUINO: return "HiBy R1";
        case meshtastic_HardwareModel_ANDROID_SIM: return "Android Sim";
        case meshtastic_HardwareModel_DIY_V1: return "DIY V1";
        case meshtastic_HardwareModel_NRF52840_PCA10059: return "nRF52840 Dongle";
        case meshtastic_HardwareModel_DR_DEV: return "DR Dev";
        case meshtastic_HardwareModel_M5STACK: return "M5Stack";
        case meshtastic_HardwareModel_HELTEC_V3: return "Heltec V3";
        case meshtastic_HardwareModel_HELTEC_WSL_V3: return "Heltec WSL V3";
        case meshtastic_HardwareModel_BETAFPV_2400_TX: return "BetaFPV 2400 TX";
        case meshtastic_HardwareModel_BETAFPV_900_NANO_TX: return "BetaFPV 900 Nano";
        case meshtastic_HardwareModel_RPI_PICO: return "RPi Pico";
        case meshtastic_HardwareModel_HELTEC_WIRELESS_TRACKER: return "Heltec Tracker";
        case meshtastic_HardwareModel_HELTEC_WIRELESS_PAPER: return "Heltec Paper";
        case meshtastic_HardwareModel_T_DECK: return "T-Deck";
        case meshtastic_HardwareModel_T_WATCH_S3: return "T-Watch S3";
        case meshtastic_HardwareModel_PICOMPUTER_S3: return "PiComputer S3";
        case meshtastic_HardwareModel_HELTEC_HT62: return "Heltec HT62";
        case meshtastic_HardwareModel_EBYTE_ESP32_S3: return "EByte ESP32-S3";
        case meshtastic_HardwareModel_ESP32_S3_PICO: return "ESP32-S3 Pico";
        case meshtastic_HardwareModel_CHATTER_2: return "Chatter 2";
        case meshtastic_HardwareModel_HELTEC_WIRELESS_PAPER_V1_0: return "Heltec Paper V1";
        case meshtastic_HardwareModel_HELTEC_WIRELESS_TRACKER_V1_0: return "Heltec Tracker V1";
        case meshtastic_HardwareModel_UNPHONE: return "unPhone";
        case meshtastic_HardwareModel_TD_LORAC: return "TD LoRaC";
        case meshtastic_HardwareModel_CDEBYTE_EORA_S3: return "Eora S3";
        case meshtastic_HardwareModel_TWC_MESH_V4: return "TWC Mesh V4";
        case meshtastic_HardwareModel_NRF52_PROMICRO_DIY: return "ProMicro DIY";
        case meshtastic_HardwareModel_RADIOMASTER_900_BANDIT_NANO: return "Bandit Nano";
        case meshtastic_HardwareModel_HELTEC_CAPSULE_SENSOR_V3: return "Heltec Capsule V3";
        case meshtastic_HardwareModel_HELTEC_VISION_MASTER_T190: return "Heltec VM T190";
        case meshtastic_HardwareModel_HELTEC_VISION_MASTER_E213: return "Heltec VM E213";
        case meshtastic_HardwareModel_HELTEC_VISION_MASTER_E290: return "Heltec VM E290";
        case meshtastic_HardwareModel_HELTEC_MESH_NODE_T114: return "Heltec T114";
        case meshtastic_HardwareModel_SENSECAP_INDICATOR: return "SenseCAP";
        case meshtastic_HardwareModel_TRACKER_T1000_E: return "T1000-E";
        case meshtastic_HardwareModel_RAK3172: return "RAK3172";
        case meshtastic_HardwareModel_WIO_E5: return "Wio E5";
        case meshtastic_HardwareModel_RADIOMASTER_900_BANDIT: return "Bandit 900";
        case meshtastic_HardwareModel_ME25LS01_4Y10TD: return "ME25LS01";
        case meshtastic_HardwareModel_RP2040_FEATHER_RFM95: return "Feather RP2040";
        case meshtastic_HardwareModel_M5STACK_COREBASIC: return "M5 Core Basic";
        case meshtastic_HardwareModel_M5STACK_CORE2: return "M5 Core2";
        case meshtastic_HardwareModel_RPI_PICO2: return "RPi Pico2";
        case meshtastic_HardwareModel_M5STACK_CORES3: return "M5 CoreS3";
        case meshtastic_HardwareModel_SEEED_XIAO_S3: return "Xiao S3";
        case meshtastic_HardwareModel_MS24SF1: return "MS24SF1";
        case meshtastic_HardwareModel_TLORA_C6: return "TLora C6";
        case meshtastic_HardwareModel_WISMESH_TAP: return "WisMesh Tap";
        case meshtastic_HardwareModel_ROUTASTIC: return "Routastic";
        case meshtastic_HardwareModel_MESH_TAB: return "Mesh Tab";
        case meshtastic_HardwareModel_MESHLINK: return "MeshLink";
        case meshtastic_HardwareModel_XIAO_NRF52_KIT: return "Xiao nRF52 Kit";
        case meshtastic_HardwareModel_THINKNODE_M1: return "ThinkNode M1";
        case meshtastic_HardwareModel_THINKNODE_M2: return "ThinkNode M2";
        case meshtastic_HardwareModel_T_ETH_ELITE: return "T-ETH Elite";
        case meshtastic_HardwareModel_HELTEC_SENSOR_HUB: return "Heltec Sensor Hub";
        case meshtastic_HardwareModel_MUZI_BASE: return "Muzi Base";
        case meshtastic_HardwareModel_HELTEC_MESH_POCKET: return "Heltec Pocket";
        case meshtastic_HardwareModel_SEEED_SOLAR_NODE: return "Seeed Solar Node";
        case meshtastic_HardwareModel_NOMADSTAR_METEOR_PRO: return "Meteor Pro";
        case meshtastic_HardwareModel_CROWPANEL: return "CrowPanel";
        case meshtastic_HardwareModel_LINK_32: return "Link 32";
        case meshtastic_HardwareModel_SEEED_WIO_TRACKER_L1: return "Wio Tracker L1";
        case meshtastic_HardwareModel_SEEED_WIO_TRACKER_L1_EINK: return "Wio Tracker L1 E-Ink";
        case meshtastic_HardwareModel_MUZI_R1_NEO: return "Muzi R1 Neo";
        case meshtastic_HardwareModel_T_DECK_PRO: return "T-Deck Pro";
        case meshtastic_HardwareModel_T_LORA_PAGER: return "T-LoRa Pager";
        case meshtastic_HardwareModel_M5STACK_RESERVED: return "M5Stack";
        case meshtastic_HardwareModel_WISMESH_TAG: return "WisMesh Tag";
        case meshtastic_HardwareModel_RAK3312: return "RAK3312";
        case meshtastic_HardwareModel_THINKNODE_M5: return "ThinkNode M5";
        case meshtastic_HardwareModel_HELTEC_MESH_SOLAR: return "Heltec Solar";
        case meshtastic_HardwareModel_T_ECHO_LITE: return "T-Echo Lite";
        case meshtastic_HardwareModel_HELTEC_V4: return "Heltec V4";
        case meshtastic_HardwareModel_M5STACK_C6L: return "M5Stack C6L";
        case meshtastic_HardwareModel_M5STACK_CARDPUTER_ADV: return "Cardputer ADV";
        case meshtastic_HardwareModel_HELTEC_WIRELESS_TRACKER_V2: return "Heltec Tracker V2";
        case meshtastic_HardwareModel_T_WATCH_ULTRA: return "T-Watch Ultra";
        case meshtastic_HardwareModel_THINKNODE_M3: return "ThinkNode M3";
        case meshtastic_HardwareModel_WISMESH_TAP_V2: return "WisMesh Tap V2";
        case meshtastic_HardwareModel_RAK3401: return "RAK3401";
        case meshtastic_HardwareModel_RAK6421: return "RAK6421";
        case meshtastic_HardwareModel_THINKNODE_M4: return "ThinkNode M4";
        case meshtastic_HardwareModel_THINKNODE_M6: return "ThinkNode M6";
        case meshtastic_HardwareModel_MESHSTICK_1262: return "MeshStick 1262";
        case meshtastic_HardwareModel_TBEAM_1_WATT: return "T-Beam 1W";
        case meshtastic_HardwareModel_T5_S3_EPAPER_PRO: return "T5 S3 ePaper Pro";
        case meshtastic_HardwareModel_TBEAM_BPF: return "T-Beam BPF";
        case meshtastic_HardwareModel_MINI_EPAPER_S3: return "Mini ePaper S3";
        case meshtastic_HardwareModel_TDISPLAY_S3_PRO: return "T-Display S3 Pro";
        case meshtastic_HardwareModel_HELTEC_MESH_NODE_T096: return "Heltec T096";
        case meshtastic_HardwareModel_MESH_TRACKER_X1: return "Mesh Tracker X1";
        case meshtastic_HardwareModel_THINKNODE_M7: return "ThinkNode M7";
        case meshtastic_HardwareModel_THINKNODE_M8: return "ThinkNode M8";
        case meshtastic_HardwareModel_THINKNODE_M9: return "ThinkNode M9";
        case meshtastic_HardwareModel_HELTEC_V4_R8: return "Heltec V4 R8";
        case meshtastic_HardwareModel_HELTEC_MESH_NODE_T1: return "Heltec T1";
        case meshtastic_HardwareModel_STATION_G3: return "Station G3";
        case meshtastic_HardwareModel_T_IMPULSE_PLUS: return "T-Impulse Plus";
        case meshtastic_HardwareModel_T_ECHO_CARD: return "T-Echo Card";
        case meshtastic_HardwareModel_SEEED_WIO_TRACKER_L2: return "Wio Tracker L2";
        case meshtastic_HardwareModel_CROWPANEL_P4: return "CrowPanel P4";
        case meshtastic_HardwareModel_HELTEC_MESH_TOWER_V2: return "Heltec Mesh Tower";
        case meshtastic_HardwareModel_MESHNOLOGY_W10: return "Meshnology W10";
        case meshtastic_HardwareModel_HELTEC_RC32: return "Heltec RC32";
        case meshtastic_HardwareModel_HELTEC_RC52: return "Heltec RC52";
        case meshtastic_HardwareModel_HELTEC_RCC6: return "Heltec RCC6";
        case meshtastic_HardwareModel_SEEED_WIO_TRACKER_L1_PRO_1W: return "Wio Tracker 1W";
        case meshtastic_HardwareModel_MESHNOLOGY_W12: return "Meshnology W12";
        case meshtastic_HardwareModel_MESHPAGER_X2: return "MeshPager X2";
        case meshtastic_HardwareModel_T_CONNECT_PRO: return "T-Connect Pro";
        case meshtastic_HardwareModel_AXIOMETA_GENESIS_MINI: return "Genesis Mini";
        case meshtastic_HardwareModel_MAKERFABS_NOMAD_TERMINAL: return "Nomad Terminal";
        case meshtastic_HardwareModel_THINKNODE_MX: return "ThinkNode MX";
        case meshtastic_HardwareModel_PRIVATE_HW: return "Custom HW";
        default: return "Meshtastic";
    }
}

extern "C" void get_node_details_string(uint32_t nodeNum, char *idStr, size_t idLen,
                                         char *roleModelStr, size_t rmLen,
                                         char *batSigStr, size_t bsLen,
                                         char *gpsStr, size_t gpsLen)
{
    const meshtastic_NodeInfoLite *info = nodeDB ? nodeDB->getMeshNode(nodeNum) : nullptr;
    if (!info) {
        snprintf(idStr, idLen, "!%08x (%u)", (unsigned)nodeNum, (unsigned)nodeNum);
        snprintf(roleModelStr, rmLen, "Role: Client  •  Model: Node");
        snprintf(batSigStr, bsLen, "Bat: --  •  No signal data");
        snprintf(gpsStr, gpsLen, "GPS: No position data");
        return;
    }

    snprintf(idStr, idLen, "!%08x (%u)", (unsigned)nodeNum, (unsigned)nodeNum);

    const char *roleName = "Client";
    switch (info->role) {
        case meshtastic_Config_DeviceConfig_Role_CLIENT_MUTE: roleName = "Client Mute"; break;
        case meshtastic_Config_DeviceConfig_Role_ROUTER: roleName = "Router"; break;
        case meshtastic_Config_DeviceConfig_Role_REPEATER: roleName = "Repeater"; break;
        case meshtastic_Config_DeviceConfig_Role_TRACKER: roleName = "Tracker"; break;
        case meshtastic_Config_DeviceConfig_Role_SENSOR: roleName = "Sensor"; break;
        case meshtastic_Config_DeviceConfig_Role_TAK: roleName = "TAK"; break;
        case meshtastic_Config_DeviceConfig_Role_CLIENT_BASE: roleName = "Client Base"; break;
        default: roleName = "Client"; break;
    }

    const char *hwName = get_hw_model_name(info->hw_model);
    snprintf(roleModelStr, rmLen, "Role: %s  •  Model: %s", roleName, hwName);

    char batPart[32] = "Bat: --";
    meshtastic_DeviceMetrics met;
    if (nodeDB && nodeDB->copyNodeTelemetry(nodeNum, met) && met.battery_level > 0) {
        if (met.voltage > 0.1f)
            snprintf(batPart, sizeof(batPart), "Bat: %u%% (%.2fV)", (unsigned)met.battery_level, met.voltage);
        else
            snprintf(batPart, sizeof(batPart), "Bat: %u%%", (unsigned)met.battery_level);
    }

    char sigPart[32] = "";
    if (info->has_hops_away && info->hops_away == 0) {
        snprintf(sigPart, sizeof(sigPart), "Direct  SNR: %+.1fdB", info->snr);
    } else if (info->has_hops_away && info->hops_away > 0) {
        snprintf(sigPart, sizeof(sigPart), "%u hops  SNR: %+.1fdB", (unsigned)info->hops_away, info->snr);
    } else {
        snprintf(sigPart, sizeof(sigPart), "SNR: %+.1fdB", info->snr);
    }
    snprintf(batSigStr, bsLen, "%s  •  %s", batPart, sigPart);

    meshtastic_PositionLite pos;
    if (nodeDB && nodeDB->copyNodePosition(nodeNum, pos) && (pos.latitude_i != 0 || pos.longitude_i != 0)) {
        double lat = pos.latitude_i * 1e-7;
        double lon = pos.longitude_i * 1e-7;
        if (pos.altitude != 0) {
            snprintf(gpsStr, gpsLen, "GPS: %.4f, %.4f (%dm)", lat, lon, (int)pos.altitude);
        } else {
            snprintf(gpsStr, gpsLen, "GPS: %.4f, %.4f", lat, lon);
        }
    } else {
        snprintf(gpsStr, gpsLen, "GPS: No position data");
    }
}

#endif
