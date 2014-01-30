(** Copyright 2009 Genforma Inc. All rights reserved. *)
module L = Logging

module R = Resources
module R_pp = Resource_pp
module G = BidirectionalLabeledGraph
module P = Predicates

let s_ = L.s_
let f_ = L.f_
let sn_ = L.sn_
let fn_ = L.fn_

(* gettext *)
let s_ x = x

class ['a] inst_iterator (nl : 'a list) =
  object (self)

  val mutable leftlist = []
  val mutable rightlist = nl

  method has_next () = not (rightlist = [])
  method has_prev () = not (leftlist = [])

  method next () =
    match rightlist with
    | [] -> raise Not_found
    | a :: rest -> (rightlist <- rest ; leftlist <- a :: leftlist; a)

  method prev () =
    match leftlist with
    | [] -> raise Not_found
    | a :: rest -> (rightlist <- a :: rightlist ; leftlist <- rest; a)

end

let debug_rdef rdef =
  let sref = ref "" in
  R_pp.pp_resource_def rdef (R_pp.make_pp_state (R_pp.output_to_str sref));
  L.log_debug L.ConsGen ("Printing rdef::\n" ^ !sref)

let debug_inst rinst =
  let sref = ref "" in
  R_pp.pp_resource_inst rinst (R_pp.make_pp_state (R_pp.output_to_str sref));
  L.log_debug L.ConsGen ("Printing rinst::\n" ^ !sref)

let rec matches key constraint_list =
  let _match_worker (s, sv) key what =
    begin
      try
	let v = List.assoc s key in
	match what with
	  0 -> v = sv
	| 1 -> R.scalar_gt v sv
	| 2 -> R.scalar_geq v sv
	| 3 -> R.scalar_lt v sv
	| 4 -> R.scalar_leq v sv
	| _ -> assert (false)
      with Not_found -> false
    end	
  in
  match constraint_list with
    [] -> true
  | thiscon :: rest ->
      begin
	let thismatch =
	  match thiscon with
	  | R.KeyEq  (s, sv) -> _match_worker (s,sv) key 0
	  | R.KeyGt  (s, sv) -> _match_worker (s,sv) key 1
	  | R.KeyGeq (s, sv) -> _match_worker (s,sv) key 2
	  | R.KeyLt  (s, sv) -> _match_worker (s,sv) key 3
	  | R.KeyLeq (s, sv) -> _match_worker (s,sv) key 4
	in
	if thismatch then matches key rest else false
      end

let port_reference_of_string s =
  let strings = Misc.chop s "\." in
  match strings with
  | "config_port" :: rest -> R.ConfigPortRef rest
  | "input_ports" :: ip :: rest -> R.InputPortRef (ip, rest)
  | _ -> failwith ("Template string " ^s)
	
let json_of_key k =
  let jmap = List.fold_left (fun current_map (s,sv) -> R.SymbolMap.add s (R.JsonScalar sv) current_map) R.SymbolMap.empty k in
  R.JsonMap jmap

let rec json_of_type_decl t =
  match t with
  | R.ScalarType s -> R.JsonScalar (R.String s)
  | R.EnumType l -> 
    R.JsonMap 
      (R.SymbolMap.add "enum" 
                       (R.JsonList (List.map (fun s -> R.JsonScalar (R.String s)) l)) R.SymbolMap.empty)
  | R.ListType tl ->
    let jtl = json_of_type_decl tl in
    R.JsonList [jtl]
  | R.MapType s_tdcl_list ->
    R.JsonMap (List.fold_left (fun current_map (s,tdcl) ->
                R.SymbolMap.add s (json_of_type_decl tdcl) current_map
                ) R.SymbolMap.empty s_tdcl_list
              )
(******************************************************************************)

(** Database to insert/look up/print resource instances *)
let add_inst, lookup_inst, iter_inst, print_inst, lookup_instance_with_key, get_machine =
  let inst_ht = Hashtbl.create 29 in
  let _addfun = (fun i -> Hashtbl.replace inst_ht (i.R.resource_key, i.R.id) i) in
  let rec _lookupfun = (fun (key,id) ->
    try Hashtbl.find inst_ht (key,id)
    with Not_found ->
      L.log_always L.ConsGen ("Instance corresponding to following key not found in install database::");
      L.log_always L.ConsGen ("Id = " ^ id ^ " , Key = ");
      R_pp.pp_key key (R_pp.make_pp_state L.system_print_string) ; flush stdout ;
      L.log_info  L.ConsGen ("lookup_inst raises Not_found with key::");
      raise Not_found)
  and _get_machine instance =
    match instance.R.inside_ref with
    | None -> instance
    | Some res_ref -> _get_machine (_lookupfun (res_ref.R.ref_key, res_ref.R.ref_id))
  in
  let _iterfun = (fun f -> Hashtbl.iter f inst_ht) in
  let _printfun = fun () ->
    L.log_info L.ConsGen "\n========================================\n";
    L.log_info L.ConsGen "Printing install spec:\n";
    let pp_state = R_pp.make_pp_state L.system_print_string in
    Hashtbl.iter (fun (key,id) data -> 
      L.log_info L.ConsGen ("Id = " ^ id ^ ", key = " ) ; 
      R_pp.pp_key key pp_state; 
      L.system_print_string "\n"; 
      R_pp.pp_resource_inst data pp_state; 
      L.system_print_string "\n" ) inst_ht ;
    L.log_info L.ConsGen "========================================\n\n";
  in
  let _lookup_instance_with_key key machine =
    Hashtbl.fold (fun (k,i) d sofar ->
      let mc = _get_machine d in
      if k = key && mc.R.resource_key = fst machine && mc.R.id = snd machine then
          d :: sofar
      else sofar 
      ) inst_ht []
  in
  (_addfun, _lookupfun, _iterfun, _printfun, _lookup_instance_with_key, _get_machine)

let mk_inst_database ilist =
  List.iter (fun i -> add_inst i) ilist

(** Database for resource definitions *)
let add_rdef, lookup_rdef, iter_rdef, filter_rdef, print_rdef =
  let rdef_ht = Hashtbl.create 29 in
  let _addfun = (fun rd -> Hashtbl.add rdef_ht rd.R.key rd) in
  let _lookupfun = (fun key ->
    try Hashtbl.find rdef_ht key
    with Not_found ->
      L.log_always L.ConsGen ("Resource corresponding to following key not found in resource library::");
      R_pp.pp_key key (R_pp.make_pp_state L.system_print_string) ; flush stdout ;
      L.log_info L.ConsGen ("lookup_rdef raises Not_found with key");
      raise Not_found)
  in
  let _iterfun = (fun f -> Hashtbl.iter f rdef_ht) in
  let _filterfun = fun boolfun ->
    Hashtbl.fold (fun k d s ->
      if boolfun k d then d :: s else s) rdef_ht []
  in
  let _printfun = fun () ->
    L.log_info L.ConsGen "\n========================================\n";
    let pp_state = R_pp.make_pp_state L.system_print_string in
    Hashtbl.iter (fun key data -> L.log_info L.ConsGen "Key = "; R_pp.pp_key key pp_state ; L.system_print_string "\n" ;
      R_pp.pp_resource_def data pp_state; L.system_print_string "\n" ) rdef_ht ;
    L.log_info L.ConsGen "\n========================================\n\n";
  in
  (_addfun, _lookupfun, _iterfun, _filterfun, _printfun)

let mk_rdef_database rlist =
  List.iter (fun r -> add_rdef r) rlist


let reset_id, make_id, is_tmp_id =
  let tmp_prefix = "__" (*"__GF_inst_"*) in
  let id = ref (-1) in
  let _reset () = id := 0 in
  let _make = fun key ->
    incr id ;
    let kstr = R_pp.format_key_for_resource_id key in
    tmp_prefix ^ kstr ^ "__" ^ (string_of_int !id)
  in
  let _is_tmp_id id =
    Misc.is_prefix tmp_prefix id
  in
  (_reset, _make, _is_tmp_id)
 
let make_new_tmp_inst key rdef (mk,mid) =
  let id = make_id key in
  let inside_ref = match rdef.R.inside with None -> None
                   | Some cc -> Some { R.ref_id = mid ;
                     R.ref_key = mk ;
                     R.ref_port_mapping = R.SymbolMap.empty 
                   } 
  in
  let inst = { R.id = id ;
    R.resource_key = key ;
    R.properties = None ; 
    R.config_port = R.SymbolMap.empty ;
    R.input_ports = R.SymbolMap.empty ;
    R.output_ports = R.SymbolMap.empty ;
    R.inside_ref = None ; (* inside_ref ; *)
    R.environment_refs = [] ;
    R.peer_refs = [] ;
    R.user_data = R.SymbolMap.empty ;
  }
  in
  add_inst inst ;
  inst


let reset_includes_list, add_includes_list, iter_includes_list, fold_left_includes_list, map_includes_list, debug_get_includes_list = 
  let includes_list = ref [] in
  let f_reset () = L.log_debug L.ConsGen ("Reset includes list"); includes_list := [] in
  let f_add (k, rinst, reskey, resid, propname, p) = includes_list := (k, rinst, reskey, resid, propname, p):: !includes_list in
  let f_iter f = List.iter f !includes_list in
  let f_fold_left f init = List.fold_left f init !includes_list in
  let f_map f = List.map f !includes_list in
  (f_reset, f_add, f_iter, f_fold_left, f_map, fun () -> !includes_list) 

