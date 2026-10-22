#pragma once
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef void CURL;

struct curl_slist {
    char *data;
    struct curl_slist *next;
};

typedef enum {
    CURLE_OK = 0,
    CURLE_UNSUPPORTED_PROTOCOL,
    CURLE_FAILED_INIT,
    CURLE_URL_MALFORMAT,
    CURLE_NOT_BUILT_IN,
    CURLE_COULDNT_RESOLVE_PROXY,
    CURLE_COULDNT_RESOLVE_HOST,
    CURLE_COULDNT_CONNECT,
    CURLE_WEIRD_SERVER_REPLY,
    CURLE_REMOTE_ACCESS_DENIED,
    CURLE_FTP_ACCEPT_FAILED,
    CURLE_FTP_ACCEPT_TIMEOUT,
    CURLE_FTP_PRET_FAILED,
    CURLE_RTSP_CSEQ_ERROR,
    CURLE_RTSP_SESSION_ERROR,
    CURLE_FTP_BAD_FILE_LIST,
    CURLE_CHUNK_FAILED,
    CURLE_NO_CONNECTION_AVAILABLE,
    CURLE_SSL_CLIENTCERT,
    CURLE_SSL_CACERT_BADFILE,
    CURLE_REMOTE_FILE_NOT_FOUND,
    CURLE_SSH,
    CURLE_SSL_SHUTDOWN_FAILED,
    CURLE_AGAIN,
    CURLE_SSL_CRL_BADFILE,
    CURLE_SSL_ISSUER_ERROR,
    CURLE_FTP_PRET_FAILED_2,
    CURLE_PARTIAL_FILE,
    CURLE_FTP_COULDNT_RETR_FILE,
    CURLE_QUOTE_ERROR,
    CURLE_HTTP_RETURNED_ERROR,
    CURLE_WRITE_ERROR,
    CURLE_UPLOAD_FAILED,
    CURLE_READ_ERROR,
    CURLE_OUT_OF_MEMORY,
    CURLE_OPERATION_TIMEDOUT,
    CURLE_GOT_NOTHING,
    CURLE_RECV_ERROR,
    CURLE_SEND_ERROR,
    CURLE_UNKNOWN_OPTION,
} CURLcode;

typedef enum {
    CURLOPT_URL = 10002,
    CURLOPT_WRITEFUNCTION = 20011,
    CURLOPT_WRITEDATA = 10001,
    CURLOPT_USERAGENT = 10018,
    CURLOPT_TIMEOUT = 13,
    CURLOPT_TIMEOUT_MS = 155,
    CURLOPT_CONNECTTIMEOUT = 78,
    CURLOPT_CONNECTTIMEOUT_MS = 156,
    CURLOPT_LOW_SPEED_LIMIT = 19,
    CURLOPT_LOW_SPEED_TIME = 20,
    CURLOPT_FOLLOWLOCATION = 52,
    CURLOPT_FAILONERROR = 45,
    CURLOPT_NOSIGNAL = 99,
    CURLOPT_HTTPHEADER = 10023,
    CURLOPT_HTTP_VERSION = 84,
    CURLOPT_SSL_VERIFYPEER = 64,
    CURLOPT_SSL_VERIFYHOST = 81,
    CURLOPT_DNS_CACHE_TIMEOUT = 92,
    CURLOPT_TCP_KEEPALIVE = 213,
    CURLOPT_ACCEPT_ENCODING = 10102,
} CURLoption;

typedef enum {
    CURLINFO_RESPONSE_CODE = 0x200000 + 2,
} CURLINFO;

#define CURL_GLOBAL_ALL 3
#define CURL_GLOBAL_DEFAULT CURL_GLOBAL_ALL
#define CURL_HTTP_VERSION_NONE 0
#define CURL_HTTP_VERSION_1_0 1
#define CURL_HTTP_VERSION_1_1 2
#define CURL_HTTP_VERSION_2_0 3
#define CURL_HTTP_VERSION_2TLS 4
#define CURL_HTTP_VERSION_3 30

static inline CURLcode curl_global_init(long flags) { (void)flags; return CURLE_OK; }
static inline void curl_global_cleanup(void) {}
static inline CURL *curl_easy_init(void) { return (CURL *)0; }
static inline void curl_easy_reset(CURL *curl) { (void)curl; }
static inline CURLcode curl_easy_setopt(CURL *curl, CURLoption option, ...) { (void)curl; (void)option; return CURLE_OK; }
static inline CURLcode curl_easy_perform(CURL *curl) { (void)curl; return CURLE_COULDNT_CONNECT; }
static inline void curl_easy_cleanup(CURL *curl) { (void)curl; }
static inline CURLcode curl_easy_getinfo(CURL *curl, CURLINFO info, ...) { (void)curl; (void)info; return CURLE_OK; }
static inline const char *curl_easy_strerror(CURLcode errornum) { (void)errornum; return "curl disabled"; }

static inline struct curl_slist *curl_slist_append(struct curl_slist *list, const char *string) { (void)string; return list; }
static inline void curl_slist_free_all(struct curl_slist *list) { (void)list; }

#ifdef __cplusplus
}
#endif
