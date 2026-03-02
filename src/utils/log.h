/**
 * @copyright Copyright (c) 2025, SDU SPgroup Holding Limited
 */
#ifndef HMC_LOG_H
#define HMC_LOG_H

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <mutex>

#include <hmc.h>

namespace hmc_log_detail {

inline std::mutex &log_mutex() {
  static std::mutex m;
  return m;
}

inline void print_line(std::ostream &os, const char *level, const char *msg) {
  std::lock_guard<std::mutex> lock(log_mutex());
  os << "[" << level << "] " << msg << std::endl;
}

inline bool debug_enabled() {
  static const bool enabled = []() {
    const char *v = std::getenv("HMC_LOG_DEBUG");
    if (!v || !*v) return false;
    return std::strcmp(v, "1") == 0 || std::strcmp(v, "true") == 0 ||
           std::strcmp(v, "TRUE") == 0 || std::strcmp(v, "on") == 0 ||
           std::strcmp(v, "ON") == 0;
  }();
  return enabled;
}

} // namespace hmc_log_detail

/* log */
#define logError(fmt, ...)                                                     \
  do {                                                                         \
    char log_buffer[1024];                                                     \
    int len = std::snprintf(log_buffer, sizeof(log_buffer), fmt, ##__VA_ARGS__); \
    if (len >= 0) {                                                            \
      hmc_log_detail::print_line(std::cerr, "ERROR", log_buffer);              \
    }                                                                          \
  } while (0)

#define logDebug(fmt, ...)                                                     \
  do {                                                                         \
    if (hmc_log_detail::debug_enabled()) {                                     \
      char log_buffer[1024];                                                   \
      int len = std::snprintf(log_buffer, sizeof(log_buffer), fmt, ##__VA_ARGS__); \
      if (len >= 0) {                                                          \
        hmc_log_detail::print_line(std::cerr, "DEBUG", log_buffer);            \
      }                                                                        \
    }                                                                          \
  } while (0)

#define logInfo(fmt, ...)                                                      \
  do {                                                                         \
    char log_buffer[1024];                                                     \
    int len = std::snprintf(log_buffer, sizeof(log_buffer), fmt, ##__VA_ARGS__); \
    if (len >= 0) {                                                            \
      hmc_log_detail::print_line(std::cout, "INFO", log_buffer);               \
    }                                                                          \
  } while (0)

#endif // HMC_LOG_H
