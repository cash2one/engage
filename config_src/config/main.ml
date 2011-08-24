(* Copyright 2009 by Genforma. All Rights Reserved. *)
(** Main program for configurator *)


open Resources
open Logging


let usage_msg = "configurator {optional flags} <resource library file> <install spec file> "
let rdef_fname = ref ""
let spec_fname = ref ""

let pretty_print_only = ref false

let arg_specs =
  [("--verbose", Arg.Unit (fun () -> Logging.set_log_level Logging.LogInfo),
    s_ "Print out informational messages");
   ("--debug", Arg.Unit (fun () -> Logging.set_log_level Logging.LogDebug),
    s_ "Print out debugging information");
   ("--detail", Arg.Unit (fun () -> Logging.set_log_level Logging.LogJunk),
    s_ "Print out detailed debugging information");
   ("--pp", Arg.Set pretty_print_only, s_ "Just validate and pretty-print the input files, then exit.") ]



let main () =
  let args_read = ref 0 in
  let gettext_args, _ = [], [] (* NO GETTEXT Gettext.init *) in
    Arg.parse (arg_specs @ gettext_args)
      (fun arg ->
         args_read := !args_read + 1;
         match !args_read with
             1 -> rdef_fname := arg
           | 2 -> spec_fname := arg
           | _ -> raise (Arg.Bad "Too many arguments, expecting two."))
      usage_msg;
    if (!args_read)<2 then begin
      print_endline (s_ "Please specify resource library and install spec files.") ;
      Arg.usage arg_specs usage_msg;
      exit 1
    end;

  log_debug Prs ("Parsing resource library file " ^ !rdef_fname);
  let rdef_list = Generate.read_rdefs_from_file !rdef_fname in
  log_debug Prs "Resource library file parsed successfully";
  log_debug Prs ("Parsing install spec file " ^ !spec_fname);
  let install_spec = Generate.read_install_spec_from_file !spec_fname in
  log_debug Prs ("Install spec file parsed successfully");

  if !pretty_print_only then begin
    (* Just pretty print our input files and exit *)
    print_endline "================ Resource Library ================";
    Resource_pp.pp_resource_library rdef_list
      (Resource_pp.make_pp_state print_string);
    print_endline "================ Install Spec ================";
    Resource_pp.pp_resource_inst_list install_spec
      (Resource_pp.make_pp_state print_string);
    print_endline "================ End of Intall Spec ================";
    exit 0
  end
  else begin
    Generate.generate rdef_list install_spec
  end




let _ = main ()
;;
