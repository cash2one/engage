"""Interface to the ocaml configuration engine.
"""
import os.path
import json

# fix path if necessary (if running from source or running as test)
import fixup_python_path

import engage_utils.process as procutils
import preprocess_resources
from engage.utils.user_error import UserError, EngageErrInf, convert_exc_to_user_error, UserErrorParseExc, parse_user_error, AREA_CONFIG

from engage.utils.log_setup import setup_engine_logger
logger = setup_engine_logger(__name__)

def get_config_error_file(installer_file_layout):
    return os.path.join(os.path.dirname(
                          installer_file_layout.get_install_script_file()),
                            "config_error.json")
    

def run_config_engine(installer_file_layout, install_spec_file):
    ifl = installer_file_layout
    config_error_file = get_config_error_file(installer_file_layout)
    preprocess_resources.validate_install_spec(install_spec_file)
    install_script_file = ifl.get_install_script_file()
    if os.path.exists(install_script_file):
        logger.debug("moving old %s to %s before running config engine" %
                     (install_script_file, install_script_file + ".prev"))
        os.rename(install_script_file, install_script_file + ".prev")
    # we run the config engine from the same directory as where we want
    # the install script file, as it write the file to the current
    # directory.
    rc = procutils.run_and_log_program([ifl.get_configurator_exe(),
                                           ifl.get_preprocessed_resource_file(),
                                           install_spec_file], None, logger,
                                          cwd=os.path.dirname(install_script_file))
    if rc != 0:
        logger.error("Config engine returned %d" % rc)
        if os.path.exists(config_error_file):
            # if the config engine wrote an error file, we parse that
            # error and raise it.
            try:
                with open(config_error_file, "rb") as f:
                    ue = parse_user_error(json.load(f),
                                          component=AREA_CONFIG)
                raise ue
            except UserErrorParseExc, e:
                logger.exception("Unable to parse user error file %s" %
                                 config_error_file)
        raise Exception("Configuration engine returned an error")
    if not os.path.exists(install_script_file):
        raise Exception("Configuration engine must have encountered a problem: install script %s was not generated" % install_script_file)


def preprocess_and_run_config_engine(installer_file_layout, install_spec_file):
    ifl = installer_file_layout
    preprocess_resources.preprocess_resource_file(
        ifl.get_resource_def_file(),
        ifl.get_extension_resource_files(),
        ifl.get_preprocessed_resource_file(),
        logger)
    run_config_engine(ifl, install_spec_file)
    logger.info("Configuration successful.")
    
