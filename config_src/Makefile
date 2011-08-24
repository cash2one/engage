# makefile for configuration engine

ifndef ENGAGE_CODE_HOME
ENGAGE_CODE_HOME=$(shell cd ..; pwd)
export ENGAGE_CODE_HOME
endif

CONFIG_SRC_HOME=$(ENGAGE_CODE_HOME)/config_src

include $(CONFIG_SRC_HOME)/config.make
include $(CONFIG_SRC_HOME)/rules.make


CONFIG_BIN=$(ENGAGE_CODE_HOME)/bin/configurator-$(ENGAGE_PLATFORM)

all: $(CONFIG_BIN)

$(CONFIG_BIN): config
	mkdir -p $(ENGAGE_CODE_HOME)/bin
	cp $(CONFIG_SRC_HOME)/config/c_wrapper/configurator $(CONFIG_BIN)
	chmod 755 $(CONFIG_BIN)

config: 3rdparty
	cd $(CONFIG_SRC_HOME)/config; make all

3rdparty:
	cd $(CONFIG_SRC_HOME)/3rdparty; make all

clean:
	cd $(CONFIG_SRC_HOME)/3rdparty; make clean
	cd $(CONFIG_SRC_HOME)/config; make clean
	rm -rf $(ENGAGE_CODE_HOME)/bin

.PHONY: all 3rdparty config clean