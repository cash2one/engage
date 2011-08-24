ifndef ENGAGE_CODE_HOME
ENGAGE_CODE_HOME=$(shell cd ../../..; pwd)
export ENGAGE_CODE_HOME
endif

CONFIG_SRC_HOME=$(ENGAGE_CODE_HOME)/config_src

include $(CONFIG_SRC_HOME)/config.make
include $(CONFIG_SRC_HOME)/rules.make

EXE_FILE=configurator

THIRD_PARTY=$(CONFIG_SRC_HOME)/3rdparty
CONFIG=$(CONFIG_SRC_HOME)/config

all: debug opt

debug: exe config.o

opt: exe config.o

exe: mlmain.cmx
	gcc -I $(OCAML_LIBDIR) -c main.c
	$(OCAML_OPT_C) str.cmxa unix.cmxa $(THIRD_PARTY)/camlmsat/libcamlmsat.a $(THIRD_PARTY)/camlmsat/predicates.cmx  main.o $(CONFIG)/config.cmxa mlmain.cmx -cclib -L$(CONFIG)/ -cc g++ -o $(EXE_FILE)

config.o: mlmain.cmx
	$(OCAML_OPT_C) str.cmxa unix.cmxa $(THIRD_PARTY)/camlmsat/libcamlmsat.a $(THIRD_PARTY)/camlmsat/predicates.cmx  $(CONFIG)/cfunctions.o $(CONFIG)/config.cmxa mlmain.cmx -cclib -L$(CONFIG)/ -cc g++ -verbose -output-obj -o config.o

mlmain.cmx: mlmain.ml
	$(OCAML_OPT_C) -c -I $(CONFIG) mlmain.ml

#test: exe
#	./$(EXE_FILE) $(GENFORMA_CODE_HOME)/test/config/openmrs_resources.json $(GENFORMA_CODE_HOME)/test/config/openmrs_inst_spec.json

clean:
	rm -f *.cm* *.exe *.o $(EXE_FILE) install.out install.script

.PHONY: clean exe debug opt test