(******************************************************************************)
(* Functions to type check resource definitions and resource instances *)
(* PRE: The resource and instance databases have been created *)

(* CHECK: foreach key in resource instance, there is a resource definition with the same key *)
let check_instance_key_exists_in_rdef () =
    iter_inst (fun (k,id) d ->
      try ignore (lookup_rdef k)
      with Not_found ->
	let errorcode = L.mTYPECHECK in
	let sref = ref "" in
	let _ =
	  R_pp.pp_key k (R_pp.make_pp_state (R_pp.output_to_str sref))
	in
	let user_errormsg =
	  s_ ("Install key not found in resource database: " ^ !sref)
	in
	let dev_errormsg =
	  s_ ("Typecheck failed in check_instance_key_exists_in_rdef")
	in
	raise (L.UserError (L.ConsGen, errorcode, user_errormsg, dev_errormsg, [])) )


(* CHECK: every port name mentioned in a port_def is actually present *)
let check_ports_exist_in_rdef () =
  let rec check_list slist piv =
    match slist with
      [] -> ()
    | s :: rest ->
	begin
	  match piv with
	  | R.MapInitialVal sivlist ->
	      begin
		try
		  let (s', iv') = List.find (fun (sym,iv) -> s = sym) sivlist
		  in
		  check_list rest iv'
		with Not_found -> assert false
	      end
	  | _ -> assert false
	end
  in
  let rec check_port_reference pref rdef =
    let _worker slist portdefs =
      match slist with
	[] -> ()
      | s :: rest ->
	  try
	    let pdef = List.find (fun p -> s = p.R.property_name) portdefs
	    in
	    match pdef.R.property_val with
	    | R.NoInitialVal -> if rest = [] then () else assert false
	    | R.Default iv -> check_list rest iv
	    | R.Fixed iv -> check_list rest iv
	    | R.Includes iv -> check_list rest iv
	  with Not_found ->
	    raise (L.UserError (L.ConsGen, L.mTYPECHECK, s^" not found", "", []))
    in
    match pref with
      R.ConfigPortRef slist ->
	begin
	  _worker slist rdef.R.config_port_def
	end
    | R.InputPortRef (i, ilist) ->
	begin
	  try
	    let pdeflist = R.SymbolMap.find i rdef.R.input_port_defs in
	    _worker ilist pdeflist
	  with Not_found ->
	    let keyref = ref "" in
	    R_pp.pp_key rdef.R.key (R_pp.make_pp_state (R_pp.output_to_str keyref));
	    raise (L.UserError (L.ConsGen, L.mTYPECHECK, i^" not found in input ports of "^ !keyref, "", []))
	end
  in
  let rec check_initial_val ival rdef =
    match ival with
    | R.ScalarInitialVal _ -> ()
    | R.PortReference pref ->
	check_port_reference pref rdef
    | R.MapInitialVal l ->
	List.iter (fun (s, iv) -> check_initial_val iv rdef) l
    | R.ListInitialVal l ->
	List.iter (fun iv -> check_initial_val iv rdef) l
    | R.TemplateInitialVal (s , slist) ->
        let plist = List.map port_reference_of_string slist in
        List.iter (fun p -> check_port_reference p rdef) plist
  in
  let check_property_def pdef rdef =
    match pdef.R.property_val with
      R.NoInitialVal -> ()
    | R.Default ival -> check_initial_val ival rdef
    | R.Fixed ival -> check_initial_val ival rdef
    | R.Includes ival -> check_initial_val ival rdef
  in
  iter_rdef
    (fun key resdef ->
      List.iter (fun pdef -> check_property_def pdef resdef) resdef.R.config_port_def ;
      R.SymbolMap.iter (fun key pdeflist ->
	List.iter (fun pdef -> check_property_def pdef resdef) pdeflist) resdef.R.input_port_defs ;
      R.SymbolMap.iter (fun key pdeflist ->
	List.iter (fun pdef -> check_property_def pdef resdef) pdeflist) resdef.R.output_port_defs ;

    )

let check_acyclic_port_references () =
  (* TODO *)
  ()

(* POST: can raise exceptions on failure that should be propagated
   to the user
*)
let typecheck () =
  check_instance_key_exists_in_rdef () ;
  check_ports_exist_in_rdef () ;
  check_acyclic_port_references ();
  ()

(******************************************************************************)


let print_machine_and_instance (mid,(k,id)) =
  let pp_state = R_pp.make_pp_state L.system_print_string in
  R_pp.pp_key (fst mid) pp_state ; 
  L.system_print_string ("\nId: "^id ^" Key:");
  R_pp.pp_key k pp_state ;
  L.system_print_string "\n" ;
  ()

let find_property_by_name rdef p =
  let pr = try [ List.find (fun pdef -> pdef.R.property_name = p) rdef.R.config_port_def ]
  with Not_found ->
    begin
      try R.SymbolMap.find p rdef.R.input_port_defs
      with Not_found ->
        try R.SymbolMap.find p rdef.R.output_port_defs
        with Not_found ->
	  let sref = ref "" in
          R_pp.pp_key rdef.R.key (R_pp.make_pp_state (R_pp.output_to_str sref)) ;
	  L.log_error L.ConsGen
	    ("Property " ^ p ^ " not found in port list of resource " ^ !sref);
	  raise Not_found
    end
  in
  pr

(******************************************************************************)
type constraint_t = INSIDE | ENVIRONMENT | PEER
type key     = (R.symbol * R.scalar_val) list
type instance = key * R.symbol
type resource_graph_node_data_t = instance * instance
type resource_graph_edge_data_t = constraint_t * int * int
type resource_graph_node_t = (resource_graph_node_data_t, resource_graph_edge_data_t) BidirectionalLabeledGraph.node

let resource_graph_node_tbl = Hashtbl.create 31

let reset_id, get_next_id =
  let unique_id = ref 0 in
  let _reset = fun () -> unique_id := 0; () in
  let _incr  =  fun () -> let i = !unique_id in incr unique_id; i in
  (_reset, _incr)

let get_node ( (m, k) : (instance * instance) ) =
  try Hashtbl.find resource_graph_node_tbl (m, k)
  with Not_found ->
    begin
      L.log_error L.ConsGen "get_node fails for machine : " ;
      let pp_state = R_pp.make_pp_state L.system_print_string in
      R_pp.pp_key (fst m) pp_state ;
      L.system_print_string ", id = " ; L.system_print_string (snd m) ;
      L.system_print_string "\n" ;
      R_pp.pp_key (fst k) pp_state ;
      L.system_print_string ", id = " ; L.system_print_string (snd k) ;
      failwith "get_node fails"
    end

(** PRE: node labeled (m,k) not in graph *)
let create_node (m,k) =
  let n = BidirectionalLabeledGraph.create_root (m, k) in
  Hashtbl.add resource_graph_node_tbl (m, k) n ;
  n

(* check if a resource is in the graph. usually used for debugging. *)
let in_graph ((m: instance), (k: instance)) =
  Hashtbl.mem resource_graph_node_tbl (m,k)

let get_or_create_node (m, k) =
  try Hashtbl.find resource_graph_node_tbl (m, k)
  with Not_found ->
    create_node (m,k)

let print_graph () =
  L.log_always L.ConsGen "Printing constraint graph";
  let numnodes = ref 0 in
  Hashtbl.iter (fun (mid,(k,id)) node ->
    incr numnodes;
    L.log_always L.ConsGen "Node : ";
    let pp_state = R_pp.make_pp_state  L.system_print_string in
    (* R_pp.pp_key (fst mid) pp_state ; 
    L.system_print_string ", id = " ; L.system_print_string (snd mid) ;
    *)
    R_pp.pp_key k pp_state ;
    L.system_print_string (", id = " ^id) ; 
    L.system_print_endline "\n" ;
    let incoming = G.get_in_edges node in
    List.iter (fun e ->
      let (sn, l, _) = G.deconstruct_edge e in
      let (etype, i,j) = match l with (PEER, i, j) -> ("peer",i,j) | (ENVIRONMENT, i, j) -> ("env",i,j) | (INSIDE, i, j) -> ("inside",i,j) in
      L.log_always L.ConsGen (Printf.sprintf "Edge %s [%d,%d] from:: " etype i j) ;
      (* print_machine_and_instance (G.get_node_label sn); *)
      let (_,(k,id)) = G.get_node_label sn in
      let keystr = ref "" in 
      let pp_state = R_pp.make_pp_state (R_pp.output_to_str keystr) in
      R_pp.pp_key k pp_state;
      L.log_always L.ConsGen ("Id : "^ id ^ " Key = " ^ !keystr); 
      L.system_print_string "\n" 
      ) incoming ;
	       ) resource_graph_node_tbl;
  L.log_always L.ConsGen ("Number of nodes = " ^ (string_of_int !numnodes));
  ()


let mk_graph_inst ( inst : R.resource_inst ) =
  let m = get_machine inst in
  let mid = m.R.resource_key, m.R.id in
  let n = get_or_create_node (mid, (inst.R.resource_key, inst.R.id) ) in
  n



(* external *)
(** this builds the resource dependency graph
    and propagates failures back to the user

   if successful, the resource graph from which constraints can be generated is created

   PRE: assumes the resource and instance databases have been built
 *)
