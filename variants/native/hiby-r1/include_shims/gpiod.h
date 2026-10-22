#ifndef _GPIOD_H_
#define _GPIOD_H_

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>

#define GPIOD_LINE_BULK_MAX_LINES 64

enum {
    GPIOD_LINE_REQUEST_DIRECTION_AS_IS = 1,
    GPIOD_LINE_REQUEST_DIRECTION_INPUT = 2,
    GPIOD_LINE_REQUEST_DIRECTION_OUTPUT = 3,
    GPIOD_LINE_REQUEST_FLAG_BIAS_PULL_UP = (1 << 3),
    GPIOD_LINE_REQUEST_FLAG_BIAS_PULL_DOWN = (1 << 4),
};

struct gpiod_chip;
struct gpiod_line;

struct gpiod_line_request_config {
    const char *consumer;
    int request_type;
    int flags;
};

struct gpiod_chip *gpiod_chip_open(const char *path);
void gpiod_chip_close(struct gpiod_chip *chip);
const char *gpiod_chip_label(struct gpiod_chip *chip);
struct gpiod_line *gpiod_chip_find_line(struct gpiod_chip *chip, const char *name);
struct gpiod_line *gpiod_chip_get_line(struct gpiod_chip *chip, unsigned int offset);

int gpiod_line_request(struct gpiod_line *line, const struct gpiod_line_request_config *config, int default_val);
int gpiod_line_request_input(struct gpiod_line *line, const char *consumer);
int gpiod_line_request_output(struct gpiod_line *line, const char *consumer, int default_val);
int gpiod_line_set_value(struct gpiod_line *line, int value);
int gpiod_line_get_value(struct gpiod_line *line);
int gpiod_line_set_flags(struct gpiod_line *line, int flags);
void gpiod_line_release(struct gpiod_line *line);

#ifdef __cplusplus
}
#endif

#endif
