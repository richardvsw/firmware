#ifndef _I2C_SMBUS_H
#define _I2C_SMBUS_H

#include <linux/types.h>
#include <linux/i2c.h>
#include <linux/i2c-dev.h>
#include <sys/ioctl.h>

static inline __s32 i2c_smbus_access(int file, char read_write, __u8 command,
                                     int size, union i2c_smbus_data *data)
{
    struct i2c_smbus_ioctl_data args;
    args.read_write = read_write;
    args.command = command;
    args.size = size;
    args.data = data;
    return ioctl(file, I2C_SMBUS, &args);
}

static inline __s32 i2c_smbus_write_quick(int file, __u8 value)
{
    return i2c_smbus_access(file, value, 0, I2C_SMBUS_QUICK, NULL);
}

#endif
