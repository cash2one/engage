
# build all the third-party libraries

ifndef ENGAGE_CODE_HOME
ENGAGE_CODE_HOME=$(shell cd ../..; pwd)
export ENGAGE_CODE_HOME
endif

CONFIG_SRC_HOME=$(ENGAGE_CODE_HOME)/config_src

include $(CONFIG_SRC_HOME)/config.make
include $(CONFIG_SRC_HOME)/rules.make

all:
	cd $(MINISAT_DIR); make all
	cd $(CAMLMSAT_DIR); make all

debug:
	cd $(MINISAT_DIR); make debug
	cd $(CAMLMSAT_DIR); make debug

opt:
	cd $(MINISAT_DIR); make opt
	cd $(CAMLMSAT_DIR); make opt

clean:
	cd $(MINISAT_DIR); make clean
	cd $(CAMLMSAT_DIR); make clean


.PHONY: clean all debug opt
