#define _GNU_SOURCE

#include <errno.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <time.h>
#include <unistd.h>

typedef void *VkDevice;
typedef void *VkInstance;
typedef void *VkPhysicalDevice;
typedef void *VkQueue;
typedef const void *VkPresentInfoKHR;
typedef int32_t VkResult;
typedef void (*PFN_vkVoidFunction)(void);
typedef PFN_vkVoidFunction (*PFN_vkGetDeviceProcAddr)(VkDevice device, const char *name);
typedef PFN_vkVoidFunction (*PFN_vkGetInstanceProcAddr)(void *instance, const char *name);

typedef struct VkAllocationCallbacks VkAllocationCallbacks;
typedef struct VkBaseInStructure {
    int32_t sType;
    const struct VkBaseInStructure *pNext;
} VkBaseInStructure;
typedef struct VkDeviceCreateInfo {
    int32_t sType;
    const void *pNext;
} VkDeviceCreateInfo;
typedef struct VkInstanceCreateInfo {
    int32_t sType;
    const void *pNext;
} VkInstanceCreateInfo;

typedef VkResult (*PFN_vkCreateDevice)(
    VkPhysicalDevice physical_device,
    const VkDeviceCreateInfo *create_info,
    const VkAllocationCallbacks *allocator,
    VkDevice *device
);
typedef VkResult (*PFN_vkCreateInstance)(
    const VkInstanceCreateInfo *create_info,
    const VkAllocationCallbacks *allocator,
    VkInstance *instance
);
typedef VkResult (*PFN_vkQueuePresentKHR)(VkQueue queue, const VkPresentInfoKHR *present_info);

typedef enum VkLayerFunction {
    VK_LAYER_LINK_INFO = 0,
    VK_LOADER_DATA_CALLBACK = 1,
    VK_LOADER_LAYER_CREATE_DEVICE_CALLBACK = 2
} VkLayerFunction;
typedef struct VkLayerInstanceLink {
    struct VkLayerInstanceLink *pNext;
    PFN_vkGetInstanceProcAddr pfnNextGetInstanceProcAddr;
    PFN_vkGetDeviceProcAddr pfnNextGetDeviceProcAddr;
} VkLayerInstanceLink;
typedef struct VkLayerDeviceLink {
    struct VkLayerDeviceLink *pNext;
    PFN_vkGetInstanceProcAddr pfnNextGetInstanceProcAddr;
    PFN_vkGetDeviceProcAddr pfnNextGetDeviceProcAddr;
} VkLayerDeviceLink;
typedef struct VkLayerInstanceCreateInfo {
    int32_t sType;
    const void *pNext;
    VkLayerFunction function;
    union {
        VkLayerInstanceLink *pLayerInfo;
        void *pfnSetInstanceLoaderData;
    } u;
} VkLayerInstanceCreateInfo;
typedef struct VkLayerDeviceCreateInfo {
    int32_t sType;
    const void *pNext;
    VkLayerFunction function;
    union {
        VkLayerDeviceLink *pLayerInfo;
        void *pfnSetDeviceLoaderData;
    } u;
} VkLayerDeviceCreateInfo;

enum {
    VK_STRUCTURE_TYPE_LOADER_INSTANCE_CREATE_INFO = 47,
    VK_STRUCTURE_TYPE_LOADER_DEVICE_CREATE_INFO = 48
};

typedef struct VkNegotiateLayerInterface {
    int32_t sType;
    void *pNext;
    uint32_t loaderLayerInterfaceVersion;
    PFN_vkGetInstanceProcAddr pfnGetInstanceProcAddr;
    PFN_vkGetDeviceProcAddr pfnGetDeviceProcAddr;
    PFN_vkVoidFunction pfnGetPhysicalDeviceProcAddr;
} VkNegotiateLayerInterface;

PFN_vkVoidFunction vkGetDeviceProcAddr(VkDevice device, const char *name);
PFN_vkVoidFunction vkGetInstanceProcAddr(void *instance, const char *name);
VkResult vkCreateDevice(
    VkPhysicalDevice physical_device,
    const VkDeviceCreateInfo *create_info,
    const VkAllocationCallbacks *allocator,
    VkDevice *device
);
VkResult vkCreateInstance(
    const VkInstanceCreateInfo *create_info,
    const VkAllocationCallbacks *allocator,
    VkInstance *instance
);
VkResult vkNegotiateLoaderLayerInterfaceVersion(VkNegotiateLayerInterface *version_struct);

