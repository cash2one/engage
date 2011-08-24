#ifndef CONFIGCINTERFACE_H
#define CONFIGCINTERFACE_H

#ifdef __cplusplus
extern "C" {
#endif

#define STATUS_OK 0
#define STATUS_ERROR -1

#define IN
#define OUT
/** Protocol for interacting with the config engine:

  b = init();
  if (!b) {
	error has occurred
  }
  while (has_next()) {
    next();
    s = get_config_ports_as_string();
    s' = get values from GUI
    set_config_ports_from_string(s');
    set_ports();
  }
*/

  extern int config_init (IN char *rdeffname, IN char *rinstfname, OUT char **error);

  extern int config_has_next();
  extern int config_has_prev();
  extern int config_next();
  extern int config_prev();

  extern void config_reinit();

  extern char * config_get_config_port_types_as_string (IN char **errorstr);
  extern char * config_get_config_ports_as_string (IN char **errorstr);

  extern void config_set_config_ports_from_string (IN char *cp);

  extern void config_set_ports(IN char *key, IN char *id);
  extern void config_set_ports_of_current();

  extern int config_write_install_file(IN char *fname, OUT char **error);

  extern char *config_get_resource(IN char *key, IN char *id);
  extern char *config_get_current_resource();

  extern void register_logger(void (*logger)(char *, char *, int, char *));

#ifdef __cplusplus
}
#endif

#endif /* MLINTERFACE_H */
