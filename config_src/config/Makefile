
ifndef ENGAGE_CODE_HOME
ENGAGE_CODE_HOME=$(shell cd ../..; pwd)
export ENGAGE_CODE_HOME
endif

CONFIG_SRC_HOME=$(ENGAGE_CODE_HOME)/config_src

include $(CONFIG_SRC_HOME)/config.make

# this needs to go before the include of rules.make to force ocaml rules to use it
OCAML_INCLUDES=-I $(CAMLMSAT_DIR)
#OCAML_INCLUDES=-I $(CAMLMSAT_DIR) -I $(CAMLENV_DIR)

include $(CONFIG_SRC_HOME)/rules.make


C_WRAPPER=$(CONFIG_SRC_HOME)/config/c_wrapper

OCAML_LIBS= bigarray.cma str.cma unix.cma
OCAML_OPT_LIBS= bigarray.cmxa str.cmxa unix.cmxa

OCAMLMSAT_DEPS=$(CAMLMSAT_DIR)/libcamlmsat.a $(CAMLMSAT_DIR)/predicates.cmo
OCAMLMSAT_OPT_DEPS=$(CAMLMSAT_DIR)/libcamlmsat.a $(CAMLMSAT_DIR)/predicates.cmx

#OCAMLENV_LIBS=$(CAMLENV_DIR)/fileutils.cma $(CAMLENV_DIR)/camomile.cma $(CAMLENV_DIR)/gettextBase.cma $(CAMLENV_DIR)/gettextExtension.cma $(CAMLENV_DIR)/gettextCamomile.cma
#OCAMLENV_OPT_LIBS=$(CAMLENV_DIR)/fileutils.cmxa $(CAMLENV_DIR)/camomile.cmxa $(CAMLENV_DIR)/gettextBase.cmxa $(CAMLENV_DIR)/gettextExtension.cmxa $(CAMLENV_DIR)/gettextCamomile.cmxa
# To compile/link without gettext
OCAMLENV_LIBS=
OCAMLENV_OPT_LIBS=

DEBUG_DEPS= misc.cmo bidirectionalLabeledGraph.cmo logging.cmo \
  resources.cmo json.cmo utils.cmo resource_pp.cmo parser.cmo lexer.cmo \
  templates.cmo parse_rdef.cmo parse_resource.cmo generate.cmo cInterface.cmo \
  main.cmo

OPT_DEPS= misc.cmx bidirectionalLabeledGraph.cmx logging.cmx \
  resources.cmx json.cmx utils.cmx resource_pp.cmx parser.cmx lexer.cmx \
  templates.cmx parse_rdef.cmx parse_resource.cmx generate.cmx cInterface.cmx \
  main.cmx

# JF 6/22/2009: For now, need to build opt before debug because the c_wrapper files
# depend on opt
all: opt debug

help:
	@echo "targets are: debug opt all clean help"

debug: configurator.dbg lib
	cd $(C_WRAPPER); make debug

lib: cfunctions.o
	$(OCAML_MKLIB) -verbose -o config $(OCAML_LIBS) $(OCAMLENV_LIBS) $(OCAML_MSAT_DEPS)\
		$(OPT_DEPS) cfunctions.o

ifeq ($(ENGAGE_PLATFORM),linux64)
  EXTRA_LINK_OPTS=-fPIC
else
  EXTRA_LINK_OPTS=
endif

cfunctions.o: cfunctions.h cfunctions.c
	gcc -I $(OCAML_LIBDIR) $(EXTRA_LINK_OPTS) -g -c cfunctions.c

opt: configurator.opt lib
	cd $(C_WRAPPER); make opt

configurator.dbg: $(OPT_CMIS) $(DEBUG_DEPS) $(OCAMLMSAT_DEPS) cfunctions.o
	$(OCAML_C) $(OCAML_C_FLAGS) -custom -cc g++ \
 -o configurator.dbg $(OCAML_LIBS)  $(OCAMLENV_LIBS) $(OCAMLMSAT_DEPS) $(DEBUG_DEPS) cfunctions.o

$(CAMLMSAT_DIR)/libcamlmsat.a:
	cd $(CAMLMSAT_DIR); make libcamlmsat.a

$(CAMLMSAT_DIR)/predicates.cmx:
	cd $(CAMLMSAT_DIR); make predicates.cmx

$(CAMLMSAT_DIR)/predicates.cmo:
	cd $(CAMLMSAT_DIR); make predicates.cmo

configurator.opt: $(OPT_CMIS) $(OPT_DEPS) $(OCAMLMSAT_OPT_DEPS) cfunctions.o
	$(OCAML_OPT_C) $(OCAML_C_OPT_FLAGS) -cc g++ -o configurator.opt $(OCAML_OPT_LIBS) $(OCAMLENV_OPT_LIBS) $(OCAMLMSAT_OPT_DEPS) $(OPT_DEPS) cfunctions.o

lexer.ml: lexer.mll resources.ml
	$(OCAML_LEX) lexer.mll

cInterface.cmx: generate.cmx

generate.cmo: generate.cmi

generate.cmx: generate.cmi

main.cmx: generate.cmx

parser.ml: parser.cmi

parser.mli: parser.mly lexer.ml resources.cmo
	$(OCAML_YACC) parser.mly

clean:
	rm -f *.orig
	rm -f *.cmo *.cmi *.cmx *.o parser.ml parser.mli lexer.ml \
           configurator.dbg configurator.opt *~
	rm -f *.a *.cmxa *.cma *.so
	cd $(C_WRAPPER); make clean

.PHONY: clean all unitest help debug opt
