(* Copyright 2009 by Genforma. All Rights Reserved. *)
(** functions to convert a json value to a resource spec *)

open Resources
open Json

exception ResourceParseError of string

let (current_resource_id:symbol option ref) = ref None
let (last_good_resource_id:symbol option ref) = ref None


let raise_error (msg:string) =
  match (!current_resource_id, !last_good_resource_id) with
      (Some res_id, _) ->
        raise (ResourceParseError (msg ^ " in resource " ^ res_id))
    | (None, Some res_id) ->
        raise (ResourceParseError (msg ^ " after resource " ^ res_id))
    | _ -> raise (ResourceParseError msg)


let do_cast (cast_fn:json_value->'v) (v:'json_value) (err_ctx:string) :'v =
  try
    cast_fn v
  with CastError (exp, act) ->
    raise_error
      (err_ctx ^ (": expecting type " ^ exp ^ ", instead found " ^ act))
        
let get_resource_property (name:symbol) (resource:json_map)
                          (cast_fn:json_value->'a) :'a =
  try
    cast_fn (SymbolMap.find name resource)
  with Not_found -> raise_error ("Missing resource property " ^ name)
    | CastError (exp, act) ->
        raise_error ("Resource property " ^ name ^
                       " has wrong type: " ^ act ^ ", was expecting " ^ exp)

(* get an optional resource property. Return default if the property is not found *)
let get_opt_resource_property (name:symbol) (resource:json_map)
                              (cast_fn:json_value->'a) (default:'a) :'a =
  try
    cast_fn (SymbolMap.find name resource)
  with Not_found -> default
    | CastError (exp, act) ->
        raise_error ("Resource property " ^ name ^
                       " has wrong type: " ^ act ^ ", was expecting " ^ exp)


let parse_resource_key (resource:json_map) :(symbol*scalar_val) list =
  let key_map = get_resource_property "key" resource cast_to_map in
  let list =
    SymbolMap.fold
      (fun name v list ->
         let s = do_cast cast_to_scalar v ("key property " ^ name) in
           (name, s)::list)
      key_map []
  in match list with
      [] -> raise_error "Key map is empty"
    | _ -> List.rev list

let parse_ports (port_group:symbol) (resource:json_map) :json_map SymbolMap.t =
  let port_map =
      get_opt_resource_property port_group resource cast_to_map SymbolMap.empty in
    SymbolMap.fold
      (fun port_name v map ->
         let port = do_cast cast_to_map v ("Wrong type for " ^ port_group) in
           SymbolMap.add port_name port map) port_map SymbolMap.empty

let parse_output_ports (resource:json_map) (input_ports: json_map SymbolMap.t) =
  let port_map =
      get_opt_resource_property "output_ports" resource cast_to_map SymbolMap.empty in
    SymbolMap.fold
      (fun port_name v map ->
         match type_of_json_value v with
         | "map" ->
           let port = do_cast cast_to_map v ("Wrong type for output ports") in
           SymbolMap.add port_name port map
         | "string" ->
           let s = cast_to_symbol v in
           print_endline s ;
           assert false ; 
         | _ -> raise_error ("Wrong type for output ports: expected map or string")
      ) 
      port_map SymbolMap.empty
  
let parse_port_mapping (ref_json:json_value) :symbol SymbolMap.t =
  let ref_map = do_cast cast_to_map ref_json "resource port mapping" in
    SymbolMap.fold
      (fun k v res_map ->
         SymbolMap.add k (do_cast cast_to_symbol v "port mapping value") res_map)
      ref_map SymbolMap.empty
         
let parse_resource_ref (ref_json:json_value) :resource_ref =
  let ref_map = do_cast cast_to_map ref_json "resource reference" in
  let id = get_resource_property "id" ref_map cast_to_symbol
  and key = parse_resource_key ref_map
  and port_mapping =
    if SymbolMap.mem "port_mapping" ref_map
    then parse_port_mapping (SymbolMap.find "port_mapping" ref_map)
    else SymbolMap.empty
  in {ref_id=id; ref_key=key; ref_port_mapping=port_mapping;}

let parse_resource_ref_list (json:json_value) :resource_ref list =
  let json_list = do_cast cast_to_list json "resource reference list" in
    List.map parse_resource_ref json_list

let parse_resource_inst (json:json_value) :resource_inst =
  match json with
      JsonMap resource -> begin
        let id = get_resource_property "id" resource cast_to_symbol in
          current_resource_id := Some id;
          let key = parse_resource_key resource
          and properties =
            if SymbolMap.mem "properties" resource
            then Some (get_resource_property "properties" resource cast_to_map)
            else None
          and config_port = get_opt_resource_property "config_port" resource
                              cast_to_map SymbolMap.empty
          and input_ports = parse_ports "input_ports" resource
          in
          (* output ports can depend directly on input ports *)
          let output_ports = parse_output_ports resource input_ports 
          and inside_ref =
            if SymbolMap.mem "inside" resource
            then Some (parse_resource_ref (SymbolMap.find "inside" resource))
            else None
          and environment_refs =
            if SymbolMap.mem "environment" resource
            then parse_resource_ref_list (SymbolMap.find "environment" resource)
            else []
          and peer_refs =
            if SymbolMap.mem "peers" resource
            then parse_resource_ref_list (SymbolMap.find "peers" resource)
            else []
          and user_data =
            begin
              let keywords = [ "id"; "key"; "properties"; "config_port"; "input_ports"; "output_ports"; "inside"; "environment"; "peers" ] in
              SymbolMap.fold (fun k v m -> if List.mem k keywords then m else SymbolMap.add k v m) resource SymbolMap.empty
            end 
          in
            last_good_resource_id := Some id;
            current_resource_id := None;
            {id=id; resource_key=key; properties=properties;
             config_port=config_port;
             input_ports=input_ports; output_ports=output_ports;
             inside_ref=inside_ref; environment_refs=environment_refs;
             peer_refs=peer_refs;
             user_data=user_data;}
      end
    | _ -> raise_error ("Expecting map for resource, got " ^
                          (type_of_json_value json))

let parse_resource_list (json:json_value) :resource_inst list =
  let list = do_cast cast_to_list json "resource list" in
    List.rev
      (List.fold_left (fun list json_resource ->
                         (parse_resource_inst json_resource)::list)
         [] list)
