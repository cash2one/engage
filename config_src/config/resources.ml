(* Copyright 2009 by Genforma. All Rights Reserved. *)
(** Types for representing resource definitions and resource instances *)

(** Version of the resource / resource instance grammar *)
let grammar_version = "1.0"

(** Symbols are just strings, but we use a level of indirection in our types
 *  in case we ever need to change them (e.g. for unicode support).
 *)
type symbol = string

(** String to symbol converstion function. Currently just returns the string *)
let symbol_of_string (str:string) :symbol = str

module Symbol =
  struct
    type t = symbol
    let compare = compare
  end

module SymbolMap = Map.Make(Symbol)


type scalar_val =
    Integer of int
  | String of symbol
  | Boolean of bool
  | Null

let scalar_eq v v' =
  match (v,v') with
  | Integer i, Integer i' -> i = i'
  | String s, String s' -> s = s'
  | Boolean b, Boolean b' -> b = b'
  | _ -> false

let scalar_gt v v' =
  match (v,v') with
  | Integer i, Integer i' -> i > i'
  | String s, String s' -> s > s'
  | _ -> false

let scalar_lt v v' =
  match (v,v') with
  | Integer i, Integer i' -> i < i'
  | String s, String s' -> s < s'
  | _ -> false

let scalar_geq v v' =
  match (v,v') with
  | Integer i, Integer i' -> i >= i'
  | String s, String s' -> s >= s'
  | _ -> false

let scalar_leq v v' =
  match (v,v') with
  | Integer i, Integer i' -> i <= i'
  | String s, String s' -> s <= s'
  | _ -> false



type port_reference =
  ConfigPortRef of symbol list (* property name *)
  | InputPortRef of symbol * (symbol list) (* port name, property name *)

type initial_val =
    ScalarInitialVal of scalar_val
  | PortReference of port_reference
  | MapInitialVal of (symbol*initial_val) list
  | ListInitialVal of initial_val list
  | TemplateInitialVal of symbol*(symbol list)

type type_decl =
    ScalarType of symbol
  | EnumType of symbol list
  | ListType of type_decl
  | MapType of (symbol*type_decl) list

type initial_val_kind =
    Default of initial_val (** default values are used in config ports *)
  | Fixed of initial_val (** fixed values are used in output ports *)
  | Includes of initial_val (** includes values are used in input ports
                                to include a value in the associated output
                                port of the source resource *)
  | NoInitialVal (** used when no initial value was specified *)

type property_def = {
  property_name : symbol;
  property_display_name : symbol option;
  property_type : type_decl;
  property_val : initial_val_kind;
  property_help : string  option;
}

(** map from port name to port def *)
type port_def_map = (property_def list) SymbolMap.t

type key_constraint =
    KeyEq of symbol * scalar_val (** name = value *)
  | KeyGt of symbol * scalar_val (** name > value *)
  | KeyGeq of symbol * scalar_val (** name >= value *)
  | KeyLt of symbol * scalar_val (** name < value *)
  | KeyLeq of symbol * scalar_val (** name <= value *)

type atomic_constraint = {
  key_constraints : key_constraint list;
  (** An atomic constraint may also have a mapping from input port names
      to output port names. If there is no mapping, then this field will
      have the value SymbolMap.empty *)
  port_mapping : symbol SymbolMap.t;
}

(** either a single constraint or an exclusive-or of a set of atomic
    constraints *)
type choice_constraint =
    AtomicConstraint of atomic_constraint
  | OneOfConstraint of atomic_constraint list

(** Either a single choice constraint or a list of choice constraints,
    all of which must be satisfied. *)
type compound_constraint =
  | ChoiceConstraint of choice_constraint
  | AllOfConstraint of choice_constraint list

type resource_def = {
  key : (symbol*scalar_val) list;
  display_name : symbol ;
  config_port_def : property_def list;
  input_port_defs : port_def_map;
  output_port_defs : port_def_map;
  inside : choice_constraint option;
  environment: compound_constraint option;
  peers: compound_constraint option;
}

(** Representation of json values. We parse resource instances into this format
    and then convert them to resource_inst records *)
type json_value =
    JsonScalar of scalar_val
  | JsonMap of json_map
  | JsonList of json_value list
and json_map = json_value SymbolMap.t

type resource_ref = {
  ref_id : symbol;
  ref_key : (symbol*scalar_val) list;
  ref_port_mapping : symbol SymbolMap.t;
}

(** Strongly-typed representation of a resource instance. The module Parse_resource
    converts from the json representation to this representation. *)
type resource_inst = {
  id : symbol;
  resource_key : (symbol*scalar_val) list;
  properties : json_map option; (** if present, these are arbrary properties
                                    which are passed through to the install
                                    engine.*)
  config_port : json_map;
  input_ports : json_map SymbolMap.t;
  output_ports : json_map SymbolMap.t;
  inside_ref: resource_ref option;
  environment_refs: resource_ref list;
  peer_refs: resource_ref list;
}


module Keywords = struct
  (* properties of the resource library *)
  let resource_def_version = "resource_def_version"
  let resource_definitions = "resource_definitions"

  (* the top level properties in a resource definition *)
  let key = "key"
  let display_name = "display_name"
  let config_port = "config_port"
  let input_ports = "input_ports"
  let output_ports = "output_ports"
  let inside = "inside"
  let environment = "environment"
  let peers = "peers"

  (* property definitions *)
  let prop_type = "type"
  let property_display_name = "display_name"
  let property_help = "help"
  let fixed_value = "fixed-value"
  let default = "default"
  let includes = "includes"
  let source = "source"

  (* relational operators *)
  let less_than = "less-than"
  let greater_than = "greater-than"
  let greater_than_or_equal = "greater-than-or-equal"
  let less_than_or_equal = "less-than-or-equal"

  (* properties for constraints *)
  let one_of = "one-of"
  let all_of = "all-of"
  let port_mapping = "port_mapping"
end;;

(** This is used by the parsers and pretty-printers *)
type port_type =
  ConfigPort
    | InputPort
    | OutputPort

let is_config_port port_type =
  match port_type with
      ConfigPort -> true | _ -> false

let is_output_port port_type =
  match port_type with
      OutputPort -> true | _ -> false

let is_input_port port_type =
  match port_type with
      InputPort -> true | _ -> false

let string_of_port_type (pt:port_type) :string =
  match pt with
      ConfigPort -> Keywords.config_port
    | InputPort -> Keywords.input_ports
    | OutputPort -> Keywords.output_ports

(* used by parser *)
module ParseInfo = struct
  let errors_in_input = ref false
end;;


