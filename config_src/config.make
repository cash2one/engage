
# ocaml definitions
OCAML_C=ocamlc
OCAML_C_FLAGS=-g

OCAML_OPT_C=ocamlopt
OCAML_OPT_C_FLAGS=

OCAML_INCLUDES=
OCAML_LEX=ocamllex
OCAML_YACC=ocamlyacc
OCAML_MKTOP=ocamlmktop
OCAML_MKLIB=ocamlmklib

#ocaml library
OCAML_LIBDIR= $(shell $(OCAML_C) -v | tail -1 | sed -e \
		's/^Standard library directory: //')

# 3rd pary libraries
#CAMLENV_DIR=$(GENFORMA_ENV_HOME)/lib/ocaml


MINISAT_DIR=$(CONFIG_SRC_HOME)/3rdparty/minisat2-070721
CAMLMSAT_DIR=$(CONFIG_SRC_HOME)/3rdparty/camlmsat

ENGAGE_PLATFORM=$(shell $(ENGAGE_CODE_HOME)/buildutils/get_platform.sh)