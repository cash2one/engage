%{
(* Copyright 2009 by Genforma. All Rights Reserved. *)
(** The parser has two top-level rules:
    - resource_library is for libraries of resource definitions. The grammar
      translates directly to lists of Resources.resource_def instances.
    - json_value is for resource instances. The grammer supports a subset of
      JSON and is translated to Resources.json_value instances. Json values can be
      translated to Resource.resource_inst values using the Parse_resource module.

*)
  open Resources
  open Lexing
  open Parsing

let parse_error s = (* Called by the parser function on error *)
  print_endline ("Parse error: " ^ s)

let print_err_line msg =
  let pos = Parsing.symbol_start_pos ()
  in let lineno = pos.pos_lnum
  and colno = pos.pos_cnum - pos.pos_bol
  in
    ParseInfo.errors_in_input := true;
    print_endline ("Syntax error at line " ^ (string_of_int lineno) ^
		     ", column " ^ (string_of_int colno) ^ ": " ^ msg)


(** The string token includes quotes, which we stip off. *)
let string_token_to_symbol (stok:string) :symbol =
  let len = String.length stok in
    match len with
        0 | 1 -> assert false
      | 2 -> symbol_of_string ""
      | _ -> symbol_of_string (String.sub stok 1 (len - 2))

exception VersionError of string

%}

/* declarations */
%token <string> SYMBOL
%token <string> STRING
%token <string> INTEGER
%token LBRACE
%token RBRACE
%token LBRACKET
%token RBRACKET
%token QUALIFIER
%token SEP
%token EQL
%token LTHAN
%token GTHAN
%token GEQ
%token LEQ
%token QUOTE
%token COLON
%token RESOURCE_DEFN
%token KEY
%token CONFIG_PORT
%token INPUT_PORTS
%token OUTPUT_PORTS
%token LIST
%token INSIDE
%token ENVIRONMENT
%token PEERS
%token ONE_OF
%token ALL_OF
%token PORT_MAPPING
%token LIBRARY
%token GRAMMAR_VERSION
%token TRUE
%token FALSE
%token NULL


%start json_value
%type<Resources.scalar_val> scalar
%type<Resources.json_map> json_prop_list
%type<Resources.json_value option> json_value


%%
/* rules */
scalar:
  STRING { Resources.String (string_token_to_symbol $1) }
  | INTEGER { Resources.Integer (int_of_string $1) }
  | TRUE { Resources.Boolean true }
  | FALSE { Resources.Boolean false }
  | NULL { Resources.Null }




json_prop_list:
  STRING COLON json_value {
    match $3 with
        Some v -> SymbolMap.add (string_token_to_symbol $1) v SymbolMap.empty
      | None -> SymbolMap.empty
    }
  | json_prop_list SEP STRING COLON json_value {
      match $5 with
          Some v -> SymbolMap.add (string_token_to_symbol $3) v $1
        | None -> SymbolMap.empty
    }

json_value_list:
  json_value {
      match $1 with
          Some v -> [v]
        | None -> []
    }
  | json_value_list SEP json_value {
      match $3 with
          Some v -> v::$1
        | None -> []
    }

json_value:
  scalar {Some (JsonScalar $1)}
  | LBRACE json_prop_list RBRACE { Some (Resources.JsonMap $2) }
  | LBRACE RBRACE { Some (Resources.JsonMap SymbolMap.empty) }
  | LBRACKET json_value_list RBRACKET { Some (Resources.JsonList (List.rev $2)) }
  | LBRACKET RBRACKET { Some (Resources.JsonList []) }
  | LBRACE error RBRACE { print_err_line "invalid json map"; None }
  | LBRACKET error RBRACKET { print_err_line "invalid json list"; None }
  | error { print_err_line "invalid json value"; None }

%%

(* trailer *)