static pthread_mutex_t g_lock = PTHREAD_MUTEX_INITIALIZER;
static PFN_vkCreateDevice g_real_create_device = NULL;
static PFN_vkCreateInstance g_real_create_instance = NULL;
static PFN_vkGetDeviceProcAddr g_real_get_device_proc_addr = NULL;
static PFN_vkGetInstanceProcAddr g_real_get_instance_proc_addr = NULL;
static PFN_vkQueuePresentKHR g_real_queue_present = NULL;
static VkInstance g_instance = NULL;
static int g_sock = -1;
static struct sockaddr_un g_sock_addr;
static int g_sock_ready = 0;
static uint64_t g_window_start_ns = 0;
static uint64_t g_session_start_ns = 0;
static uint64_t g_last_present_ns = 0;
static unsigned int g_frame_count = 0;
static uint64_t g_session_frame_count = 0;
static double g_last_fps = 0.0;
static double g_last_frametime_ms = 0.0;
static double g_last_sample_window_ms = 0.0;
static uint64_t g_last_send_ns = 0;
static int g_logged_first_present = 0;
static int g_logged_socket_error = 0;

static const char *state_dir(char *buffer, size_t size) {
    const char *configured = getenv("OPEN_TROFEO_STATE_HOME");
    if (configured != NULL && configured[0] != '\0') {
        snprintf(buffer, size, "%s", configured);
        return buffer;
    }
    const char *state_home = getenv("XDG_STATE_HOME");
    if (state_home != NULL && state_home[0] != '\0') {
        snprintf(buffer, size, "%s/open-trofeo-lcd", state_home);
        return buffer;
    }
    const char *home = getenv("HOME");
    if (home != NULL && home[0] != '\0') {
        snprintf(buffer, size, "%s/.local/state/open-trofeo-lcd", home);
        return buffer;
    }
    snprintf(buffer, size, "/tmp/open-trofeo-lcd");
    return buffer;
}

static void mkdir_p(const char *path) {
    if (path == NULL || path[0] == '\0') {
        return;
    }
    char tmp[512];
    snprintf(tmp, sizeof(tmp), "%s", path);
    size_t len = strlen(tmp);
    if (len == 0) {
        return;
    }
    if (tmp[len - 1] == '/') {
        tmp[len - 1] = '\0';
    }
    for (char *p = tmp + 1; *p != '\0'; ++p) {
        if (*p == '/') {
            *p = '\0';
            mkdir(tmp, 0700);
            *p = '/';
        }
    }
    mkdir(tmp, 0700);
}

static void log_event(const char *event, const char *detail) {
    char dir[512];
    state_dir(dir, sizeof(dir));
    mkdir_p(dir);
    char path[640];
    snprintf(path, sizeof(path), "%s/fps-probe.log", dir);
    FILE *handle = fopen(path, "a");
    if (handle == NULL) {
        return;
    }
    time_t now = time(NULL);
    fprintf(
        handle,
        "%ld pid=%ld event=%s detail=%s game=%s launcher=%s layer=%s socket=%s\n",
        (long)now,
        (long)getpid(),
        event == NULL ? "" : event,
        detail == NULL ? "" : detail,
        getenv("OPEN_TROFEO_GAME_NAME") == NULL ? "" : getenv("OPEN_TROFEO_GAME_NAME"),
        getenv("OPEN_TROFEO_GAME_LAUNCHER") == NULL ? "" : getenv("OPEN_TROFEO_GAME_LAUNCHER"),
        getenv("OPEN_TROFEO_FPS_LAYER") == NULL ? "" : getenv("OPEN_TROFEO_FPS_LAYER"),
        getenv("OPEN_TROFEO_FPS_SOCKET") == NULL ? "" : getenv("OPEN_TROFEO_FPS_SOCKET")
    );
    fclose(handle);
}

static void copy_queue_present_symbol(PFN_vkQueuePresentKHR *target, PFN_vkVoidFunction symbol) {
    memcpy(target, &symbol, sizeof(*target));
}

