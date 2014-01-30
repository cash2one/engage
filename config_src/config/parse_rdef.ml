(** Parse the new-style resource definitions, which are encoded in JSON *)

open Resources
open Json

exception RdefParseError of string

let filename = ref None

let raise_error (err_ctx:string) (msg:string) =
  match !filename with
    Some fn ->
          raise (RdefParseError
                   ("Error in parsing resource library file '" ^ fn ^
                      "' at " ^ err_ctx ^ ": " ^ msg))
      | None ->
          raise (RdefParseError
                   ("Resource library parse error at " ^ err_ctx ^
                      ": " ^ msg))

let do_cast (cast_fn:json_value->'v) (v:'json_value) (err_ctx:string) :'v =
  try
    cast_fn v
  with CastError (exp, act) ->
    raise_error err_ctx ("expecting type " ^ exp ^ ", instead found " ^ act)


let get_json_property (prop_name:string) (map:json_map)
                      (cast_fn:json_value->'v) (err_ctx:string) :'v =
  try
    cast_fn (SymbolMap.find prop_name map)
  with Not_found ->
    raise_error err_ctx ("required property " ^ prop_name ^ " not found")
    | CastError (exp, act) ->
        raise_error err_ctx
          ("property " ^ prop_name ^ " has wrong type " ^
              act ^ ", was expecting " ^ exp)


let get_opt_json_property (prop_name:string) (map:json_map)
                          (cast_fn:json_value->'v) (err_ctx:string)
                          (default:'v) :'v =
  try
    cast_fn (SymbolMap.find prop_name map)
  with Not_found -> default
    | CastError (exp, act) ->
        raise_error err_ctx
          ("property " ^ prop_name ^ " has wrong type " ^
              act ^ ", was expecting " ^ exp)

let parse_key (key_container:json_map) (err_ctx:string)
              :(symbol*scalar_val) list =
  let key_map = get_json_property Keywords.key key_container cast_to_map
                  err_ctx in
  let list =
    SymbolMap.fold
      (fun name v list ->
         let s = do_cast cast_to_scalar v (err_ctx ^ " key property " ^ name) in (name, s)::list)
      key_map []
  in match list with
      [] -> raise_error err_ctx "Key map is empty"
    | _ -> List.rev list


let string_of_key (key:(symbol*scalar_val) list) :string =
  "{" ^
    (List.fold_left
       (fun str (sym, value) ->
          let entry = "\"" ^ sym ^ "\":" ^ (string_of_scalar_val value)
          in if str="" then entry
            else str ^ ", " ^ entry) "" key)
    ^ "}"


let rec parse_prop_type (json:json_value) (err_ctx:string) :type_decl =
  match json with
      JsonScalar (String s) -> ScalarType s
    | JsonMap m ->
        if SymbolMap.mem "enum" m then
          match (SymbolMap.find "enum" m) with
          | JsonList l -> 
            let l' = List.map (fun s -> 
              match s with JsonScalar (String str) -> str
              | _ -> raise_error err_ctx ("enumerated type should be a string list")) 
              l
            in
            EnumType l'
          | _ -> raise_error  err_ctx ("Enumerated type is not a list of JSON")
        else
          MapType (SymbolMap.fold
                   (fun prop_name json lst ->
                      (prop_name, parse_prop_type json err_ctx)::lst)
                   m [])
    | JsonList l -> begin
        match l with
            [typ] -> ListType (parse_prop_type typ err_ctx)
          | _ ->
              raise_error err_ctx
                "List types should have exactly one member"
      end
    | _ ->
        raise_error err_ctx
          ("property type should be a string or a map, instead found " ^
             (type_of_json_value json))


let parse_port_reference (json:json_value) (err_ctx:string) :port_reference =
  let ref_str = do_cast cast_to_symbol json err_ctx in
    try
      match Utils.split ref_str '.' with
          port_type::name::[] ->
            if port_type=Keywords.config_port then
              ConfigPortRef (name::[])
            else raise Not_found
        | port_type::name1::name2::rst ->
            if port_type=Keywords.config_port then
              ConfigPortRef (name1::name2::rst)
            else (if port_type=Keywords.input_ports then
                    InputPortRef (name1, (name2::rst))
                  else raise Not_found)
        | _ -> raise Not_found
    with Not_found ->
      raise_error err_ctx ("invalid port reference: '" ^ ref_str)


let rec parse_property_value (json:json_value) (prop_type:type_decl) err_ctx
 :initial_val =
  match (json, prop_type) with
    | (JsonScalar (String s), typ) -> begin
        match Templates.parse_string s with
            Templates.String s -> ScalarInitialVal (String s)
          | Templates.Reference r ->
              PortReference (parse_port_reference (JsonScalar (String r))
                               err_ctx)
          | Templates.Template (t, sl) -> TemplateInitialVal (t, sl)
      end
    | (JsonScalar sc, ScalarType _) ->
        (* For now, we don't check the values of scalars against their declared
           types. We would need some subtyping relationship (e.g. to say that
           a port is a subtype of an int *)
        ScalarInitialVal sc
    | (JsonMap m, ScalarType "map") ->
        let rec compute_val m =
          SymbolMap.fold (fun k v sofar -> 
            let v' = match v with
                     | JsonMap m' -> MapInitialVal (compute_val m')
                     | JsonScalar sv -> ScalarInitialVal sv
                     | JsonList l -> assert false 
            in
            (k,v') :: sofar) m []
        in
        MapInitialVal (compute_val m)
    | (JsonScalar (String sc), EnumType l) ->
        if not (List.mem sc l) then raise_error err_ctx ("Value not found in enumerated type")
        else
          ScalarInitialVal (String sc)
    | (JsonMap m, MapType prop_list) ->
        (* For now we ignore any properties that aren't in the declared type *)
        MapInitialVal
          (List.map
             (fun (prop_name, prop_type) ->
                if not (SymbolMap.mem prop_name m) then
                  raise_error err_ctx ("Expected property " ^ prop_name ^
                                         " missing");
                (prop_name,
                 (parse_property_value (SymbolMap.find prop_name m) prop_type
                    err_ctx))) prop_list)
    | (JsonList l, ListType typ) ->
        ListInitialVal
          (List.map
             (fun json_val -> parse_property_value json_val typ err_ctx) l)
    | _ -> raise_error err_ctx "Property value does not match expected type"



let parse_prop_initialization (map:json_map) (prop_type:type_decl)
                              (port_type:port_type) (err_ctx:string)
                              :initial_val option =
  match (SymbolMap.mem Keywords.source map,
         SymbolMap.mem Keywords.fixed_value map,
         SymbolMap.mem Keywords.default map,
         SymbolMap.mem Keywords.includes map) with
      (true, false, false, false) ->
        if not (is_output_port port_type) then
          raise_error err_ctx
            "'source' property only valid for output ports"
        else
          Some
            (PortReference
               (parse_port_reference (SymbolMap.find Keywords.source map) err_ctx))
    | (false, true, false, false) ->
        if is_output_port port_type then
          Some (parse_property_value (SymbolMap.find Keywords.fixed_value map)
                  prop_type err_ctx)
        else
          raise_error err_ctx
            "'fixed-value' property only valid for output ports"
    | (false, false, true, false) ->
        if not (is_config_port port_type) then
          raise_error err_ctx
            "'default' property only valid for config ports"
        else
          Some (parse_property_value (SymbolMap.find Keywords.default map)
                  prop_type err_ctx)
    | (false, false, false, true) ->
        if not (is_input_port port_type) then
          raise_error err_ctx
            "'includes' property only valid for input ports"
        else
          Some (parse_property_value (SymbolMap.find Keywords.includes map)
                  prop_type err_ctx)
    | (false, false, false, false) -> None
    | _ ->
        raise_error err_ctx
          "Invalid definition of property value: should have only one of 'source', 'fixed-value', or 'includes', 'default'"


let parse_port_def (json:json_map) (port_type:port_type) (err_ctx:string)
                   :property_def list =
  SymbolMap.fold
    (fun prop_name json lst ->
       let err_ctx = err_ctx ^ " property '" ^ prop_name ^ "'" in
       let err_ctx = err_ctx ^ " json :: " ^ (Resource_pp.string_of_json json) in
         match json with
             JsonScalar (String s) ->
               {property_name=prop_name;
                property_display_name=None ;
                property_help= None ;
                property_type=ScalarType s ;
                property_val=NoInitialVal;}::lst
           | JsonMap map -> begin
               let property_type =
                 try
                   parse_prop_type (SymbolMap.find Keywords.prop_type map)
                     err_ctx
                 with Not_found ->
                   raise_error err_ctx
                     "type property missing in property definition"
               in let property_display_name =
                 get_opt_json_property Keywords.property_display_name
                   map cast_to_string_option err_ctx None
               in let property_help =
                 get_opt_json_property Keywords.property_help
                   map cast_to_string_option err_ctx None
               in let property_value =
                   parse_prop_initialization map property_type port_type
                     err_ctx
               in let property_kind =
                   match (property_value, port_type) with
                       (None, _) -> NoInitialVal
                     | (Some v, ConfigPort) -> Default v
                     | (Some v, InputPort) -> Includes v
                     | (Some v, OutputPort) -> Fixed v
               in  ({property_name=prop_name;
                     property_display_name= property_display_name ;
                     property_help= property_help ;
                     property_type=property_type;
                     property_val=property_kind;})::lst
             end
           | _ -> raise_error err_ctx
               ("Property definition should be a map, instead was " ^
                  (type_of_json_value json)))
    json []

let parse_port_def_map (json:json_map) (port_type:port_type) (err_ctx:string) (lut: port_def_map)
    :port_def_map =
  SymbolMap.fold
    (fun port_name port_json map ->
       let err_ctx = err_ctx ^ " port '" ^ port_name ^ "'" in
       let port_val = 
         if type_of_json_value port_json = "string" then
           let s = (do_cast cast_to_symbol port_json err_ctx) in
           let slist = Utils.split s '.' in
           match slist with
           | p_type :: name :: _ ->
             if p_type = Keywords.input_ports then
             begin
               try SymbolMap.find name lut
               with Not_found ->
                 raise_error err_ctx ("String value " ^ s ^ " not found in property table") 
             end 
             else raise_error err_ctx ("String " ^ s ^ " is not an input port reference")
           | _ -> raise_error err_ctx ("String " ^ s ^ " is not an input port reference")
         else 
           let port_json_map = do_cast cast_to_map port_json err_ctx in
           (parse_port_def port_json_map port_type err_ctx) 
       in 
       SymbolMap.add port_name port_val map)
    json SymbolMap.empty


let parse_key_constraint (key_prop:string) (json:json_value) (err_ctx:string)
                         :key_constraint list =
  let err_ctx = err_ctx ^ " key constraint for property '" ^ key_prop ^ "'" in
    match json with
        JsonScalar sc -> [KeyEq (key_prop, sc)]
      | JsonMap map -> begin
          SymbolMap.fold
            (fun (rel_op:string) compare_val lst ->
               let compare_val_scalar =
                 do_cast cast_to_scalar compare_val err_ctx in
               let comparison =
                 if rel_op = Keywords.less_than then
                   KeyLt (key_prop, compare_val_scalar)
                 else if rel_op = Keywords.greater_than then
                   KeyGt (key_prop, compare_val_scalar)
                 else if rel_op = Keywords.greater_than_or_equal then
                   KeyGeq (key_prop, compare_val_scalar)
                 else if rel_op = Keywords.less_than_or_equal then
                   KeyLeq (key_prop, compare_val_scalar)
                 else
                   (raise_error err_ctx
                     ("Invalid relational operator '" ^ rel_op ^ "'"))
               in comparison::lst) map []
        end
      | _ ->
          raise_error err_ctx
            "Key constraints should be either a string or a map"

let parse_key_constraints (json_map:json_map) (err_ctx:string)
    :key_constraint list =
    SymbolMap.fold
      (fun prop_name json_val result_lst ->
         (parse_key_constraint prop_name json_val err_ctx) @ result_lst)
      json_map []


let parse_port_mapping (json_map:json_map) (err_ctx:string) :symbol SymbolMap.t =
  let err_ctx = err_ctx ^ " port mapping" in
    SymbolMap.fold
      (fun input_port output_port_json result_map ->
         let output_port = do_cast cast_to_symbol output_port_json err_ctx in
           SymbolMap.add input_port output_port result_map)
      json_map SymbolMap.empty


let parse_atomic_constraint (json_map:json_map) (err_ctx:string)
    :atomic_constraint =
  let key_constraints =
    parse_key_constraints
      (get_json_property Keywords.key json_map cast_to_map err_ctx) err_ctx
  and port_mapping =
    parse_port_mapping
      (get_opt_json_property Keywords.port_mapping json_map cast_to_map err_ctx
         SymbolMap.empty) err_ctx
  in {key_constraints=key_constraints; port_mapping=port_mapping;}

let parse_choice_constraint (json_map:json_map) (err_ctx:string)
    :choice_constraint =
  if SymbolMap.mem Keywords.one_of json_map then
    begin
      let constraint_list =
        get_json_property Keywords.one_of json_map cast_to_list err_ctx in
      OneOfConstraint
        (List.map
           (fun json ->
              let map = do_cast cast_to_map json err_ctx in
                parse_atomic_constraint map err_ctx) constraint_list)
    end
  else AtomicConstraint (parse_atomic_constraint json_map err_ctx)

let parse_compound_constraint (json_map:json_map) (err_ctx:string)
    :compound_constraint =
  match (SymbolMap.mem Keywords.all_of json_map,
         SymbolMap.mem Keywords.one_of json_map) with
      (true, false) ->
        let constraint_list =
          get_json_property Keywords.all_of json_map cast_to_list err_ctx
        in
          AllOfConstraint
            (List.map
               (fun constraint_json ->
                  let map = do_cast cast_to_map constraint_json err_ctx in
                    parse_choice_constraint map err_ctx)
             constraint_list)
    | (false, true) | (false, false) ->
        ChoiceConstraint (parse_choice_constraint json_map err_ctx)
    | (true, true) ->
        raise_error err_ctx
          "Constraint definition cannot contain both one-of and all-of constraints"

(* helper to see if the resource definition contains the specified property
   and, if so, that it is a non-emtpy map. Raises an error if the property
   exists but is the wrong type *)
let has_nonempty_map_prop (prop_name:string) (rdef_map:json_map)
                          (err_ctx:string) :bool =
  try
    let prop_val = SymbolMap.find prop_name rdef_map in
    let map =  do_cast cast_to_map prop_val err_ctx in
      not (SymbolMap.is_empty map)
  with Not_found -> false


let rdef_no = ref 0

let parse_rdef (json:json_value) :resource_def =
  let err_ctx = "resource definition " ^ (string_of_int !rdef_no) in
  let rdef_json = do_cast cast_to_map json err_ctx
  in let key = parse_key rdef_json err_ctx
  in let err_ctx = "resource definition " ^ (string_of_key key)
  in let display_name = get_json_property Keywords.display_name rdef_json cast_to_symbol err_ctx
  in let err_ctx = "resource definition " ^ display_name
  in let config_port =
      begin
        let err_ctx = err_ctx ^ " configuration port" in
          parse_port_def (get_opt_json_property Keywords.config_port rdef_json
                            cast_to_map err_ctx SymbolMap.empty)
            ConfigPort err_ctx
      end
  and input_port_defs =
      begin
        let err_ctx = err_ctx ^ " input ports" in
          parse_port_def_map (get_opt_json_property Keywords.input_ports rdef_json
                                cast_to_map err_ctx SymbolMap.empty)
            InputPort err_ctx
            (SymbolMap.empty)
      end
  in let output_port_defs =
      begin
        let err_ctx = err_ctx ^ " output ports" in
          parse_port_def_map (get_opt_json_property Keywords.output_ports rdef_json
                                cast_to_map err_ctx SymbolMap.empty)
            OutputPort err_ctx
            input_port_defs
      end
  and inside =
      begin
        let err_ctx = err_ctx ^ " inside constraint" in
          if (has_nonempty_map_prop Keywords.inside rdef_json err_ctx) then
            Some (parse_choice_constraint
                    (get_json_property Keywords.inside rdef_json cast_to_map
                       err_ctx) err_ctx)
        else None
      end
  and environment =
      begin
        let err_ctx = err_ctx ^ " environment constraint" in
          if (has_nonempty_map_prop Keywords.environment rdef_json err_ctx) then
            Some (parse_compound_constraint
                    (get_json_property Keywords.environment rdef_json
                       cast_to_map err_ctx)
                    err_ctx)
        else None
      end
  and peers =
      begin
        let err_ctx = err_ctx ^ " peers constraint" in
          if (has_nonempty_map_prop Keywords.peers rdef_json err_ctx) then
            Some (parse_compound_constraint
                    (get_json_property Keywords.peers rdef_json
                       cast_to_map err_ctx)
                    err_ctx)
        else None
      end
  and user_data = (* additional information that a user might stick into a resource def. Copy these along. *)
      begin 
        let err_ctx = err_ctx ^ " user data " in
        let keywords = Keywords.to_list() in 
        let ud = 
          SymbolMap.fold (fun k v ud -> 
            if List.mem k keywords then ud else SymbolMap.add k v ud ) rdef_json SymbolMap.empty 
        in
        ud 
      end
  in rdef_no := !rdef_no + 1;
    {key=key; display_name = display_name ; config_port_def=config_port;
     input_port_defs=input_port_defs;
     output_port_defs=output_port_defs;
      inside=inside; environment=environment; peers=peers; user_data_def=user_data; }

let parse_rdef_library (json:json_value) : resource_def list =
    let library = do_cast cast_to_map json "resource library definition" in
    let file_version =
      get_json_property "resource_def_version" library cast_to_symbol
        "resource library definition"
    and rdef_json_list =
      get_json_property "resource_definitions" library cast_to_list
        "resource library definition"
    in
      if file_version<>grammar_version then
        raise (RdefParseError ("Wrong version for resource definition library: expecting " ^ grammar_version ^ ", found " ^ file_version));
      List.map parse_rdef rdef_json_list


