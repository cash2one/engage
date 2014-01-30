(* Copyright 2009 by Genforma. All Rights Reserved. *)
(** Resource pretty printer. The main entry points are:
 *  make_pp_state - initialize a state object for this module, giving it
 *                  an output function.
 *  pp_resource_library - pretty-print a resource definition library.
 *  pp_resource_inst_list - prrety-print a list of resource instances
 *
 *)

open Str

open Resources
open Json

exception InternalError of string

type pp_state = {
  output_fn : string -> unit;
  mutable indent_level : int;
}

let make_pp_state (output_fn:string->unit) :pp_state =
  {output_fn=output_fn; indent_level=0;}

let _indents = [| ""; "  "; "    "; "      "; "        "; "          "|]

let indent_str (pp_state:pp_state) :string =
  if pp_state.indent_level < 6 then _indents.(pp_state.indent_level)
  else begin
  let str = ref "          " in
    for i = 6 to pp_state.indent_level do
      str := !str ^ "  "
    done;
    !str
  end

(* adjust the indentation level in by 2 and return a new indentation string *)
let indent_in (pp_state:pp_state) :string =
  pp_state.indent_level <- pp_state.indent_level + 1;
  indent_str pp_state

let indent_out (pp_state:pp_state) :unit =
  pp_state.indent_level <- pp_state.indent_level - 1

let quote_str str =
  "\"" ^ str ^ "\""

let quote_prop str =
  "\"" ^ str ^ "\": "


(* Print a list of items using prt_fn, separating with the specified
   separator sting. *)
let pp_sep_list (prt_fn:'a->pp_state->unit) (sep:string) (list:'a list)
                (pp_state:pp_state) :unit =
  let first = ref true in
    List.iter (fun item ->
                 (if not !first then pp_state.output_fn sep
                  else first := false);
                 prt_fn item pp_state) list

(** Adds an indent level.
    Then print a list of things, separting them with comma, newline, and the
    necessary indentation. Finally, restores the original indent level.
*)
let pp_indented_list (prt_fn:'a->pp_state->unit) (list:'a list)
                     (pp_state:pp_state) :unit =
  let indent_str = indent_in pp_state in
    begin
      pp_state.output_fn indent_str;
      pp_sep_list prt_fn (",\n" ^ indent_str) list pp_state;
      indent_out pp_state
    end