static void copy_create_device_symbol(PFN_vkCreateDevice *target, PFN_vkVoidFunction symbol) {
    memcpy(target, &symbol, sizeof(*target));
}

static void copy_create_instance_symbol(PFN_vkCreateInstance *target, PFN_vkVoidFunction symbol) {
    memcpy(target, &symbol, sizeof(*target));
}

static const void *instance_pnext(const VkInstanceCreateInfo *create_info) {
    return create_info == NULL ? NULL : create_info->pNext;
}

static const void *device_pnext(const VkDeviceCreateInfo *create_info) {
    return create_info == NULL ? NULL : create_info->pNext;
}

static VkLayerInstanceCreateInfo *find_instance_layer_info(const VkInstanceCreateInfo *create_info) {
    const VkBaseInStructure *chain = (const VkBaseInStructure *)instance_pnext(create_info);
    while (chain != NULL) {
        if (chain->sType == VK_STRUCTURE_TYPE_LOADER_INSTANCE_CREATE_INFO) {
            VkLayerInstanceCreateInfo *layer_info = (VkLayerInstanceCreateInfo *)chain;
            if (layer_info->function == VK_LAYER_LINK_INFO) {
                return layer_info;
            }
        }
        chain = chain->pNext;
    }
    return NULL;
}

static VkLayerDeviceCreateInfo *find_device_layer_info(const VkDeviceCreateInfo *create_info) {
    const VkBaseInStructure *chain = (const VkBaseInStructure *)device_pnext(create_info);
    while (chain != NULL) {
        if (chain->sType == VK_STRUCTURE_TYPE_LOADER_DEVICE_CREATE_INFO) {
            VkLayerDeviceCreateInfo *layer_info = (VkLayerDeviceCreateInfo *)chain;
            if (layer_info->function == VK_LAYER_LINK_INFO) {
                return layer_info;
            }
        }
        chain = chain->pNext;
    }
    return NULL;
}

static void json_escape(char *dst, size_t dst_size, const char *src) {
    if (dst_size == 0) {
        return;
    }
    size_t out = 0;
    if (src == NULL) {
        dst[0] = '\0';
        return;
    }
    for (size_t i = 0; src[i] != '\0' && out + 1 < dst_size; ++i) {
        unsigned char ch = (unsigned char)src[i];
        if ((ch == '"' || ch == '\\') && out + 2 < dst_size) {
            dst[out++] = '\\';
            dst[out++] = (char)ch;
        } else if (ch >= 0x20) {
            dst[out++] = (char)ch;
        }
    }
    dst[out] = '\0';
}

static uint64_t now_ns(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) {
        return 0;
    }
    return ((uint64_t)ts.tv_sec * 1000000000ull) + (uint64_t)ts.tv_nsec;
}

static const char *default_socket_path(char *buffer, size_t size) {
    const char *configured = getenv("OPEN_TROFEO_FPS_SOCKET");
    if (configured != NULL && configured[0] != '\0') {
        return configured;
    }
    const char *runtime_dir = getenv("XDG_RUNTIME_DIR");
    if (runtime_dir != NULL && runtime_dir[0] != '\0') {
        snprintf(buffer, size, "%s/open-trofeo-lcd/fps.sock", runtime_dir);
        return buffer;
    }
    snprintf(buffer, size, "/run/user/%ld/open-trofeo-lcd/fps.sock", (long)getuid());
    return buffer;
}

static void init_socket_locked(void) {
    if (g_sock_ready) {
        return;
    }
    char path_buffer[sizeof(g_sock_addr.sun_path)] = {0};
    const char *path = default_socket_path(path_buffer, sizeof(path_buffer));
    if (path == NULL || strlen(path) >= sizeof(g_sock_addr.sun_path)) {
        g_sock_ready = -1;
        return;
    }
    g_sock = socket(AF_UNIX, SOCK_DGRAM | SOCK_CLOEXEC, 0);
    if (g_sock < 0) {
        g_sock_ready = -1;
        return;
    }
    memset(&g_sock_addr, 0, sizeof(g_sock_addr));
    g_sock_addr.sun_family = AF_UNIX;
    memcpy(g_sock_addr.sun_path, path, strlen(path) + 1);
    g_sock_ready = 1;
}

