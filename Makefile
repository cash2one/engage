# main makefile for engage
SHELL=/bin/bash

ifndef ENGAGE_CODE_HOME
ENGAGE_CODE_HOME=$(shell pwd)
export ENGAGE_CODE_HOME
endif
all: config-engine download-packages

help:
	@echo "targets are all config-engine download-packages test docs clean clean-all"

config-engine:
	cd $(ENGAGE_CODE_HOME)/config_src; make all


download-packages:
	mkdir -p $(ENGAGE_CODE_HOME)/sw_packages
	$(ENGAGE_CODE_HOME)/buildutils/pkgmgr.py -t $(ENGAGE_CODE_HOME)/sw_packages -p $(ENGAGE_CODE_HOME)/buildutils/packages.json group Engage Engage-public
	if [ -f $(ENGAGE_CODE_HOME)/../engage-utils/setup.py ]; then UTILS_HOME=$(ENGAGE_CODE_HOME)/../engage-utils; else if [ -f $(ENGAGE_CODE_HOME)/../../../engage-utils/setup.py ]; then UTILS_HOME=$(ENGAGE_CODE_HOME)/../../../engage-utils; fi; fi; if [[ "$$UTILS_HOME" != "" ]]; then echo "Found engage-utils at $$UTILS_HOME"; cd $$UTILS_HOME; python setup.py sdist; cp dist/engage_utils*.tar.gz $(ENGAGE_CODE_HOME)/sw_packages; else echo "Did not find engage-utils package, deployments will have to download directly from github"; fi


test: config-engine download-packages
	rm -rf $(ENGAGE_CODE_HOME)/test_output
	mkdir $(ENGAGE_CODE_HOME)/test_output
	cd $(ENGAGE_CODE_HOME)/buildutils; python test_engage.py

$(ENGAGE_CODE_HOME)/disthome_for_docs: config-engine download-packages
	cd $(ENGAGE_CODE_HOME); ./bootstrap.py $(ENGAGE_CODE_HOME)/disthome_for_docs
	$(ENGAGE_CODE_HOME)/disthome_for_docs/engage/bin/pip install -I sphinx

docs: $(ENGAGE_CODE_HOME)/disthome_for_docs
	@if [[ `which sphinx-build` == "" ]]; then echo "Need to install Sphinx before building docs"; exit 1; fi
	export PATH=$(ENGAGE_CODE_HOME)/disthome_for_docs/engage/bin:$$PATH; echo `which python`; cd $(ENGAGE_CODE_HOME)/docs/users_guide; make html
	export PATH=$(ENGAGE_CODE_HOME)/disthome_for_docs/engage/bin:$$PATH; cd $(ENGAGE_CODE_HOME)/docs/dev_guide; make html
	rm -rf $(ENGAGE_CODE_HOME)/disthome_for_docs # don't leave it around afterward

clean:
	cd $(ENGAGE_CODE_HOME)/config_src; make clean
	rm -rf $(ENGAGE_CODE_HOME)/test_output
	cd $(ENGAGE_CODE_HOME)/docs/users_guide; make clean
	cd $(ENGAGE_CODE_HOME)/docs/dev_guide; make clean
	cd $(ENGAGE_CODE_HOME)/python_pkg; rm -rf ./build ./dist ./engage.egg-info
	rm -rf $(ENGAGE_CODE_HOME)/disthome_for_docs


# The clean-all target also deletes the downloaded packages
clean-all: clean
	rm -rf $(ENGAGE_CODE_HOME)/sw_packages

.PHONY: all config-engine clean clean-all download-packages docs help test
