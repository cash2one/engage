open Generate
module L = Logging
module R_pp = Resource_pp

exception GUIUserError of string
exception GUISystemError of string

let config_obj = ref None

let write_user_error_to_file (l: L.log_area) (e: int) (u: string) (d: string) (c: L.context) (fname :string) :unit =
  let fp = open_out fname in
  let print_to_file fp s =
    Printf.fprintf fp "%s" s
  in
  let pp_state = R_pp.make_pp_state (print_to_file fp) and
      (u:string) = Misc.replace_string "\"" "'" u and
      (d:string) = Misc.replace_string "\"" "'" d in
    (R_pp.pp_user_error (l,e,u,d,c) pp_state);
    close_out fp

let wrap f =
  try f () 
  with (L.UserError (a,b,c,d,e)) ->
    L.log_error L.ConsGen "Error raised in processing install spec:";
    let exstring = ref "" in
      (R_pp.pp_user_error (a,b,c,d,e) (R_pp.make_pp_state (R_pp.output_to_str exstring)) ) ;
      write_user_error_to_file a b c d e "config_error.json" ;
      raise (GUIUserError !exstring)
  | ex ->
    let  exstring = Printexc.to_string ex in begin
        L.log_error L.ConsGen ("Exception raised in OCAML code:: " ^ exstring);
        flush stdout ;
        write_user_error_to_file L.ConsGen (-1) ("Unexpected system error::" ^ exstring) "" [] "config_error.json" ;
        let exs = ref "" in
            (R_pp.pp_user_error (L.ConsGen,-1,"Unexpected system error",exstring,[]) 
               (R_pp.make_pp_state (R_pp.output_to_str exs)) ) ;
            raise (GUISystemError !exs)
      end


let config_init rdef_fname install_fname =
  let f () = 
    let rdef_list = Generate.read_rdefs_from_file rdef_fname in
    let install_spec = Generate.read_install_spec_from_file install_fname in
    let (pmodel, node_id_tbl, id_node_tbl, topo_list) = Generate.generate rdef_list install_spec in
    let o = new Generate.config_engine_factory pmodel id_node_tbl node_id_tbl topo_list in
    config_obj := Some o
  in
  wrap f

let get_config_obj () =
  let f () = 
    match !config_obj with
    | None -> failwith "config_obj is not set"
    | Some o -> o
  in
  wrap f

let has_next () =
  let f () = 
    let o = get_config_obj () in
    o#has_next ()
  in
  wrap f

let has_prev () =
  let f () = 
    let o = get_config_obj () in
    o#has_prev ()
  in
  wrap f

let reinit () =
  let f () = 
    let o = get_config_obj () in
    o#reinit ()
  in
  wrap f

let next () =
  let f () = 
    let o = get_config_obj () in
    o#next ()
  in
  wrap f

let prev () =
  let f () = 
    let o = get_config_obj () in
    o#prev ()
  in
  wrap f

let get_config_port_types_as_string () =
  let f () = 
    let o = get_config_obj () in
    o#get_config_port_types_as_string ()
  in
  wrap f

let get_config_ports_as_string () =
  let f () = 
    let o = get_config_obj () in
    o#get_config_ports_as_string ()
  in
  wrap f

let set_config_ports_from_string s =
  let f () = 
    let o = get_config_obj () in
    o#set_config_ports_from_string s
  in 
  wrap f

let set_ports s s' =
  let f () = 
    let o = get_config_obj () in
    o#set_ports s s'
  in
  wrap f

let set_ports_of_current ()  =
  let f () = 
    let o = get_config_obj () in
    o#set_ports_of_current ()
  in
  wrap f

let get_resource s s' =
  let f () = 
    let o = get_config_obj () in
    o#get_resource s s'
  in
  wrap f

let get_current_resource () =
  let f () = 
    let o = get_config_obj () in
    o#get_current_resource ()
  in
  wrap f

let write_install_file fname =
  let f () = 
    let o = get_config_obj () in
    o#write_install_file fname
  in
  wrap f


(* Interface to C *)
let setup_callbacks () =
  Callback.register "config_init" config_init ;
  Callback.register "config_has_next" has_next ;
  Callback.register "config_has_prev" has_prev ;
  Callback.register "config_next" next ;
  Callback.register "config_prev" prev ;
  Callback.register "config_reinit" reinit ;
  Callback.register "config_get_config_ports" get_config_ports_as_string ;
  Callback.register "config_get_config_port_types" get_config_port_types_as_string ;
  Callback.register "config_set_config_ports" set_config_ports_from_string ;
  Callback.register "config_set_ports" set_ports ;
  Callback.register "config_set_ports_of_current" set_ports_of_current ;
  Callback.register "config_get_resource" get_resource ;
  Callback.register "config_get_current_resource" get_current_resource ;
  Callback.register "config_write_install_file" write_install_file ;
  Callback.register_exception "config_user_error" (GUIUserError "") ;
  Callback.register_exception "config_sys_error" (GUISystemError "") ;
  ()

let _ =
  L.log_always L.ConsGen "Setting up CAML callbacks\n";
  setup_callbacks (); 
  L.log_always L.ConsGen "Done\n";