let build_graph inst_list =
  let pending_vertex_queue = Queue.create () in
  let add_to_pending_queue n = Queue.add n pending_vertex_queue in
  let pending_queue_is_empty () = Queue.is_empty pending_vertex_queue in
  let pending_queue_get_next () =
    (assert (not (pending_queue_is_empty ())));
    Queue.take pending_vertex_queue
  in
  let pending_queue_size () = Queue.length pending_vertex_queue in

  let generated_instances_table = Hashtbl.create 13 in

  let process_atomic currentn a (kind, num, i) =
    let ((currentm: instance) , (currentkey, currentid) ) = G.get_node_label currentn in
    let resources = filter_rdef
	(fun key data -> matches key a.R.key_constraints)
    in
    if (resources = [] ) then
      begin
	let sref = ref "" in
	let to_str = R_pp.make_pp_state (R_pp.output_to_str sref) in
	R_pp.pp_atomic_constraint a to_str;
	raise (L.UserError (L.ConsGen, 0, 
			    "Unknown key in constraint: " ^ !sref,
			    "", []))
      end;
    (* TODO: need to update machine for peer constraints *)
    List.iter (fun r ->
      let possible_resources = lookup_instance_with_key r.R.key currentm in 
      let sref = R_pp.string_of_key r.R.key in
      L.log_always L.ConsGen ("List of possible resources for " ^ sref 
        ^ " is " ^ (string_of_int (List.length possible_resources)));
      let inst = 
        match possible_resources with
        | [ one ] -> one
        | [] -> 
          if Hashtbl.mem generated_instances_table (currentm, r.R.key) then
            Hashtbl.find generated_instances_table (currentm, r.R.key)
          else begin
            let t = make_new_tmp_inst r.R.key r currentm in
            Hashtbl.add generated_instances_table (currentm, r.R.key) t ;
            t
          end
        | _   -> assert false
      in
      let thisnode =
	if in_graph (currentm, (r.R.key, inst.R.id) ) then
	  get_node (currentm, (r.R.key, inst.R.id) )
	else begin
	  let n = create_node (currentm, (r.R.key, inst.R.id) ) in
	  add_to_pending_queue n ;
	  n
	end
      in
      L.log_always L.ConsGen "Adding edge...";
      G.hookup_parent_child thisnode currentn (kind, num, i) ) resources
  in
  let process_choicecon currentn kind cc num =
    let (m, (k,id)) = G.get_node_label currentn in
    let process () =
      match cc with
      | R.AtomicConstraint a -> process_atomic currentn a (kind,num,0)
      | R.OneOfConstraint alist ->
	  let i = ref 0 in
	  List.iter
	    (fun acon ->
	      process_atomic currentn acon (kind, num, !i);
	      incr i)
	    alist;
(*
	  L.log_debug L.ConsGen (string_of_int(!i) ^ " constraints processed")
*)
    in
    try
      let work m rr =
	    begin
	      L.log_debug L.ConsGen ("In work with " ^ rr.R.ref_id);
	      let thisnode =
	        if in_graph (m, (rr.R.ref_key, rr.R.ref_id) ) then
	          get_node (m, (rr.R.ref_key, rr.R.ref_id) )
	        else begin
                  let n = create_node (m, (rr.R.ref_key, rr.R.ref_id) ) in
                  add_to_pending_queue n;
                  n
	        end
	      in
              L.log_debug L.ConsGen (Printf.sprintf "Adding edge %d" num);
	      G.hookup_parent_child thisnode currentn (kind, num, 0)
	    end
      in
      let inst = lookup_inst (k,id) in
      match kind with
      | INSIDE ->
        begin
          match inst.R.inside_ref with
            None -> process ()
          | Some rr -> work m rr
         end
      | PEER -> (* TO DO : see code for ENVIRONMENT *)
         if inst.R.peer_refs = [] then process ()
         else
           List.iter (fun p -> work m p  ) inst.R.peer_refs
      | ENVIRONMENT ->
         let exists_match con ls =
           let rec _list_worker keycon ls =
             match ls with
             | [] -> (false, None)
             | rr :: rest -> 
               if matches rr.R.ref_key keycon then
                 (true, Some rr)
               else _list_worker keycon rest
           in
           match cc with
           | R.AtomicConstraint a ->
             _list_worker a.R.key_constraints ls
           | R.OneOfConstraint alist ->
             let rec _list_worker2 l =
               match l with
               | [] -> (false, None)
               | a :: rest ->
                 let (b,p) = _list_worker a.R.key_constraints ls in
                 if b then (b,p) else _list_worker2 rest 
             in 
             _list_worker2 alist
         in
         let (b, p) = exists_match cc inst.R.environment_refs in
         if b then
	   match p with Some rr -> work m rr | None -> assert false
         else ( process () )
    with Not_found -> (process () )
  in
  (* 1. create a node for each instance in the install script *)
  List.iter (fun inst ->
    let n = mk_graph_inst inst in
    add_to_pending_queue n)
    inst_list ;
  (* 2. create edges for each constraint of the instance *)
  while (not (pending_queue_is_empty ())) do
    begin
      Logging.log_debug L.ConsGen "One more iteration of the build-graph loop";
      Logging.log_debug L.ConsGen ("Pending queue size is "^(string_of_int (pending_queue_size())));
      let currentn = pending_queue_get_next () in
      let (currentm, (currentkey, currentid) ) = G.get_node_label currentn in
      (* lookup resource def *)
      let rdef = lookup_rdef currentkey in
      let inst = lookup_inst (currentkey,currentid) in
      let keystr = R_pp.string_of_key currentkey in
      L.log_always L.ConsGen ("Current key is: " ^ keystr);
      (match rdef.R.inside with
	None -> ()
      | Some c ->
	  begin
	    process_choicecon currentn INSIDE c 0
	  end );
      (match rdef.R.environment with
	None -> ()
      | Some cc ->
	  begin
	    match cc with
	      R.AllOfConstraint cclist ->
                L.log_always L.ConsGen "environment:: All of constraint" ;
                let _ = List.fold_left 
                  (fun num thiscc -> 
                     process_choicecon currentn ENVIRONMENT thiscc num ; num + 1) 0 cclist in
                L.log_always L.ConsGen "environment:: done!!" ;
		()
	    | R.ChoiceConstraint cc ->
		process_choicecon currentn ENVIRONMENT cc 0
	  end
      );
      (match rdef.R.peers with
	None -> ()
      | Some cc ->
          begin
	    match cc with
	      R.AllOfConstraint cclist ->
                L.log_always L.ConsGen "peer:: All of constraint" ;
		let _ = List.fold_left (fun num thiscc -> process_choicecon currentn PEER thiscc num ; num + 1) 0 cclist in
		()
	    | R.ChoiceConstraint cc ->
                L.log_always L.ConsGen "peer:: Choice constraint" ;
		process_choicecon currentn PEER cc 0
          end
      );
    end
  done ;
  print_graph ();
  ()