static void send_sample_locked(uint64_t ts_ns) {
    init_socket_locked();
    if (g_sock_ready != 1 || g_sock < 0) {
        return;
    }
    if (g_last_send_ns != 0 && ts_ns > g_last_send_ns && (ts_ns - g_last_send_ns) < 100000000ull) {
        return;
    }
    const char *game_name = getenv("OPEN_TROFEO_GAME_NAME");
    const char *launcher = getenv("OPEN_TROFEO_GAME_LAUNCHER");
    if (game_name == NULL || game_name[0] == '\0') {
        game_name = "Vulkan Game";
    }
    if (launcher == NULL || launcher[0] == '\0') {
        launcher = "native";
    }
    char game_name_json[192];
    char launcher_json[96];
    json_escape(game_name_json, sizeof(game_name_json), game_name);
    json_escape(launcher_json, sizeof(launcher_json), launcher);
    char payload[768];
    const char *source = getenv("OPEN_TROFEO_FPS_LAYER") != NULL
        ? "open-trofeo-vulkan-layer"
        : "open-trofeo-vulkan-preload";
    int written = snprintf(
        payload,
        sizeof(payload),
        "{\"fps\":%.3f,\"frametime_ms\":%.3f,\"sample_window_ms\":%.3f,"
        "\"session_frames\":%llu,\"session_time_s\":%.3f,\"source\":\"%s\","
        "\"game_name\":\"%s\",\"game_process\":\"vulkan\",\"game_launcher\":\"%s\","
        "\"game_overlay\":\"none\",\"pid\":%ld,\"timestamp\":%.3f}",
        g_last_fps,
        g_last_frametime_ms,
        g_last_sample_window_ms,
        (unsigned long long)g_session_frame_count,
        (g_session_start_ns > 0 && ts_ns > g_session_start_ns) ? (double)(ts_ns - g_session_start_ns) / 1000000000.0 : 0.0,
        source,
        game_name_json,
        launcher_json,
        (long)getpid(),
        (double)time(NULL)
    );
    if (written <= 0) {
        return;
    }
    size_t len = (size_t)written;
    if (len >= sizeof(payload)) {
        len = sizeof(payload) - 1;
    }
    if (sendto(g_sock, payload, len, MSG_DONTWAIT, (const struct sockaddr *)&g_sock_addr, sizeof(g_sock_addr)) < 0) {
        if (!g_logged_socket_error) {
            char detail[96];
            snprintf(detail, sizeof(detail), "sendto errno=%d", errno);
            log_event("socket-error", detail);
            g_logged_socket_error = 1;
        }
        if (errno == ENOENT || errno == ECONNREFUSED) {
            g_sock_ready = 0;
        }
    } else {
        g_last_send_ns = ts_ns;
    }
}

static void record_present(void) {
    uint64_t ts_ns = now_ns();
    if (ts_ns == 0) {
        return;
    }
    if (!g_logged_first_present) {
        log_event("first-present", "vkQueuePresentKHR");
        g_logged_first_present = 1;
    }
    pthread_mutex_lock(&g_lock);
    if (g_session_start_ns == 0) {
        g_session_start_ns = ts_ns;
    }
    if (g_last_present_ns != 0 && ts_ns > g_last_present_ns) {
        g_last_frametime_ms = (double)(ts_ns - g_last_present_ns) / 1000000.0;
    }
    g_last_present_ns = ts_ns;
    if (g_window_start_ns == 0) {
        g_window_start_ns = ts_ns;
    }
    g_frame_count += 1;
    g_session_frame_count += 1;
    uint64_t elapsed_ns = ts_ns - g_window_start_ns;
    if (elapsed_ns >= 250000000ull) {
        g_last_fps = ((double)g_frame_count * 1000000000.0) / (double)elapsed_ns;
        g_last_sample_window_ms = (double)elapsed_ns / 1000000.0;
        if (g_last_frametime_ms <= 0.0 && g_last_fps > 0.0) {
            g_last_frametime_ms = 1000.0 / g_last_fps;
        }
        g_window_start_ns = ts_ns;
        g_frame_count = 0;
        send_sample_locked(ts_ns);
    }
    pthread_mutex_unlock(&g_lock);
}

