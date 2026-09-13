CC ?= gcc
CFLAGS ?= -O2 -fPIC -Wall -Wextra -Wpedantic
LDFLAGS ?= -shared
LDLIBS ?= -pthread

TARGET := libopen_trofeo_fps_probe.so
SRC := open_trofeo_fps_probe.c

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $< $(LDLIBS)

clean:
	rm -f $(TARGET)
