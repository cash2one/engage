#
# This makefile has been modified to work in the Genforma build environment.
# See Makefile.orig for the original makefile.

ifndef ENGAGE_CODE_HOME
ENGAGE_CODE_HOME=$(shell cd ../../..; pwd)
export ENGAGE_CODE_HOME
endif

CONFIG_SRC_HOME=$(ENGAGE_CODE_HOME)/config_src

include $(CONFIG_SRC_HOME)/config.make
include $(CONFIG_SRC_HOME)/rules.make


#OCAML_STD_LIB=$(shell sh ./ocamllibdir.sh)


MINISAT_INC=-I $(MINISAT_DIR)/mtl -I $(MINISAT_DIR)/core
MINISAT_OBJ=$(MINISAT_DIR)/core/Solver.o


CAMLMSAT_DEPS=libcamlmsat.a camlmsat.cmi

# We always build the C++ libraries optimzed.  If you run into a low-level problem,
# you might try using CC_OPTS instead.
CC_OPTS=-ffloat-store -g
CC_OPT_OPTS=-ffloat-store -O3


# unit test executables
# do we need to define $(EXE) to be .exe on cygwin?
TEST_STUBS=test_stubs$(EXE)
TEST_PREDS=test_preds$(EXE)
TEST_STUBS_OPT=test_stubs.opt$(EXE)
TEST_PREDS_OPT=test_preds.opt$(EXE)
TEST_TOPLEVEL=test_toplevel$(EXE)


all: debug opt

debug: $(CAMLMSAT_DEPS) predicates.cmo $(TEST_STUBS) $(TEST_PREDS) $(TEST_TOPLEVEL)
	./$(TEST_STUBS)
	./$(TEST_PREDS)

opt: $(CAMLMSAT_DEPS) predicates.cmx $(TEST_STUBS_OPT) $(TEST_PREDS_OPT)
	./$(TEST_STUBS_OPT)
	./$(TEST_PREDS_OPT)

# The output of this program can be piped to the Simplify theorem prover.
# All the predicates should be valid.
$(TEST_PREDS_OPT): test_preds.ml predicates.cmi predicates.cmx $(CAMLMSAT_DEPS)
	$(OCAML_OPT_C) $(OCAML_OPT_C_FLAGS) -cc g++ libcamlmsat.a predicates.cmx test_preds.ml -o $(TEST_PREDS_OPT)

# The output of this program can be piped to the Simplify theorem prover.
# All the predicates should be valid.
$(TEST_PREDS): test_preds.ml predicates.cmi predicates.cmo $(CAMLMSAT_DEPS)
	$(OCAML_C) $(OCAML_C_FLAGS) -custom  -cc g++ libcamlmsat.a predicates.cmo test_preds.ml -o $(TEST_PREDS)

predicates.cmx: predicates.ml predicates.cmi

predicates.cmo: predicates.ml predicates.cmi

predicates.cmi: predicates.mli camlmsat.cmi

# toplevel for interactive debugging of the predicates API
$(TEST_TOPLEVEL): predicates.cmi predicates.cmo
	$(OCAML_MKTOP) -o $(TEST_TOPLEVEL) $(CAML_C_FLAGS)  -custom  -cc g++ libcamlmsat.a predicates.cmo

$(TEST_STUBS_OPT): $(CAMLMSAT_DEPS) test_stubs.ml
	$(OCAML_OPT_C) $(OCAML_OPT_C_FLAGS) -cc g++ -o $(TEST_STUBS_OPT) libcamlmsat.a test_stubs.ml

$(TEST_STUBS): $(CAMLMSAT_DEPS) test_stubs.ml
	$(OCAML_C) $(OCAML_C_FLAGS) -custom  -cc g++ -o $(TEST_STUBS) libcamlmsat.a test_stubs.ml

libcamlmsat.a: camlmsat_stubs.o $(MINISAT_OBJ)
	ar cr libcamlmsat.a camlmsat_stubs.o $(MINISAT_OBJ)
	ranlib libcamlmsat.a

camlmsat_stubs.o: camlmsat_stubs.C $(MINISAT_OBJ)
	g++ -c $(CC_OPT_OPTS) $(MINISAT_INC) -I $(OCAML_LIBDIR) camlmsat_stubs.C

$(MINISAT_OBJ):
	@echo "Making MiniSat"
	cd $(MINISAT_DIR)/core; make

clean:
	rm -f *~ $(TEST_STUBS) $(TEST_PREDS) *.o *.a *.cmi *.cmo *.cmx libcamlmsat.a \
           $(TEST_TOPLEVEL) $(TEST_STUBS_OPT) $(TEST_PREDS_OPT)

.PHONY: all debug opt clean