(** return a list of all instances to be installed in topological order *)
let topological_sort pmodel node_id_tbl id_node_tbl =
  let ndht = Hashtbl.create 13 in
  let uniquify_list ls =
   let t = Hashtbl.create 29 in
   List.iter (fun x -> Hashtbl.replace t x ()) ls;
   Hashtbl.fold (fun x y l -> x::l) t [] 
  in
  let is_set_to_true nd =
    let (m,inst) = G.get_node_label nd in
    let node_id = Hashtbl.find node_id_tbl (m,inst) in
    P.PredModel.find (string_of_int node_id) pmodel
  in
  let __debug_toposort nlist =
    List.iter (fun n -> let (m,(k,id)) = G.get_node_label n in
                      L.log_always L.ConsGen ("id = " ^ id);
                      L.log_always L.ConsGen (if is_set_to_true n then " set to true" else " set to false")
     ) nlist 
  in
  let find_nodes_with_no_incoming pmodel =
    let nlist = ref [] in
    Hashtbl.iter (fun (m,k) nd ->
      if G.get_in_edges nd = [] then
       let id = Hashtbl.find node_id_tbl (m,k) in
       if P.PredModel.find (string_of_int id) pmodel then
          nlist := nd :: !nlist
       else ()
      else ()
      ) resource_graph_node_tbl ;
    !nlist
  in
  let get_new_nodes n =
    let take n = 
      if not (is_set_to_true n) then false
      else
        let prevs = List.map G.get_source (G.get_in_edges n) in
        List.for_all (fun n' -> not (is_set_to_true n') or (Hashtbl.mem ndht n')) prevs
    in
    let targets = List.map G.get_target (G.get_out_edges n) in
    uniquify_list (List.filter take targets)
  in
  let no_incoming = find_nodes_with_no_incoming pmodel in
  __debug_toposort no_incoming;
  let rec toposort_worker worklist sofar =
    match worklist with
    | [] -> sofar
    | n :: rest ->
      begin
        Hashtbl.add ndht n true ;
        let newnodes = get_new_nodes n in
        __debug_toposort newnodes;
        let nodes = if List.mem n sofar then sofar else n::sofar in
        toposort_worker (rest  @ newnodes) (nodes)
      end
  in
  List.rev (toposort_worker no_incoming [])

let fix_up_tmp_instances (pmodel, node_id_tbl, id_node_tbl) n =
  let (m,k) = G.get_node_label n in
  if is_tmp_id (snd k) then
  begin
    L.log_debug L.ConsGen ("FIXING UP " ^ (snd k)) ;
    let inst = lookup_inst k in
    let rdef = lookup_rdef (fst k) in
    let incoming = G.get_in_edges n in
    let inside = List.filter 
      (fun e -> let (c,i,j) = G.get_edge_label e in
        let (m,k) = G.get_node_label (G.get_source e) in
        let id = Hashtbl.find node_id_tbl (m,k) in
        c = INSIDE && P.PredModel.find (string_of_int id) pmodel
      ) incoming
    in 
    let get_port_mapping rdef key =
      match rdef.R.inside with
      | None -> assert false
      | Some cc ->
        begin
          match cc with
          | R.AtomicConstraint a ->
            assert (matches key a.R.key_constraints ) ;
            a.R.port_mapping
          | R.OneOfConstraint alist ->
            try 
              let a = List.find (fun a -> matches key a.R.key_constraints) alist in
              a.R.port_mapping
            with Not_found -> assert false
        end
    in
    match inside with
    | [] -> ()
    | [ e ] -> 
      begin
        let n = G.get_source e in
        let (prev_mid, prev_k) = G.get_node_label n in
        let pmapping = get_port_mapping rdef (fst prev_k) in 
        let inside_ref = { R.ref_id = snd prev_k; 
                           R.ref_key = fst prev_k; 
                           R.ref_port_mapping = pmapping }
        in
        let inst' = { inst with R.inside_ref = Some inside_ref } in
        add_inst inst'  ;
        ()
      end
    | _ -> assert false 
  end
  else () ;
  let dinst = lookup_inst k in
  debug_inst dinst 

(******************************************************************************)
(* The following functions build and solve constraints out of a RIG. *)

(** partitions edges into collections that agree on the 1st two components of the label *)
let partition edges  =
  let ht = Hashtbl.create 31 in
  List.iter (fun e ->
    let srcnode = G.get_source e in
    let (a,b,c) = G.get_edge_label e in
    try
      let l = Hashtbl.find ht (a,b) in
      Hashtbl.replace ht (a,b) ((G.get_node_label srcnode)::l)
    with Not_found ->
      Hashtbl.add ht (a,b) [G.get_node_label srcnode ] ) edges ;
  Hashtbl.fold (fun k d sofar -> d :: sofar) ht []

(* external *)
(* Generate constraints from a RIG. *)
(* PRE: assume that the resource instance graph has been created *)
let generate_constraints install_spec =
  let id_node_ht = Hashtbl.create 31 in
  let node_id_ht = Hashtbl.create 31 in
  let get_id (m,k) =
    let id =
      try Hashtbl.find id_node_ht (m,k)
      with Not_found ->
	let i = get_next_id () in
	Hashtbl.add id_node_ht (m,k) i ;
	Hashtbl.add node_id_ht i (m,k) ;
	i
    in
    string_of_int id
  in
  let to_atomic (m,k) = P.Atom (get_id (m,k)) in
  let exactly_one pl = (* exactly one of the preds in pl is true *)
    let rec _exactly_one_worker (left, right) sofar =
      match right with 
      | [] -> P.And sofar
      | p :: rest ->
        let thisone = P.Implies ( p , P.Not (P.Or (left @ rest) )) in
        _exactly_one_worker (p :: left, rest) (thisone :: sofar)  
    in
    match pl with
      [] -> assert false 
    | [ p ] -> p
    | _ -> _exactly_one_worker ([], pl) []
  in
  let plist =
    Hashtbl.fold (fun (m,k) n psofar ->
      let a = to_atomic (m,k) in
      let incoming = G.get_in_edges n in
      let partitions = partition incoming in
      let list_of_p = List.map
	  (fun el -> let pl = List.map to_atomic el in
             match pl with [] -> assert false
             | [p ] -> P.Implies (a, p)
             | _ -> P.And [P.Implies (a, P.Or pl ) ; exactly_one pl ])
	      partitions
      in
      list_of_p @ psofar  )
      resource_graph_node_tbl []
  in
  (* for each vertex in the resource graph corresponding to a
     resource instance in the install spec, assert that the
     corresponding resource predicate is true
  *)
  let instplist = List.fold_left
      (fun sofar inst ->
	let m = get_machine inst in
        let mid = (m.R.resource_key, m.R.id) in
	let pi = to_atomic (mid, (inst.R.resource_key, inst.R.id) ) in
	assert (in_graph (mid, (inst.R.resource_key, inst.R.id) ) ) ;
	pi :: sofar
      )
      [] install_spec
  in
  (* for every "machine" that is generated temporarily, assert that it is
     not set to true (we cannot "manufacture" machines from thin air )
  *)
  let tmp_machine_plist = 
    Hashtbl.fold (fun (m,k) n psofar ->
      if is_tmp_id (snd k) then
      begin
        let rdef = lookup_rdef (fst k) in
        if rdef.R.inside = None then
          let a = to_atomic (m,k) in
          (P.Not a) :: psofar
        else psofar
      end
      else psofar ) resource_graph_node_tbl []
  in
  (instplist @ tmp_machine_plist @ plist, id_node_ht, node_id_ht)

(************************************************************************)
(* The following functions output the install specifications.
   This requires "hooking together" values of input and output ports
   based on the constraint solution
*)

let find_port_map_from_resource_ref rref k =
  if R.SymbolMap.mem k rref.R.ref_port_mapping then
    Some (rref.R.ref_key, rref.R.ref_id, R.SymbolMap.find k rref.R.ref_port_mapping)
  else None


let find_port_map rinst rdef k =
  L.log_debug L.ConsGen "find_port_map:::";
(*
  R_pp.pp_resource_inst rinst (R_pp.make_pp_state L.system_print_string);
  R_pp.pp_resource_def rdef (R_pp.make_pp_state L.system_print_string);
*)
  L.log_debug L.ConsGen ("key = " ^k );
  let ip_map =
    match rinst.R.inside_ref with
    | None -> None
    | Some rref -> find_port_map_from_resource_ref rref k
  in
  let env_map =
    if ip_map = None then
      let l = List.map (fun rref -> find_port_map_from_resource_ref rref k) rinst.R.environment_refs in
      try List.find (fun r -> not (r = None)) l
      with Not_found -> None
    else ip_map
  in
  let peer_map =
    if env_map = None then
      begin
	L.log_debug L.ConsGen ("In peer map with " ^ k);
	let l = List.map (fun rref -> find_port_map_from_resource_ref rref k) rinst.R.peer_refs in
	try List.find (fun r -> not (r = None)) l
	with Not_found -> None
      end
    else env_map
  in
  if peer_map = None then
    begin
      assert false
    end
  else
    peer_map


let rec json_of_port_reference rinst rdef pref =
  begin
    match pref with
    | R.ConfigPortRef slist ->
        if List.length slist = 1 then
          let s = List.hd slist in
          L.system_print_endline s ;
          try
            let v = R.SymbolMap.find s rinst.R.config_port
            in
            v
          with Not_found -> (* try default value in rdef *)
            begin
              try
                let pdef = List.find (fun p -> p.R.property_name = s) rdef.R.config_port_def in
                match pdef.R.property_val with
                | R.NoInitialVal ->
		    let user_error = ("Configuration port " ^ pdef.R.property_name ^" requires input from user.\n") in
		    raise (L.UserError (L.ConsGen, L.mUSER_INPUT_REQUIRED, user_error, "json_of_property_ref", []))
                | R.Default ival 
                | R.Fixed ival 
                | R.Includes ival -> json_of_initial_val rinst rdef ival 
              with Not_found -> assert false
            end
        else assert false (* failwith "TODO" *) 
    | R.InputPortRef (s, slist) ->
        L.system_print_endline "2nd THIS CASE " ;
        L.system_print_endline s;
        List.iter (fun s-> L.system_print_endline s) slist ;
        L.system_print_endline ("Printing ports of rinst " ^(rinst.R.id)) ;
        R.SymbolMap.iter (fun k d -> L.system_print_endline ("k = " ^ k ))  rinst.R.input_ports ;
        L.system_print_endline "2nd THIS CASE OVER" ;
        let p = try R.SymbolMap.find s rinst.R.input_ports with Not_found ->
	  raise (L.UserError (L.ConsGen, 0, s ^ " not found among input ports of instance " ^ rinst.R.id, "", []))
	in
        R.SymbolMap.iter (fun k d -> L.system_print_endline ("k = " ^ k ))  p ;
        let rec _portfinder ls p =
          match ls with [a] -> 
              L.log_debug L.ConsGen ("In portfinder with a = "^a);
              R.SymbolMap.iter (fun k d -> L.system_print_endline ("k = " ^ k ))  p ;
             R.SymbolMap.find a p
          | a :: rest -> 
            begin
              L.log_debug L.ConsGen ("In portfinder with a = "^a);
              R.SymbolMap.iter (fun k d -> L.system_print_endline ("k = " ^ k ))  p ;
              let p' = (R.SymbolMap.find a p) in
              match p' with
              | R.JsonMap jmap -> _portfinder rest jmap
              | _ -> assert false
            end
          | [] -> assert false
        in        
        _portfinder slist p
  end

and string_of_template_initial_val rinst rdef s slist =
        let substitution = List.map
	  (fun s' -> (s',
                      json_of_port_reference rinst rdef
                        (port_reference_of_string s')) ) slist in
        let subst_fn = fun s' ->
          try let j = List.assoc s' substitution  in
            match j with
              | R.JsonScalar (R.Integer i) -> string_of_int i
              | R.JsonScalar (R.Boolean true) -> "true"
              | R.JsonScalar (R.Boolean false) -> "false"
              | R.JsonScalar (R.Null) -> "null"
              | R.JsonScalar (R.String s) -> s
              | _ -> L.log_always L.ConsGen "In subst_fn" ; R_pp.pp_json_value j (R_pp.make_pp_state L.system_print_string) ; assert false
          with Not_found -> s'
        in
        Templates.substitute_template s subst_fn 

and json_of_initial_val rinst rdef (ival:R.initial_val) :R.json_value =
  match ival with
    | R.ScalarInitialVal sval -> R.JsonScalar sval
    | R.PortReference pref -> json_of_port_reference rinst rdef pref
    | R.TemplateInitialVal (s, slist) -> (* find values for ports in slist, substitute these values in s *)
        R.JsonScalar (R.String (string_of_template_initial_val rinst rdef s slist))
    | R.ListInitialVal iv_list ->
        R.JsonList
          (List.map (fun ival' -> json_of_initial_val rinst rdef ival')
             iv_list)
    | R.MapInitialVal prop_list ->
        R.JsonMap
        (List.fold_left
           (fun map (k, ival') ->
              R.SymbolMap.add k (json_of_initial_val rinst rdef ival') map)
           R.SymbolMap.empty prop_list)

let json_of_property_ref rinst rdef p =
  match p.R.property_val with
  | R.NoInitialVal ->
      begin
        L.system_print_endline ("No initial value specified for " ^ p.R.property_name);
        (* if no initial value is specified, look into port mappings *)
	None
      end
  | R.Includes ival
  | R.Default ival
  | R.Fixed ival -> Some (json_of_initial_val rinst rdef ival)

let find_port_map_for_key_from_constraint  c k =
  let rec find_atomic_con_list al k =
    match al with
    | [] -> None
    | a :: rest ->
	if matches k a.R.key_constraints
	then Some a.R.port_mapping else find_atomic_con_list rest k
  in
  let find_choice_con cc k =
    match cc with
    | R.AtomicConstraint a -> find_atomic_con_list  [a] k
    | R.OneOfConstraint alist -> find_atomic_con_list alist k
  in
  let rec find_choice_con_list al k =
    match al with
    | [] -> None
    | a :: rest ->
      (match find_choice_con a k with None -> find_choice_con_list rest k | Some pm -> Some pm)
  in
  match c with
  | R.AllOfConstraint cclist -> find_choice_con_list cclist k
  | R.ChoiceConstraint cc -> find_choice_con cc k

let find_inside_ref n pmodel rinst (node_id_tbl, id_node_tbl) =
  let incoming = G.get_in_edges n  in
  try
    let e = List.find (fun e ->
      let (sn, l, _) = G.deconstruct_edge e in
      match l with
      | (INSIDE, _, _) ->
	  let (m,k) = G.get_node_label sn in
	  let id = Hashtbl.find node_id_tbl (m,k) in
	  let b = P.PredModel.find (string_of_int id) pmodel in
	  b
      | _ -> false
		      ) incoming
    in
    let (sn, _, _) = G.deconstruct_edge e in
    let (_,(k,i)) = G.get_node_label sn in
    let (refid, pmapping) = match rinst.R.inside_ref with
      Some rref -> 
        (rref.R.ref_id , rref.R.ref_port_mapping)
    | None -> failwith "ID NOT FOUND"
    in
    Some { R.ref_id = refid ;
           R.ref_key = k ;
           R.ref_port_mapping = pmapping ;
	 }
  with Not_found -> None


let find_peer_refs n pmodel rinst (node_id_tbl, id_node_tbl) =
  L.log_debug L.ConsGen "In find_peer_refs" ;
  let incoming = G.get_in_edges n in
  try
    let elist = List.filter (fun e ->
      let (sn, l, _) = G.deconstruct_edge e in
      match l with
      | (PEER, _, _) ->
	  let (m,k) = G.get_node_label sn in
	  let id = Hashtbl.find node_id_tbl (m,k) in
	  let b = P.PredModel.find (string_of_int id) pmodel in
	  b
      | _ -> false
			    ) incoming
    in
    List.map (fun e ->
      let (sn, _, _) = G.deconstruct_edge e in
      let (_,(k,id)) = G.get_node_label sn in
      try
        let eref = List.find (fun r -> r.R.ref_key = k) rinst.R.peer_refs in
        { R.ref_id = eref.R.ref_id ;
          R.ref_key = k ;
          R.ref_port_mapping = eref.R.ref_port_mapping ;
        }
      with Not_found ->  (* failwith "peer not found" *)
        let eref = lookup_inst (k,id) in
        let edef = lookup_rdef rinst.R.resource_key in
        let cons = match edef.R.peers with None -> failwith "peer not found" | Some cc -> cc in
        let pm = find_port_map_for_key_from_constraint cons k in
        { R.ref_id = eref.R.id ;
          R.ref_key = k ;
          R.ref_port_mapping = match pm with None -> R.SymbolMap.empty | Some pm' -> pm'
        }
	     ) elist
  with Not_found -> []

let find_env_refs n pmodel rinst (node_id_tbl, id_node_tbl) =
  L.log_debug L.ConsGen "In find_env_refs" ;
  L.log_debug L.ConsGen ("Inst id = " ^ rinst.R.id);
  let incoming = G.get_in_edges n in
  try
    let elist = List.filter (fun e ->
      let (sn, l, _) = G.deconstruct_edge e in
      match l with
      | (ENVIRONMENT, _, _) ->
          L.system_print_endline "found";
	  let (m,k) = G.get_node_label sn in
	  let id = Hashtbl.find node_id_tbl (m,k) in
	  let b = P.PredModel.find (string_of_int id) pmodel in
	  b
      | _ -> false
			    ) incoming
    in
    L.log_debug L.ConsGen ("find_env_refs: elist length = " ^ (string_of_int (List.length elist)));
    List.map (fun e ->
      let (sn, _, _) = G.deconstruct_edge e in
      let (_,(k,id)) = G.get_node_label sn in
      L.log_debug L.ConsGen "current key is " ; R_pp.pp_key k (R_pp.make_pp_state L.system_print_string) ; 
      L.log_debug L.ConsGen "Printing keys in environment refs of instance" ;
      List.iter (fun r -> R_pp.pp_key r.R.ref_key (R_pp.make_pp_state L.system_print_string)) rinst.R.environment_refs ;
      try
	let eref = List.find (fun r -> r.R.ref_key = k) rinst.R.environment_refs in
        { R.ref_id = eref.R.ref_id ;
          R.ref_key = k ;
          R.ref_port_mapping = eref.R.ref_port_mapping ;
        }
      with Not_found ->
        let eref = lookup_inst (k,id) in
        let edef = lookup_rdef rinst.R.resource_key in
        let cons = match edef.R.environment with None -> failwith "env not found" | Some cc -> cc in
        let pm = find_port_map_for_key_from_constraint cons k in
        { R.ref_id = eref.R.id ;
          R.ref_key = k ;
          R.ref_port_mapping = match pm with None -> R.SymbolMap.empty | Some pm' -> pm'
        }
	     ) elist
  with Not_found -> []


let map_input_ports rdef rinst =
  L.log_debug L.ConsGen ("In map_input_ports with key " ^ rinst.R.id);
  let _input_port_worker k d smap =
    ignore (L.log_debug L.ConsGen ("In _f:: Key = " ^ k ^ "\n")) ;
    let ilist = try 
      R.SymbolMap.find k rdef.R.input_port_defs
    with Not_found -> assert false
    in
    match (find_port_map rinst rdef k) with
    | Some (resource_key, resource_id, property_name) ->
	begin
	  L.log_debug L.ConsGen ("Port mapped from " ^ resource_id);
	  let mapped_rdef = lookup_rdef resource_key in
	  let ri = lookup_inst (resource_key, resource_id) in
	  let pr = find_property_by_name mapped_rdef property_name in
	  let rioports = R.SymbolMap.find property_name ri.R.output_ports in	  
	  let pl = List.fold_left 
	      (fun sofar p ->
		L.log_debug L.ConsGen ("Now with property " ^ p.R.property_name);
		(try
		  let prop = 
		    List.find (fun n -> n.R.property_name = p.R.property_name) ilist 
		  in
		  match prop.R.property_val with
		  | R.Includes _ ->
		      (* fix the output port of ri *)
		      L.log_debug L.ConsGen ("property " ^property_name ^ ":" ^ p.R.property_name ^ " added to includes list");
		      add_includes_list (k, rinst, resource_key, resource_id, property_name, prop)
		  | _ -> ()
		with Not_found -> ()); 
		begin
		  let jv = try
		    R.SymbolMap.find p.R.property_name rioports 
		  with Not_found -> assert false
		  in
		  R.SymbolMap.add p.R.property_name jv sofar
		end
	      ) R.SymbolMap.empty pr 
	  in
	  R.SymbolMap.add k pl smap
	end
    | None -> L.log_debug L.ConsGen ("Assertion hit with key " ^ k ^"\n") ;assert false
  in
  R.SymbolMap.fold _input_port_worker
    rdef.R.input_port_defs
    (R.SymbolMap.empty)

let map_output_ports rdef rinst =
  L.log_debug L.ConsGen ("In map_output_ports with key " ^ rinst.R.id);
  let _output_ports_worker k d smap =
    let pl = List.fold_left
	(fun sofar p ->
          L.log_debug L.ConsGen ("Now looking for " ^ p.R.property_name) ; 
          let pval = json_of_property_ref rinst rdef p in
          match pval with
            None   -> 
	      begin
		L.log_warning L.ConsGen ("WARNING: no mapping found for " ^ p.R.property_name ); 
		match p.R.property_type with
		  R.ListType _ -> R.SymbolMap.add p.R.property_name (R.JsonList []) sofar
		| _ -> sofar
	      end
          | Some s -> 
              let stref = ref "" in 
              R_pp.pp_json_value s (R_pp.make_pp_state (R_pp.output_to_str stref));
              L.log_debug L.ConsGen ("mapped to : " ^ !stref); 
              R.SymbolMap.add p.R.property_name s sofar
	) R.SymbolMap.empty d
    in
    R.SymbolMap.add k pl smap
  in
  R.SymbolMap.fold _output_ports_worker
    rdef.R.output_port_defs (R.SymbolMap.empty)

let fill_in_config_ports rdef rinst =
  let local_symmap_ref = ref (R.SymbolMap.empty) in
  let do_one_property_def pdef =
    if (R.SymbolMap.mem pdef.R.property_name  rinst.R.config_port) then
      let init_val = R.SymbolMap.find pdef.R.property_name rinst.R.config_port in
      local_symmap_ref := R.SymbolMap.add pdef.R.property_name init_val !local_symmap_ref
    else begin
      match pdef.R.property_val with
      | R.NoInitialVal ->
        let rk = ref "" in
        R_pp.pp_key rdef.R.key (R_pp.make_pp_state (R_pp.output_to_str rk)) ;
        raise (L.UserError (L.ConsGen, L.mUSER_INPUT_REQUIRED, s_ "No initial value given for config port : " ^ pdef.R.property_name ^ " of resource key : " ^ !rk, "", []))
      | R.Default (R.ScalarInitialVal sval) -> local_symmap_ref := R.SymbolMap.add pdef.R.property_name (R.JsonScalar sval) !local_symmap_ref
      | _ -> failwith "TODO"
    end
  in
  List.iter do_one_property_def rdef.R.config_port_def ;
  !local_symmap_ref

let fill_in_user_data rdef rinst = 
  (* merge user data from the resource def and the resource inst, giving priotiry to the data from the instance *)
  L.log_info L.ConsGen "PRINTING RESOURCE USER DATA";
  R.SymbolMap.iter (fun k v -> L.log_info L.ConsGen k; R_pp.pp_json_value v (R_pp.make_pp_state L.system_print_string)) rdef.R.user_data_def; 
  L.log_info L.ConsGen "PRINTING RESOURCE USER DATA";
  R.SymbolMap.iter (fun k v -> L.log_info L.ConsGen k; R_pp.pp_json_value v (R_pp.make_pp_state L.system_print_string)) rinst.R.user_data; 
  let jmap = R.SymbolMap.fold (fun k v m -> if R.SymbolMap.mem k m then m else R.SymbolMap.add k v m) rdef.R.user_data_def rinst.R.user_data 
  in
  L.log_info L.ConsGen "PRINTING USER DATA";
  R.SymbolMap.iter (fun k v -> L.log_info L.ConsGen k; R_pp.pp_json_value v (R_pp.make_pp_state L.system_print_string)) jmap; 
  jmap 


let set_includes_ports rd ri (key, rinst, map_resource_key, map_resource_id, map_property_name, p) =
  L.log_debug L.ConsGen ("set includes port called with "  ^ p.R.property_name);
  debug_rdef rd; debug_inst ri;
  let incpval = json_of_property_ref ri rd p in
  L.log_debug L.ConsGen "Property value is = ";
  (match incpval with None -> L.log_debug L.ConsGen "NONE"
  | Some s -> R_pp.pp_json s (R_pp.make_pp_state L.system_print_string));
  match incpval with 
  | None -> ri
  | Some s ->
    (* add this to input port of  ri *)
    let jmap = R.SymbolMap.find key ri.R.input_ports in
    let new_map =  R.SymbolMap.add p.R.property_name s jmap in
    let new_ip = R.SymbolMap.add key new_map ri.R.input_ports in
    let ri' = { ri with R.input_ports = new_ip }  in
    (* add this to output port of  ri *)
    let ori = try lookup_inst (map_resource_key, map_resource_id) with Not_found -> assert false in
    let jmap = R.SymbolMap.find map_property_name  ori.R.output_ports in
    let newmap = R.SymbolMap.add p.R.property_name s jmap in
    let newop = R.SymbolMap.add map_property_name newmap ori.R.output_ports in
    add_inst { ori with R.output_ports = newop }; 
    ri'
   
(** given a solution from the sat solver (a P.PredicateModel instance),
   and a table mapping id's in the constraints to (instance, instance) pairs,
   print out the satisfying assignment.

   The variables marked "true" are the ones to be installed.
*)
let print_model pmodel node_id_tbl id_node_tbl =
      L.log_always L.ConsGen "************Printing model***********";
(*
  let ts = topological_sort pmodel id_node_tbl node_id_tbl in
  L.log_always L.ConsGen "Printing topological order:" ;
  List.iter (fun n -> let (m,k) = G.get_node_label n in
   L.log_always L.ConsGen "Key = " ; R_pp.pp_key k (R_pp.make_pp_state L.system_print_string) ) ts ;
  L.log_always L.ConsGen "done printing topological order:" ;
*)
      let fp = open_out "install.out" in
      let print_to_file fp s =
        Printf.fprintf fp "%s" s
      in
      Printf.fprintf fp "[\n";
      P.PredModel.iter (fun k b ->
	L.log_always L.ConsGen ("Now printing install spec for key " ^ k) ;
        let id = try int_of_string k with _ -> failwith "print_model" in
	let (m,(k,i)) = try Hashtbl.find node_id_tbl id with Not_found -> failwith "id not found" in
        print_machine_and_instance (m,(k,i)) ;
	L.log_always L.ConsGen (if b then ":: true" else ":: false");
        let n = get_node (m,(k,i)) in
        let rinst = lookup_inst (k,i) in
        let rdef = lookup_rdef k in
        let new_cp = fill_in_config_ports rdef rinst in
        let udata = fill_in_user_data rdef rinst in
        let rinst_1 = { rinst with R.config_port = new_cp ; R.user_data = udata } in
        L.log_debug L.ConsGen "config ports filled" ;
        let inside = find_inside_ref n pmodel rinst_1 (id_node_tbl, node_id_tbl) in
        let rinst_2 = { rinst_1 with R.inside_ref = inside } in
        L.log_debug L.ConsGen "inside constraints filled" ;
        let peers =  find_peer_refs  n pmodel rinst_2 (id_node_tbl, node_id_tbl) in
        let rinst_3 = { rinst_2 with R.peer_refs = peers } in
        L.log_debug L.ConsGen "peer constraints filled" ;
        let envs =   find_env_refs   n pmodel rinst_3 (id_node_tbl, node_id_tbl) in
        let rinst_4 = { rinst_3 with R.environment_refs = envs } in
        L.log_debug L.ConsGen "env constraints filled" ;
        let new_ip = map_input_ports rdef rinst_4 in
        let rinst_5 = { rinst_3 with R.input_ports = new_ip } in
        L.log_debug L.ConsGen "input ports filled" ;
        let new_op = map_output_ports rdef rinst_5 in
        L.log_debug L.ConsGen "output ports filled" ;
	let new_rinst = { rinst_5 with R.output_ports = new_op } in
        add_inst new_rinst ;
        R_pp.pp_resource_inst new_rinst (R_pp.make_pp_state (print_to_file fp));
        L.system_print_string "\n"; Printf.fprintf fp ",\n"
		       )
	pmodel ;
      Printf.fprintf fp "\n]\n";
      close_out fp ;
      ()




(*****************************************************************************)
(* API *)
let parse_json_file fname : R.json_value =
  try
    R.ParseInfo.errors_in_input := false;
    let in_chan = open_in fname
    in let lexbuf = Lexing.from_channel in_chan
    in let json_value_opt = Parser.json_value Lexer.token lexbuf
    in match json_value_opt with
        Some json_value ->
          if not !(R.ParseInfo.errors_in_input) then json_value
          else
            raise (L.UserError (L.Prs, L.mSYNTAX_ERROR, s_ ("Exiting due to syntax errors in file ") ^ fname, "parse_json_file" , []))
      | None ->
          raise (L.UserError (L.Prs, L.mSYNTAX_ERROR, s_ ("Exiting due to syntax errors in file ") ^ fname, "parse_json_file", []))
  with
      End_of_file ->
	raise (L.UserError (L.Prs, L.mEOF, s_ ("Failed due to premature end of file :") ^ fname, "parse_json_file", []))
    | Sys_error e -> raise (L.UserError (L.Prs, L.mFILE_NOT_FOUND, s_ ("Unable to open file ") ^ fname, "parse_json_file", []))


(* API *)
(* can RAISE: UserError *)
let read_rdefs_from_file (fname : string) =
  let rdef_json = parse_json_file fname in
  Parse_rdef.parse_rdef_library rdef_json

(* API *)
(* can RAISE: UserError *)
let read_install_spec_from_file (fname : string) =
  let install_spec_json = parse_json_file fname in
  Parse_resource.parse_resource_list install_spec_json

(* API *)
let get_config_ports (only_types:bool) rdef rinst =
 let config_list =
 List.map (fun pdef ->
   L.log_debug L.ConsGen ("In get_config_ports with " ^ pdef.R.property_name);
   let pdefmap1 =
     match  pdef.R.property_display_name with
     | None -> R.SymbolMap.empty
     | Some s -> R.SymbolMap.add "display_name"
                   (R.JsonScalar (R.String s)) R.SymbolMap.empty
   in
   let pdefmap2 =
     match  pdef.R.property_help with
     | None -> pdefmap1
     | Some s -> R.SymbolMap.add "help"
                   (R.JsonScalar (R.String s)) pdefmap1
   in
   let json_name = pdef.R.property_name in
   let json_type = json_of_type_decl pdef.R.property_type in
   let pdefmap3 =
     R.SymbolMap.add "name" (R.JsonScalar (R.String json_name))
       (R.SymbolMap.add "type" json_type pdefmap2)
   in
   let json_default_value =
     if only_types = true then None
     else begin
       L.log_debug L.ConsGen ("Now checking rinst with " ^ json_name);
       debug_inst rinst ;
       
       if ( R.SymbolMap.mem json_name rinst.R.config_port) then begin
         L.log_debug L.ConsGen ("Found in rinst:" ^ json_name);
         Some (R.SymbolMap.find json_name rinst.R.config_port)
       end
       else
         match pdef.R.property_val with
         | R.Default ival ->
         begin
           match ival with
           | R.ScalarInitialVal sv -> Some (R.JsonScalar sv)
           | R.PortReference pr -> Some (json_of_port_reference rinst rdef pr )
           | R.MapInitialVal _ ->  assert false
           | R.ListInitialVal _ -> assert false
           | R.TemplateInitialVal (s,slist) -> Some (R.JsonScalar (R.String (string_of_template_initial_val rinst rdef s slist))) 
         end
     	| R.NoInitialVal -> None
        | _ -> assert false
     end
   in
   let pdefmap =
     match json_default_value with
     | None -> pdefmap3
     | Some v -> (R.SymbolMap.add "default" v pdefmap3)
   in
   R.JsonMap pdefmap
   )  rdef.R.config_port_def 
   in
   L.log_debug L.ConsGen "About to return from get_config_port";
   List.iter (fun l -> let sref = ref "" in
     R_pp.pp_json l (R_pp.make_pp_state (R_pp.output_to_str sref));
     L.log_debug L.ConsGen !sref)  config_list;
   R.JsonList config_list



class type config_engine =
  object

    val mutable current_node :
        ((instance * instance, constraint_t * int * int)
        BidirectionalLabeledGraph.node) option

    val id_node_tbl :
        (int, instance * instance ) Hashtbl.t

    val node_id_tbl :
        (instance * instance, int) Hashtbl.t

    val mutable node_iterator :
        (instance * instance, constraint_t * int * int)
        BidirectionalLabeledGraph.node inst_iterator

    val pmodel : Predicates.pred_model

    val topo_list :
        (instance * instance, constraint_t * int * int)
        BidirectionalLabeledGraph.node list

  method private get_current_inst : unit -> R.resource_inst

  method has_next : unit -> bool
  method has_prev : unit -> bool
  method next : unit -> bool
  method prev : unit -> bool
  method reinit : unit -> unit
  method get_config_port_types_as_string : unit -> string
  method get_config_ports_as_string : unit -> string
  method set_config_ports_from_string : string -> unit
  method set_ports : string -> string -> unit
  method set_ports_of_current : unit -> unit
  method get_resource : string -> string -> string
  method get_current_resource : unit -> string
  method write_install_file : string -> unit
end

class config_engine_factory
      (model_: P.pred_model)
      (node_id_tbl_ : (instance * instance, int) Hashtbl.t)
      (id_node_tbl_ :  (int, instance * instance) Hashtbl.t)
      (topo_list_ : (instance * instance, 
                     constraint_t * int * int) BidirectionalLabeledGraph.node list) =
  object (self)

  val         pmodel        = model_
  val         node_id_tbl   = node_id_tbl_
  val         id_node_tbl   = id_node_tbl_
  val         topo_list     = topo_list_
  val mutable node_iterator = new inst_iterator topo_list_

  val mutable current_node = (None : (instance * instance, 
                     constraint_t * int * int) BidirectionalLabeledGraph.node option)

  method private get_current_inst () =
      match current_node with
      | Some n ->
        let (m,k) = G.get_node_label n in
        lookup_inst k
      | None -> failwith "Sync error"

  method has_next () = node_iterator#has_next ()
  method has_prev () = node_iterator#has_prev ()

  method next () =
    if node_iterator#has_next () then
    begin
      current_node <- Some (node_iterator#next ()) ;
      true
    end
    else false

  method prev () =
    if node_iterator#has_prev () then
    begin
      current_node <- Some (node_iterator#prev ()) ;
      true
    end
    else false

  method reinit () = node_iterator <- new inst_iterator topo_list

  method get_config_port_types_as_string () = 
    let (inst, rdef) =
      match current_node with
      | Some n ->
        let (m,k) = G.get_node_label n in
        (lookup_inst k, lookup_rdef (fst k))
      | None -> failwith "Sync error"
    in
    L.log_debug L.ConsGen ("[CAPI] Getting config port types of " ^ inst.R.id);
    L.log_debug L.ConsGen "Getting config ports [types]" ;
    let cfgmap1 = R.SymbolMap.add "key" (json_of_key inst.R.resource_key) R.SymbolMap.empty in
    let cfgmap2 = R.SymbolMap.add "id" (R.JsonScalar (R.String inst.R.id) ) cfgmap1 in
    let cfgmap3 = R.SymbolMap.add "resource_display_name" (R.JsonScalar (R.String  rdef.R.display_name ) ) cfgmap2 in
    let cfgmap4 =
      match inst.R.properties with
      | None -> cfgmap3
      | Some jmap -> R.SymbolMap.add "properties" (R.JsonMap jmap) cfgmap3
    in
    let cfgportvals = try get_config_ports true rdef inst
      with ex -> L.system_print_endline (Printexc.to_string ex) ; assert false
    in
    let cfgmap5 = R.SymbolMap.add "config_property_defs" cfgportvals cfgmap4 in
    let jsonval = R.JsonMap cfgmap5 in
    let sref = ref ""  in
    R_pp.pp_json_value jsonval (R_pp.make_pp_state (R_pp.output_to_str sref)) ;
    !sref

  method get_config_ports_as_string () =
    let (inst, rdef) =
      match current_node with
      | Some n ->
        let (m,k) = G.get_node_label n in
        (lookup_inst k, lookup_rdef (fst k))
      | None -> failwith "Sync error"
    in
    reset_includes_list();
    L.log_debug L.ConsGen ("[CAPI]Getting config ports of " ^ inst.R.id);
    L.log_debug L.ConsGen ("Initializing inside, peer, environment, and input ports of " ^ inst.R.id);
    let machine = get_machine inst in
    let mid = machine.R.resource_key, machine.R.id in
    let n = get_node (mid, (inst.R.resource_key, inst.R.id)) in
    let inside = find_inside_ref n pmodel inst (node_id_tbl, id_node_tbl) in
    let inst_2 = { inst with R.inside_ref = inside }   in
    L.log_debug L.ConsGen "inside constraints filled" ;
    let peers =  find_peer_refs  n pmodel inst_2 (node_id_tbl, id_node_tbl) in
    let inst_3 = { inst_2 with R.peer_refs = peers } in
    L.log_debug L.ConsGen "peer constraints filled" ;
    let envs =   find_env_refs   n pmodel inst_3 (node_id_tbl, id_node_tbl) in
    let inst_4 = { inst_3 with R.environment_refs = envs } in
    L.log_debug L.ConsGen "env constraints filled" ;
    let new_ip = map_input_ports rdef inst_4 in
    let inst_5 = { inst_4 with R.input_ports = new_ip } in
    L.log_debug L.ConsGen "input ports filled" ;
    add_inst inst_5; 
    L.log_debug L.ConsGen "Getting config ports" ;
    let cfgmap1 = R.SymbolMap.add "key" (json_of_key inst_5.R.resource_key) R.SymbolMap.empty in
    let cfgmap2 = R.SymbolMap.add "id" (R.JsonScalar (R.String inst_5.R.id) ) cfgmap1 in
    let cfgmap3 = R.SymbolMap.add "resource_display_name" (R.JsonScalar (R.String  rdef.R.display_name ) ) cfgmap2 in
    let cfgmap4 =
      match inst_5.R.properties with
      | None -> cfgmap3
      | Some jmap -> R.SymbolMap.add "properties" (R.JsonMap jmap) cfgmap3
    in
    let cfgportvals = try get_config_ports false rdef inst_5
    with ex -> L.system_print_endline (Printexc.to_string ex) ; assert false
    in
    let cfgmap5 = R.SymbolMap.add "config_property_defs" cfgportvals cfgmap4 in
    let jsonval = R.JsonMap cfgmap5 in
    let sref = ref ""  in
    R_pp.pp_json_value jsonval (R_pp.make_pp_state (R_pp.output_to_str sref)) ;
    !sref
      
  (* GUI API *)
  method set_config_ports_from_string jmapstring = 
  try
    let lexbuf = Lexing.from_string jmapstring in
    let json_value_opt = Parser.json_value Lexer.token lexbuf in
    L.log_debug L.ConsGen ("[CAPI] In set_config_ports_from_string :: parsed json "); flush stdout;
    match json_value_opt with
    | Some (R.JsonMap jval) ->
      if not !(R.ParseInfo.errors_in_input) then
      begin
        let key_map = match (R.SymbolMap.find "key" jval) with
          R.JsonMap p -> p | _ -> failwith "cast error"
        in
        let key = List.rev (R.SymbolMap.fold (fun k d lst -> let dval = Json.cast_to_scalar d in (k,dval)::lst) key_map []) in
        let id  = Json.cast_to_symbol (R.SymbolMap.find "id" jval) in
        let inst = lookup_inst (key,id) in
        L.log_debug L.ConsGen ("Setting config ports from json for instance " ^ inst.R.id);
        match R.SymbolMap.find "config_property_defs" jval with
        | (R.JsonList jcfgports) ->
          let jcfgmap = List.fold_left (fun current_map thistuple ->
            match thistuple with
            | R.JsonMap jmap ->
              let name =
                let jsonname = R.SymbolMap.find "name" jmap in
                match jsonname with
                | R.JsonScalar (R.String s) -> s
                | _ -> assert false
              in
              let value = try (R.SymbolMap.find "default" jmap) 
              with Not_found ->
                begin
                  L.log_warning L.ConsGen ("Value not found for config port "^name);
                  R.JsonScalar (R.String "<UNDEFINED>")
                end
              in
              R.SymbolMap.add name value current_map
            | _ -> assert false
           ) R.SymbolMap.empty jcfgports
          in
          let updated_inst = { inst with R.config_port = jcfgmap } in
          let updated_inst = fold_left_includes_list (set_includes_ports (lookup_rdef key)) updated_inst in
          (* reset_includes_list (); *)
          L.log_always L.ConsGen "set_config_ports_from_string: Updated config ports" ;
          R_pp.pp_resource_inst updated_inst (R_pp.make_pp_state L.system_print_string) ;
          add_inst updated_inst
        | _ -> failwith "System error: config_property_defs not a list"
      end
      else failwith "Syntax errors in json string"
    | _ -> failwith "Syntax errors in json string"
  with ex -> L.log_always L.ConsGen ("EXCEPTION raised in set_config_ports_from_string:: " ^(Printexc.to_string ex)) ; flush stdout; raise ex

  (* GUI API *)
  method set_ports jkey jid =
  try
    L.log_always L.ConsGen "In set_ports";
    let lexbuf = Lexing.from_string jkey in
    let json_value_opt = Parser.json_value Lexer.token lexbuf in
    let jval =
      match json_value_opt with
      | Some (R.JsonMap jval) -> jval
      | _ -> failwith "Syntax errors in json string"
    in
    let key_of_jval = List.rev 
      (R.SymbolMap.fold (fun k d lst -> let dval = Json.cast_to_scalar d in (k,dval)::lst) 
         jval []) in
    let (rdef, rinst) = (lookup_rdef key_of_jval, lookup_inst (key_of_jval, jid) ) in
    let machine = get_machine rinst in
    let mid = machine.R.resource_key, machine.R.id in
    let udata = fill_in_user_data rdef rinst in
    let rinst_5 = { rinst with R.user_data = udata } in
    let new_op = map_output_ports rdef rinst_5 in
    let rinst_6 = { rinst_5 with R.output_ports = new_op } in
    L.log_debug L.ConsGen ("Includes list has size " ^(string_of_int (List.length (debug_get_includes_list())))) ;
    let rinst_7 = fold_left_includes_list (set_includes_ports rdef) rinst_6 in
    (* reset_includes_list (); *)
    add_inst rinst_7;
    L.log_debug L.ConsGen "Added updated instance to instance database";
    ()
  with ex -> L.log_debug L.ConsGen ("EXCEPTION RAISED IN SET_PORTS!!" ^ (Printexc.to_string ex)); flush stdout; raise ex 

  method set_ports_of_current () =
    let inst = self#get_current_inst () in
    let json_key = json_of_key inst.R.resource_key in
    let jid = inst.R.id in
    let sref = ref ""  in
    R_pp.pp_json_value json_key (R_pp.make_pp_state (R_pp.output_to_str sref)) ;
    self#set_ports !sref jid

  method get_resource jkey jid =
    let lexbuf = Lexing.from_string jkey in
    let json_value_opt = Parser.json_value Lexer.token lexbuf in
    let jval =
      match json_value_opt with
      | Some (R.JsonMap jval) -> jval
      | _ -> failwith "Syntax errors in json string"
    in
    let key_of_jval = List.rev (R.SymbolMap.fold (fun k d lst -> let dval = Json.cast_to_scalar d in (k,dval)::lst) jval []) in
    let rinst = lookup_inst (key_of_jval, jid) in
    let sref = ref "" in
    let pp_state = R_pp.make_pp_state (R_pp.output_to_str sref) in
    R_pp.pp_resource_inst rinst pp_state ;
    !sref



  method get_current_resource () =
    let inst =
      match current_node with
      | Some n ->
        let (m,k) = G.get_node_label n in
        lookup_inst k
      | None -> failwith "Sync error"
    in
    let sref = ref "" in
    let pp_state = R_pp.make_pp_state (R_pp.output_to_str sref) in
    R_pp.pp_resource_inst inst pp_state ;
    !sref

  method write_install_file fname =
      let fp = open_out fname in
      let print_to_file fp s =
        Printf.fprintf fp "%s" s
      in
      let pp_state = R_pp.make_pp_state (print_to_file fp) in
      let rinst_list =
        List.map
          (fun n ->
             let (m,k) = G.get_node_label n in lookup_inst k) topo_list in
      R_pp.pp_resource_inst_list
        rinst_list pp_state;
      close_out fp


end


(* external *)
(* can RAISE: UserError *)
let generate (rdef_list : Resources.resource_def list)
             (install_spec: Resources.resource_inst list) =
  L.log_always L.ConsGen "In generate" ;
  mk_rdef_database rdef_list ;
  mk_inst_database install_spec ;
  typecheck ();

  L.log_always L.ConsGen "Database Constructed" ;
  print_rdef ();
  print_inst ();

  (* build resource instance graph from install_spec *)
  (try
    L.log_always L.ConsGen "Building graph" ;
    build_graph install_spec
  with ex -> L.system_print_string "Build graph failed" ; raise ex);
  L.log_always L.ConsGen "... done Building graph" ;
  L.log_always L.ConsGen "Generating constraints" ;

  let plist, id_node_tbl, node_id_tbl = generate_constraints install_spec in

  L.log_always L.ConsGen "...done";
  L.log_debug L.ConsGen "Printing constraints..." ;
  List.iter (fun p -> L.log_debug L.ConsGen (P.pred2str p)) plist ;
  L.log_debug L.ConsGen "\nVariable ids:";
  Hashtbl.iter (fun k d -> L.system_print_string (string_of_int d) ; L.system_print_string " :: "; print_machine_and_instance k) id_node_tbl ;
  L.log_always L.ConsGen "... done printing constraints";
  L.log_always L.ConsGen "Solving constraints";
  L.log_always L.ConsGen (P.pred2camlstr (P.And plist));
  let model = P.solve_pred (P.And plist) in
  L.log_always L.ConsGen "... done solving constraints";
  let pmodel = match model with
      None ->
      begin
        L.log_error L.ConsGen (s_ "The install specification is not implementable. No solution to constraints found." ) ;
	(* should print out conflicting "core" *)
        raise (L.UserError (L.ConsGen, L.mNO_SOLUTION, s_ "Config fails: No solution found to installation requirements", "", []))
      end
    | Some _pmodel -> _pmodel
  in
  P.PredModel.iter (fun k v -> L.log_always L.ConsGen (k ^ " assigned " ^ (if v then "true" else "false")) ) pmodel; 
  let topo_list = topological_sort pmodel id_node_tbl node_id_tbl in
  L.log_always L.ConsGen "Printing topological order:" ;
  List.iter (fun n -> let (m, (k,id)) = G.get_node_label n in
  L.log_always L.ConsGen "Key = " ; R_pp.pp_key k (R_pp.make_pp_state L.system_print_string) ;
  L.log_always L.ConsGen ("id = " ^ id) ;
  ) topo_list ;
  L.log_always L.ConsGen "done printing topological order:" ;
  (* at this point, all the temporary instances do not have inside, environment, and peer refs filled in.
     We do it now.
  *)
  L.log_always L.ConsGen "Fixing up temporary instances" ;
  List.iter (fix_up_tmp_instances (pmodel, id_node_tbl, node_id_tbl))  topo_list ;
  L.log_always L.ConsGen "done Fixing up temporary instances" ;
 
  (pmodel, node_id_tbl, id_node_tbl, topo_list)