VkResult vkCreateInstance(
    const VkInstanceCreateInfo *create_info,
    const VkAllocationCallbacks *allocator,
    VkInstance *instance
) {
    PFN_vkCreateInstance real_fn = NULL;
    VkLayerInstanceCreateInfo *layer_info = find_instance_layer_info(create_info);
    if (layer_info != NULL && layer_info->u.pLayerInfo != NULL) {
        VkLayerInstanceLink *next = layer_info->u.pLayerInfo;
        PFN_vkGetInstanceProcAddr next_gipa = next->pfnNextGetInstanceProcAddr;
        layer_info->u.pLayerInfo = next->pNext;
        if (next_gipa != NULL) {
            PFN_vkVoidFunction create_symbol = next_gipa(NULL, "vkCreateInstance");
            if (create_symbol != NULL) {
                pthread_mutex_lock(&g_lock);
                g_real_get_instance_proc_addr = next_gipa;
                copy_create_instance_symbol(&g_real_create_instance, create_symbol);
                real_fn = g_real_create_instance;
                pthread_mutex_unlock(&g_lock);
            }
        }
    }
    if (real_fn != NULL) {
        log_event("create-instance", "layer-chain");
        VkResult result = real_fn(create_info, allocator, instance);
        if (result == 0 && instance != NULL) {
            pthread_mutex_lock(&g_lock);
            g_instance = *instance;
            pthread_mutex_unlock(&g_lock);
        }
        return result;
    }
    pthread_mutex_lock(&g_lock);
    real_fn = g_real_create_instance;
    pthread_mutex_unlock(&g_lock);
    if (real_fn == NULL) {
        log_event("create-instance-failed", "no-next");
        return -3;
    }
    log_event("create-instance", "fallback");
    VkResult result = real_fn(create_info, allocator, instance);
    if (result == 0 && instance != NULL) {
        pthread_mutex_lock(&g_lock);
        g_instance = *instance;
        pthread_mutex_unlock(&g_lock);
    }
    return result;
}

VkResult vkCreateDevice(
    VkPhysicalDevice physical_device,
    const VkDeviceCreateInfo *create_info,
    const VkAllocationCallbacks *allocator,
    VkDevice *device
) {
    PFN_vkCreateDevice real_fn = NULL;
    VkLayerDeviceCreateInfo *layer_info = find_device_layer_info(create_info);
    if (layer_info != NULL && layer_info->u.pLayerInfo != NULL) {
        VkLayerDeviceLink *next = layer_info->u.pLayerInfo;
        PFN_vkGetInstanceProcAddr next_gipa = next->pfnNextGetInstanceProcAddr;
        PFN_vkGetDeviceProcAddr next_gdpa = next->pfnNextGetDeviceProcAddr;
        layer_info->u.pLayerInfo = next->pNext;
        VkInstance instance = NULL;
        pthread_mutex_lock(&g_lock);
        instance = g_instance;
        pthread_mutex_unlock(&g_lock);
        PFN_vkVoidFunction create_symbol = NULL;
        if (next_gipa != NULL) {
            create_symbol = next_gipa(instance, "vkCreateDevice");
            if (create_symbol == NULL) {
                create_symbol = next_gipa(NULL, "vkCreateDevice");
            }
        }
        if (create_symbol == NULL && next_gdpa != NULL) {
            create_symbol = next_gdpa(NULL, "vkCreateDevice");
        }
        if (create_symbol != NULL) {
            pthread_mutex_lock(&g_lock);
            g_real_get_instance_proc_addr = next_gipa;
            g_real_get_device_proc_addr = next_gdpa;
            copy_create_device_symbol(&g_real_create_device, create_symbol);
            real_fn = g_real_create_device;
            pthread_mutex_unlock(&g_lock);
        } else {
            log_event("create-device-link-miss", instance == NULL ? "no-instance" : "no-symbol");
        }
    }
    if (real_fn != NULL) {
        log_event("create-device", "layer-chain");
        return real_fn(physical_device, create_info, allocator, device);
    }
    pthread_mutex_lock(&g_lock);
    real_fn = g_real_create_device;
    pthread_mutex_unlock(&g_lock);
    if (real_fn == NULL) {
        log_event("create-device-failed", "no-next");
        return -3;
    }
    log_event("create-device", "fallback");
    return real_fn(physical_device, create_info, allocator, device);
}