let pp_multiline_map ?(quote_keys = true) (value_prt_fn:'v->unit)
                     (iter_fn:((symbol*'v)->unit)->'c->unit)
                     (collection:'c) (pp_state:pp_state)
                     :unit =
  pp_state.output_fn "{";
  let body_indent = indent_in pp_state
  and first = ref true in
    begin
      iter_fn (fun (key, value) ->
                 if not !first then pp_state.output_fn (",\n"^body_indent)
                 else (first := false; pp_state.output_fn ("\n"^body_indent));
                 if quote_keys then pp_state.output_fn ("\"" ^ key ^ "\": ")
                 else pp_state.output_fn (key ^ ": ");
                 (value_prt_fn value)) collection;
      indent_out pp_state;
      if not (!first) then pp_state.output_fn ("\n"^(indent_str pp_state)^"}")
      else pp_state.output_fn " }"
    end

let pp_multiline_list (value_prt_fn:'v->unit)
                      (iter_fn:('v->unit)->'c->unit)
                     (collection:'c) (pp_state:pp_state) :unit =
  pp_state.output_fn "[\n";
  let body_indent = indent_in pp_state in
    begin
      pp_state.output_fn body_indent;
      let first = ref true in
        iter_fn (fun value ->
                 (if not !first then pp_state.output_fn (",\n"^body_indent)
                  else first := false);
                   (value_prt_fn value)) collection;
    end;
    indent_out pp_state;
    pp_state.output_fn ("\n" ^ (indent_str pp_state) ^ "]")


(** This iterator looks like a list iterator, but works on a symbol map *)
let symmap_iter_fn (fn:(symbol*'v)->unit) (collection:'v SymbolMap.t) :unit =
  SymbolMap.iter (fun key value -> fn (key, value)) collection


(** Function to pretty print a json value *)
let rec pp_json (json_value:json_value) (pp_state:pp_state) :unit =
  match json_value with
      JsonScalar sc -> pp_state.output_fn (string_of_scalar_val sc)
    | JsonMap map ->
        pp_multiline_map (fun jv -> pp_json jv pp_state) symmap_iter_fn map
          pp_state
    | JsonList lst ->
        pp_multiline_list (fun jv -> pp_json jv pp_state)
          List.iter lst pp_state

let rec pp_json_value (value:json_value) (pp_state:pp_state) :unit =
    match value with
        JsonScalar s -> pp_state.output_fn (string_of_scalar_val s)
      | JsonList l ->
          pp_multiline_list (fun jv -> pp_json_value jv pp_state)
            List.iter l pp_state
      | JsonMap m -> pp_json_map m pp_state
and pp_json_map (map:json_map) (pp_state:pp_state) :unit =
  pp_multiline_map ~quote_keys:true
    (fun jv -> pp_json_value jv pp_state) symmap_iter_fn map pp_state

let pp_key ?(quote_property_names=true)
           (key_def:(symbol*scalar_val) list) (pp_state:pp_state) :unit=
  pp_state.output_fn "{";
  pp_sep_list (fun (name, scalar_val) pp_state ->
                 let prop_name =
                   if quote_property_names then "\"" ^ name ^ "\"" else name in
                   pp_state.output_fn (prop_name ^ ": " ^
                                         (string_of_scalar_val scalar_val)))
    ", " key_def pp_state;
  pp_state.output_fn "}"

let rec prop_type_to_json_val (prop_type:type_decl) :json_value =
  match prop_type with
      ScalarType sym -> JsonScalar (String sym)
    | EnumType l -> JsonList (List.map (fun s -> JsonScalar (String s)) l) 
    | ListType td -> JsonList [(prop_type_to_json_val td)]
    | MapType td_prop_lst ->
        JsonMap
          (List.fold_left
             (fun map (name, td) ->
                SymbolMap.add name (prop_type_to_json_val td) map)
             SymbolMap.empty td_prop_lst)

let rec initial_val_to_json_val (initial_val:initial_val) :json_value =
  match initial_val with
      ScalarInitialVal sc -> JsonScalar sc
    | MapInitialVal prop_list ->
        JsonMap
          (List.fold_left
             (fun map (name, iv) ->
                SymbolMap.add name (initial_val_to_json_val iv) map)
             SymbolMap.empty prop_list)
    | ListInitialVal iv_list ->
        JsonList (List.map initial_val_to_json_val iv_list)
    | PortReference pr ->
        raise
          (InternalError
             "Should not encounter port reference in an initial value")
    | TemplateInitialVal (tmpl, vars) -> JsonScalar (String tmpl)

let extract_initial_val (kind:initial_val_kind)
    :(initial_val*string) option =
  match kind with
      Default v -> Some (v, Keywords.default)
    | Fixed v -> Some (v, Keywords.fixed_value)
    | Includes v -> Some (v, Keywords.includes)
    | NoInitialVal -> None

let pp_property_def (pdef:property_def) (port_type:port_type)
                    (pp_state:pp_state) :unit =
  pp_state.output_fn (quote_prop pdef.property_name);
  match (pdef.property_type, extract_initial_val pdef.property_val) with
      (ScalarType s, None) ->
        (* special case for scalar types when there isn't an initial value *)
        pp_state.output_fn (quote_str s)
    | (_, None) ->
        let type_json = prop_type_to_json_val pdef.property_type in
          pp_json
            (JsonMap (Utils.make_map [(Keywords.prop_type, type_json)]))
            pp_state
    | (_, Some (PortReference (ConfigPortRef (pr)), kw)) ->
        let type_json = prop_type_to_json_val pdef.property_type in
          pp_json
            (JsonMap
               (Utils.make_map
                  [(kw,
                    JsonScalar (String (Utils.join
                                          (Keywords.config_port::pr) ".")));
                  (Keywords.prop_type, type_json)]))
            pp_state
    | (_, Some (PortReference (InputPortRef (pn, pr)), kw)) ->
        let type_json = prop_type_to_json_val pdef.property_type in
          pp_json
            (JsonMap
               (Utils.make_map
                  [(kw,
                    JsonScalar (String (Utils.join
                                         (Keywords.input_ports::pn::pr) ".")));
                   (Keywords.prop_type, type_json)]))
          pp_state
    | (_, Some (initial_val, kw)) -> begin
        let type_json = prop_type_to_json_val pdef.property_type
        and initial_val_json = initial_val_to_json_val initial_val in
        let json_map = Utils.make_map [(Keywords.prop_type, type_json);
                                       (kw, initial_val_json)]
        in pp_json (JsonMap json_map) pp_state
      end

let pp_port_def (prop_defs:property_def list) (port_type:port_type)
                (pp_state:pp_state) :unit =
  pp_state.output_fn "{\n";
  pp_indented_list (fun pdef pp_state ->
                      pp_property_def pdef port_type pp_state)
    prop_defs pp_state;
  pp_state.output_fn ("\n" ^ (indent_str pp_state) ^"}")

let pp_ports (port_type:port_type) (ports:port_def_map)
                (pp_state:pp_state) :unit =
  pp_state.output_fn ((indent_str pp_state) ^
                      (quote_prop (string_of_port_type port_type)));
  pp_multiline_map (fun port_def -> pp_port_def port_def port_type pp_state)
    symmap_iter_fn ports pp_state

(** We always print the key constraints on one line *)
let pp_key_constraints (constraints:key_constraint list) (pp_state:pp_state)
                       :unit =
  let constraint_map =
    List.fold_left
      (fun map key_constraint ->
         let add_key name relop value =
           if SymbolMap.mem name map then
             let relmap = cast_to_map (SymbolMap.find name map) in
               SymbolMap.add name
                 (JsonMap (SymbolMap.add relop (JsonScalar value) relmap)) map
           else
             SymbolMap.add name
               (JsonMap (SymbolMap.add relop (JsonScalar value)
                           SymbolMap.empty)) map
         in
           match key_constraint with
                 KeyEq (name, value) ->
                   SymbolMap.add name (JsonScalar value) map
               | KeyGt (name, value) ->
                   add_key name Keywords.greater_than value
               | KeyGeq (name, value) ->
                   add_key name Keywords.greater_than_or_equal value
               | KeyLeq (name, value) ->
                   add_key name Keywords.less_than_or_equal value
               | KeyLt (name, value) ->
                   add_key name Keywords.less_than value)
      SymbolMap.empty constraints
  in pp_json (JsonMap constraint_map) pp_state

let pp_port_mapping (port_mapping:symbol SymbolMap.t) (pp_state:pp_state)
                    :unit =
  pp_multiline_map (fun symbol -> pp_state.output_fn ("\"" ^ symbol ^ "\""))
    symmap_iter_fn port_mapping pp_state

let pp_atomic_constraint (ac:atomic_constraint) (pp_state:pp_state) :unit =
  if ac.port_mapping <> SymbolMap.empty then begin
    let body_indent = indent_in pp_state in
      pp_state.output_fn ("{\n" ^ body_indent ^ (quote_prop Keywords.key));
      pp_key_constraints ac.key_constraints pp_state;
      pp_state.output_fn (",\n" ^ body_indent ^
                            (quote_prop Keywords.port_mapping));
      pp_multiline_map (fun symbol -> pp_state.output_fn ("\"" ^ symbol ^ "\""))
        symmap_iter_fn ac.port_mapping pp_state;
      indent_out pp_state;
      pp_state.output_fn ("\n" ^ (indent_str pp_state) ^ "}")
  end
  else begin
    (* no port mappings, just print on one line *)
    pp_state.output_fn ("{" ^ (quote_prop Keywords.key));
    pp_key_constraints ac.key_constraints pp_state;
    pp_state.output_fn "}"
  end

let pp_choice_constraint (cc:choice_constraint) (pp_state:pp_state) :unit =
  match cc with
      AtomicConstraint ac -> pp_atomic_constraint ac pp_state
    | OneOfConstraint ac_list -> begin
        pp_state.output_fn ("{ " ^ (quote_prop Keywords.one_of) ^ "[\n");
        pp_indented_list pp_atomic_constraint ac_list pp_state;
        pp_state.output_fn ("\n" ^ (indent_str pp_state) ^ "] }")
      end

let pp_compound_constraint (cp:compound_constraint) (pp_state:pp_state) :unit =
  match cp with
      ChoiceConstraint choice -> pp_choice_constraint choice pp_state
    | AllOfConstraint cp_list -> begin
        pp_state.output_fn ("{ " ^ (quote_prop Keywords.all_of) ^ "[\n");
        pp_indented_list pp_choice_constraint cp_list pp_state;
        pp_state.output_fn ("\n" ^ (indent_str pp_state) ^ "] }")
      end

let pp_user_data ?(quote_keys = true) (value_prt_fn:'v->unit)
                     (iter_fn:((symbol*'v)->unit)->'c->unit)
                     (collection:'c) (pp_state:pp_state)
                     :unit =
  let first = ref true in
    begin
      let body_indent = indent_str pp_state in
      iter_fn (fun (key, value) ->
                 if not !first then pp_state.output_fn (",\n"^body_indent)
                 else (first := false; pp_state.output_fn ("\n"^body_indent));
                 if quote_keys then pp_state.output_fn ("\"" ^ key ^ "\": ")
                 else pp_state.output_fn (key ^ ": ");
                 (value_prt_fn value)) collection;
      ()
    end

(** Pretty print a resource definition *)
let pp_resource_def (rdef:resource_def) (pp_state:pp_state) :unit =
  pp_state.output_fn ((indent_str pp_state) ^ "{\n");
  let body_indent = indent_in pp_state in begin
      pp_state.output_fn (body_indent ^ (quote_prop Keywords.key));
      pp_key rdef.key pp_state;
      pp_state.output_fn ",\n";
      if rdef.user_data_def <> SymbolMap.empty then begin
          pp_user_data ~quote_keys:true (fun jv -> pp_json_value jv pp_state) symmap_iter_fn rdef.user_data_def pp_state
      end ;
      pp_state.output_fn (",\n" ^ body_indent ^
                            (quote_prop Keywords.config_port));
      pp_port_def rdef.config_port_def ConfigPort pp_state;
      pp_state.output_fn ",\n";
      pp_ports InputPort rdef.input_port_defs pp_state;
      pp_state.output_fn ",\n";
      pp_ports OutputPort rdef.output_port_defs pp_state;
      (match rdef.inside with
           Some cc ->
             pp_state.output_fn (",\n" ^ body_indent ^
                                   (quote_prop Keywords.inside));
             pp_choice_constraint cc pp_state
         | None -> ());
      (match rdef.environment with
           Some cp ->
             pp_state.output_fn (",\n" ^ body_indent ^
                                   (quote_prop Keywords.environment));
             pp_compound_constraint cp pp_state
         | None -> ());
      (match rdef.peers with
           Some cp ->
             pp_state.output_fn (",\n" ^ body_indent ^
                                   (quote_prop Keywords.peers));
             pp_compound_constraint cp pp_state
         | None -> ());
      pp_state.output_fn "\n"
    end;
    indent_out pp_state;
    pp_state.output_fn ((indent_str pp_state) ^ "}")

(** main entry point for printing resource libraries *)
let pp_resource_library (rdef_list:resource_def list) (pp_state:pp_state) :unit=
  pp_state.output_fn ((indent_str pp_state) ^ "{ \"" ^
                        Keywords.resource_def_version ^ "\":\"" ^
                        Resources.grammar_version ^ "\",\n");
  let body_indent = indent_in pp_state in begin
      let fst_resource = ref true in
        pp_state.output_fn (body_indent ^ "\"" ^
                              Keywords.resource_definitions ^ "\": [\n");
        ignore (indent_in pp_state);
        List.iter
          (fun rdef ->
             if !fst_resource then fst_resource :=false
             else pp_state.output_fn ",\n";
             pp_resource_def rdef pp_state)
        rdef_list;
      indent_out pp_state;
      pp_state.output_fn ("\n" ^ body_indent ^ "]\n");
    end;
    indent_out pp_state;
    pp_state.output_fn ((indent_str pp_state) ^ "}\n")

let pp_resource_port (port:json_map) (pp_state:pp_state) :unit =
  pp_multiline_map ~quote_keys:true (fun value -> pp_json_value value pp_state)
    symmap_iter_fn port pp_state

let pp_resource_ports (port_map:json_map SymbolMap.t)
                      (pp_state:pp_state) :unit =
    pp_multiline_map ~quote_keys:true
      (fun port -> pp_resource_port port pp_state) symmap_iter_fn port_map
      pp_state

let pp_resource_ref (resource_ref:resource_ref) (pp_state:pp_state) :unit =
  let body_indent = indent_in pp_state in begin
      pp_state.output_fn ("{\n" ^ body_indent ^  "\"id\": \"" ^
                            resource_ref.ref_id ^ "\",\n");
      pp_state.output_fn (body_indent ^ "\"key\": ");
      pp_key ~quote_property_names:true resource_ref.ref_key pp_state;
      if resource_ref.ref_port_mapping <> SymbolMap.empty then begin
        pp_state.output_fn (",\n" ^ body_indent ^ "\"port_mapping\": ");
        pp_multiline_map ~quote_keys:true
          (fun port -> pp_state.output_fn ("\"" ^ port ^ "\"")) symmap_iter_fn
          resource_ref.ref_port_mapping pp_state
      end
    end;
    indent_out pp_state;
    pp_state.output_fn ("\n" ^ (indent_str pp_state) ^ "}")

let pp_resource_inst (rinst:resource_inst) (pp_state:pp_state) :unit =
  pp_state.output_fn ("{ \"id\": \"" ^ rinst.id ^ "\",\n");
  let body_indent = indent_in pp_state in begin
      pp_state.output_fn (body_indent ^ "\"key\": ");
      pp_key ~quote_property_names:true rinst.resource_key pp_state;
      (match rinst.properties with
           Some json_map -> begin
             pp_state.output_fn (",\n" ^ body_indent ^ "\"properties\": ");
             pp_json_map json_map pp_state
           end
         | None -> ());
      if rinst.user_data <> SymbolMap.empty then begin
        pp_state.output_fn (",\n" ^ body_indent);
        pp_user_data ~quote_keys:true (fun jv -> pp_json_value jv pp_state) symmap_iter_fn rinst.user_data pp_state
      end;
      if rinst.config_port <> SymbolMap.empty then begin
        pp_state.output_fn (",\n" ^ body_indent ^ "\"config_port\": ");
        pp_resource_port rinst.config_port pp_state
      end;
      if rinst.input_ports <> SymbolMap.empty then begin
        pp_state.output_fn (",\n" ^ body_indent ^ "\"input_ports\": ");
        pp_resource_ports rinst.input_ports pp_state
      end;
      if rinst.output_ports <> SymbolMap.empty then begin
        pp_state.output_fn (",\n" ^ body_indent ^ "\"output_ports\": ");
        pp_resource_ports rinst.output_ports pp_state
      end;
      (match rinst.inside_ref with
           Some rr -> begin
             pp_state.output_fn (",\n" ^ body_indent ^ "\"inside\": " );
             pp_resource_ref rr pp_state
           end
         | _ -> ());
      (match rinst.environment_refs with
           hd::rest -> begin
             pp_state.output_fn (",\n" ^ body_indent ^ "\"environment\": " );
             pp_multiline_list (fun rr -> pp_resource_ref rr pp_state) List.iter
               rinst.environment_refs pp_state
           end
         | [] -> ());
      (match rinst.peer_refs with
           hd::rest -> begin
             pp_state.output_fn (",\n" ^ body_indent ^ "\"peers\": " );
             pp_multiline_list (fun rr -> pp_resource_ref rr pp_state) List.iter
               rinst.peer_refs pp_state
           end
         | [] -> ())
    end;
    indent_out pp_state;
    pp_state.output_fn ("\n" ^ (indent_str pp_state) ^ "}")

(** main entry point for printing resource instances *)
let pp_resource_inst_list (rinst_list:resource_inst list) (pp_state:pp_state)
    :unit =
  pp_state.output_fn (indent_str pp_state);
  pp_multiline_list (fun rinst -> pp_resource_inst rinst pp_state)
    List.iter rinst_list pp_state;
  pp_state.output_fn "\n"

let pp_user_error (l,e,u,d,c) pp_state =
  let json_of_user_error =
    let smap1 = SymbolMap.add "logarea" (JsonScalar (String (Logging.log_area_to_string l))) (SymbolMap.empty) in
    let smap2 = SymbolMap.add "errorcode" (JsonScalar (Integer e)) smap1 in
    let smap3 = SymbolMap.add "usererror" (JsonScalar (String u)) smap2 in
    let smap4 = SymbolMap.add "deverror" (JsonScalar (String d)) smap3 in
    let smap5 = SymbolMap.add "context" (JsonList (List.map (fun s -> JsonScalar (String s)) c)) smap4 in
    JsonMap smap5
  in
  pp_json json_of_user_error pp_state

(** Utility fn which returns a function to append strings to a string ref *)
let output_to_str (strref: string ref) :(string->unit) =
  fun s -> strref := !strref ^ s

let string_of_json jv =
  let sref = ref "" in
  pp_json jv (make_pp_state (output_to_str sref)) ;
  !sref

let string_of_key key =
  let sref = ref "" in
  pp_key key (make_pp_state (output_to_str sref));
  !sref

let format_key_for_resource_id (key:(symbol*scalar_val) list) :string =
  let r = Str.regexp "-\\| \\|\\." in (* match dash, space, or period *)
  let format_val sv =
    Str.global_replace r "_" 
      (match sv with
           Integer i -> string_of_int i
         | String s -> s
         | Boolean true -> "true"
         | Boolean false -> "false"
         | Null -> "null")
  in
  let name = format_val (List.assoc "name" key) and
      version = format_val (List.assoc "version" key) in
    name ^ "__" ^ version

