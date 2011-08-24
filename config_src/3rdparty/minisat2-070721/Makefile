#
# This Makefile was not part of the original minisat distribution. Added to support
# the Genforma build environment.

all: core/Solver.o

debug: core/Solver.o

opt: core/Solver.o

core/Solver.o:
	cd core; make

clean:
	cd core; make clean

.PHONY: all clean debug opt