VkResult vkQueuePresentKHR(VkQueue queue, const VkPresentInfoKHR *present_info) {
    PFN_vkQueuePresentKHR real_fn = NULL;
    pthread_mutex_lock(&g_lock);
    real_fn = g_real_queue_present;
    pthread_mutex_unlock(&g_lock);
    if (real_fn == NULL) {
        return -3;
    }
    VkResult result = real_fn(queue, present_info);
    record_present();
    return result;
}

PFN_vkVoidFunction vkGetDeviceProcAddr(VkDevice device, const char *name) {
    pthread_mutex_lock(&g_lock);
    PFN_vkGetDeviceProcAddr real_fn = g_real_get_device_proc_addr;
    pthread_mutex_unlock(&g_lock);
    if (name != NULL && strcmp(name, "vkCreateDevice") == 0) {
        return (PFN_vkVoidFunction)vkCreateDevice;
    }
    if (name != NULL && strcmp(name, "vkQueuePresentKHR") == 0) {
        PFN_vkVoidFunction next = NULL;
        if (real_fn != NULL) {
            next = real_fn(device, name);
            if (next != NULL && next != (PFN_vkVoidFunction)vkQueuePresentKHR) {
                pthread_mutex_lock(&g_lock);
                copy_queue_present_symbol(&g_real_queue_present, next);
                pthread_mutex_unlock(&g_lock);
            }
        }
        pthread_mutex_lock(&g_lock);
        int can_wrap = g_real_queue_present != NULL;
        pthread_mutex_unlock(&g_lock);
        return can_wrap ? (PFN_vkVoidFunction)vkQueuePresentKHR : next;
    }
    return real_fn == NULL ? NULL : real_fn(device, name);
}

PFN_vkVoidFunction vkGetInstanceProcAddr(void *instance, const char *name) {
    pthread_mutex_lock(&g_lock);
    PFN_vkGetInstanceProcAddr real_fn = g_real_get_instance_proc_addr;
    pthread_mutex_unlock(&g_lock);
    if (name != NULL && strcmp(name, "vkCreateInstance") == 0) {
        return (PFN_vkVoidFunction)vkCreateInstance;
    }
    if (name != NULL && strcmp(name, "vkCreateDevice") == 0) {
        return (PFN_vkVoidFunction)vkCreateDevice;
    }
    if (name != NULL && strcmp(name, "vkQueuePresentKHR") == 0) {
        return g_real_queue_present == NULL ? NULL : (PFN_vkVoidFunction)vkQueuePresentKHR;
    }
    if (name != NULL && strcmp(name, "vkNegotiateLoaderLayerInterfaceVersion") == 0) {
        return (PFN_vkVoidFunction)vkNegotiateLoaderLayerInterfaceVersion;
    }
    if (name != NULL && strcmp(name, "vkGetInstanceProcAddr") == 0) {
        return (PFN_vkVoidFunction)vkGetInstanceProcAddr;
    }
    if (name != NULL && strcmp(name, "vkGetDeviceProcAddr") == 0) {
        return (PFN_vkVoidFunction)vkGetDeviceProcAddr;
    }
    return real_fn == NULL ? NULL : real_fn(instance, name);
}

PFN_vkVoidFunction open_trofeo_GetDeviceProcAddr(VkDevice device, const char *name) {
    return vkGetDeviceProcAddr(device, name);
}

PFN_vkVoidFunction open_trofeo_GetInstanceProcAddr(void *instance, const char *name) {
    return vkGetInstanceProcAddr(instance, name);
}

VkResult vkNegotiateLoaderLayerInterfaceVersion(VkNegotiateLayerInterface *version_struct) {
    if (version_struct == NULL) {
        return -3;
    }
    if (version_struct->loaderLayerInterfaceVersion > 2) {
        version_struct->loaderLayerInterfaceVersion = 2;
    }
    version_struct->pfnGetInstanceProcAddr = open_trofeo_GetInstanceProcAddr;
    version_struct->pfnGetDeviceProcAddr = open_trofeo_GetDeviceProcAddr;
    version_struct->pfnGetPhysicalDeviceProcAddr = NULL;
    log_event("negotiate", "ok");
    return 0;
}

__attribute__((constructor)) static void open_trofeo_layer_loaded(void) {
    log_event("loaded", "library");
}
