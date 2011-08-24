{
  (* Copyright 2009 by Genforma. All Rights Reserved. *)
  open Parser (* defines the type "token" *)
  exception Eof

 let incr_lineno lexbuf =
    let pos = lexbuf.Lexing.lex_curr_p in
    lexbuf.Lexing.lex_curr_p <- { pos with
      Lexing.pos_lnum = pos.Lexing.pos_lnum + 1;
      Lexing.pos_bol = pos.Lexing.pos_cnum;
    }
  ;;
}
rule token = parse
    [' ' '\t'] { token lexbuf } (* skip whitespace *)
    (* for comments, we skip to the end of the line, updating line counter *)
  | "//" [^'\n']* '\n' { incr_lineno lexbuf; token lexbuf }
    (* trace line numbers *)
  | '\n'              { incr_lineno lexbuf; token lexbuf }
  | '{'               { LBRACE }
  | '}'               { RBRACE }
  | '['               { LBRACKET }
  | ']'               { RBRACKET }
  | '.'               { QUALIFIER }
  | ','               { SEP }
  | '='               { EQL }
  | '<'               { LTHAN }
  | '>'               { GTHAN }
  | ">="              { GEQ }
  | "<="              { LEQ }
  | ':'               { COLON }

  (* keywords *)
  | "resource_def"    { RESOURCE_DEFN }
  | "key"             { KEY }
  | "config_port"     { CONFIG_PORT }
  | "input_ports"     { INPUT_PORTS }
  | "output_ports"    { OUTPUT_PORTS }
  | "list"            { LIST }
  | "inside"          { INSIDE }
  | "environment"     { ENVIRONMENT }
  | "peers"           { PEERS }
  | "one_of"          { ONE_OF }
  | "all_of"          { ALL_OF }
  | "port_mapping"    { PORT_MAPPING }
  | "resource_library" { LIBRARY }
  | "resource_def_version" { GRAMMAR_VERSION }
  | "true"             { TRUE }
  | "false"            { FALSE }
  | "null"             { NULL }

  | eof             { raise Eof }


  | ['A'-'Z' 'a'-'z'] (['A'-'Z' 'a'-'z' '0'-'9' '_']*) as name { SYMBOL(name) }
  | ['"'][^'"']*['"'] as string { STRING(string) }
  | ['0'-'9']+ as integer { INTEGER(integer) }
  | _ as c		{ print_string "Char:: " ; print_char c; token lexbuf }
