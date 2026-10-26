CC ?= gcc
CFLAGS ?= -O2 -fPIC -Wall -Wextra -Wpedantic
LDFLAGS ?= -shared
LDLIBS ?= -pthread

TARGET := libopen_trofeo_fps_probe.so
SRC := open_trofeo_fps_probe.c

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(SRC)
	@set -e; probe_tmp=$$(mktemp ./.$(TARGET).XXXXXX); \
	trap 'rm -f "$$probe_tmp"' EXIT; \
	$(CC) $(CFLAGS) $(LDFLAGS) -o "$$probe_tmp" $< $(LDLIBS); \
	chmod 0755 "$$probe_tmp"; \
	mv -f "$$probe_tmp" $@

clean:
	rm -f $(TARGET)
