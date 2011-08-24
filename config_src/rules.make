%.cmo: %.ml
	$(OCAML_C) $(OCAML_C_FLAGS) $(OCAML_INCLUDES) -c $< -o $@

%.cmx: %.ml
	$(OCAML_OPT_C) $(OCAML_OPT_C_FLAGS) $(OCAML_INCLUDES) -c $< -o $@

%.cmi: %.mli
	$(OCAML_C) $(OCAML_C_FLAGS) $(OCAML_INCLUDES) -c $< -o $@
