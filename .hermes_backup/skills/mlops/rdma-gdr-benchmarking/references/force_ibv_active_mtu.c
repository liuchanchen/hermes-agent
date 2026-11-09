#define _GNU_SOURCE

#include <dlfcn.h>
#include <errno.h>
#include <infiniband/verbs.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#undef ibv_query_port

typedef int (*ibv_query_port_fn)(struct ibv_context *, uint8_t,
                                 struct _compat_ibv_port_attr *);
typedef void *(*dlsym_fn)(void *, const char *);

static ibv_query_port_fn real_query_port;
static dlsym_fn real_dlsym;

static enum ibv_mtu requested_mtu(void) {
  const char *value = getenv("FORCE_IBV_ACTIVE_MTU");

  if (value == NULL || value[0] == '\0' || value[0] == '1') {
    return IBV_MTU_1024;
  }
  if (value[0] == '2') {
    return IBV_MTU_2048;
  }
  if (value[0] == '4') {
    return IBV_MTU_4096;
  }

  fprintf(stderr, "force_ibv_active_mtu: unsupported MTU '%s'\n", value);
  return IBV_MTU_1024;
}

int ibv_query_port(struct ibv_context *context, uint8_t port_num,
                   struct _compat_ibv_port_attr *compat_port_attr) {
  static int reported;
  struct ibv_port_attr *port_attr = (struct ibv_port_attr *)compat_port_attr;

  if (real_query_port == NULL) {
    real_query_port =
        (ibv_query_port_fn)dlvsym(RTLD_NEXT, "ibv_query_port", "IBVERBS_1.1");
    if (real_query_port == NULL) {
      fprintf(stderr, "force_ibv_active_mtu: dlvsym failed: %s\n", dlerror());
      errno = ENOSYS;
      return -1;
    }
  }

  int result = real_query_port(context, port_num, compat_port_attr);
  enum ibv_mtu cap = requested_mtu();
  if (result == 0 && port_attr != NULL && port_attr->active_mtu > cap) {
    enum ibv_mtu original = port_attr->active_mtu;
    port_attr->active_mtu = cap;
    if (!reported) {
      fprintf(stderr,
              "force_ibv_active_mtu: process-local cap active_mtu %d -> %d\n",
              original, cap);
      reported = 1;
    }
  }
  return result;
}

/* NCCL resolves verbs symbols from a dlopen() handle. Interpose that lookup so
 * its process-local ibv_query_port call receives the capped value above. */
void *dlsym(void *handle, const char *symbol) {
  if (real_dlsym == NULL) {
    real_dlsym = (dlsym_fn)dlvsym(RTLD_NEXT, "dlsym", "GLIBC_2.34");
    if (real_dlsym == NULL) {
      real_dlsym = (dlsym_fn)dlvsym(RTLD_NEXT, "dlsym", "GLIBC_2.2.5");
    }
  }
  if (real_dlsym == NULL) {
    return NULL;
  }

  void *resolved = real_dlsym(handle, symbol);
  if (strcmp(symbol, "ibv_query_port") == 0) {
    real_query_port = (ibv_query_port_fn)resolved;
    return (void *)&ibv_query_port;
  }
  return resolved;
}
