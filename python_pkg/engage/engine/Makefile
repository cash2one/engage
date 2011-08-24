# The GENFORMA_CODE_HOME  variable points to the top of the "code" repository.
ifndef GENFORMA_CODE_HOME
GENFORMA_CODE_HOME=$(shell cd ../..; pwd)
export GENFORMA_CODE_HOME
endif

# name of the platform: macosx, linux, or cygwin
ifndef GENFORMA_PLATFORM
GENFORMA_PLATFORM=$(shell $(GENFORMA_CODE_HOME)/buildutils/get_platform.sh)
export GENFORMA_PLATFORM
endif


all: unittest

unittest:
	@python resource_metadata.py
	@python json_metadata_utils.py
	@python library.py
	@rm -f test.log
	python install_engine.py -s --log DEBUG -f ./test.log test-$(GENFORMA_PLATFORM).json ../../test/install/resource_library.json

clean:
	rm -f *.pyc *~ installer.error test.log

.PHONY: all unittest clean
