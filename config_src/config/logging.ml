(* Copyright 2009 by Genforma. All Rights Reserved. *)

(** I18n interface to ocaml-gettext *)

(*
module Gettext = Gettext.Program(
  struct let textdomain = "gfei"
         let codeset = None
         let dir = None
         let dependencies = []
  end) (GettextCamomile.Map)

let s_ = Gettext.s_
let sn_ = Gettext.sn_
let f_ = Gettext.f_
let fn_ = Gettext.fn_
*)
let s_ = fun x -> x
let sn_ = fun x -> x
let f_ = fun x -> x
let fn_ = fun x -> x

(** APIs for logging *)
type log_area =
    Gen      (** General -- unclassified *)
 |  Prs      (** Parser *)
 |  ConsGen  (** Generator *)


let log_area_to_string area =
  match area with
      Prs -> "Prs"
  |   ConsGen -> "ConsGen"
  |   Gen -> "Unclassified"


type logmsg_level =
    LogJunk
  | LogDebug (** Only print when debugging is enabled *)
  | LogInfo  (** Information messges to be printed when verbose is on *)
  | LogReserved
  | LogWarning (** A Warning. *)
  | LogError (** An Error. *)
  | LogCritical (** Error, possibly leading to termination *) 


let log_junk_lvl = 5
let log_debug_lvl  = 10
let log_info_lvl   = 20
let log_reserved_lvl  = 25
let log_warning_lvl   = 30
let log_error_lvl = 40
let log_critical_lvl = 50

let log_level_to_int lvl =
  match lvl with
    LogJunk -> log_junk_lvl
  | LogDebug -> log_debug_lvl 
  | LogInfo  -> log_info_lvl 
  | LogReserved -> log_reserved_lvl
  | LogWarning -> log_warning_lvl
  | LogError -> log_error_lvl 
  | LogCritical -> log_critical_lvl 

let log_level = ref log_info_lvl

let set_log_level (level:logmsg_level) =
  log_level := (log_level_to_int level)

let logging_enabled_for_lvl lvl = (!log_level)>=lvl

external system_logger : string -> string -> int -> string -> unit = "c_system_logger" 
external system_print_string : string -> unit = "c_system_print_string"
external system_print_endline : string -> unit = "c_system_print_endline"
external system_print_newline : unit -> unit = "c_system_print_newline"

let log_error area msg =
  prerr_endline ((log_area_to_string area) ^ " " ^ msg)

let log_always area msg =
  system_logger "Config" (log_area_to_string area) log_warning_lvl msg

let log_warning area msg =
  system_logger "Config" (log_area_to_string area) log_warning_lvl msg

let log_info area msg =
  if logging_enabled_for_lvl log_info_lvl then
    system_logger "Config" (log_area_to_string area) log_info_lvl msg


let log_debug area msg =
  if logging_enabled_for_lvl log_debug_lvl then
    system_logger "Config" (log_area_to_string area) log_debug_lvl  msg 

let log_junk area msg =
  system_logger "Config" (log_area_to_string area) log_junk_lvl msg

let log area level msg =
  system_logger "Config" (log_area_to_string area) (log_level_to_int level) msg

let is_info_enabled area =
  logging_enabled_for_lvl log_info_lvl

let is_debug_enabled area =
  logging_enabled_for_lvl log_debug_lvl


let eval_and_log_debug (area:log_area)  (fn:unit->string) =
  if logging_enabled_for_lvl log_debug_lvl
  then let msg = fn () in
    system_logger "Config" (log_area_to_string area) log_debug_lvl msg


(*
class error_msg =
object (self)
  val mutable user_msg = "" (* user level message *)
  val mutable developer_msg = "" (* developer message *)
  val mutable error_code = 0

  val mutable log_area = Gen

  method print () = ()

end
*)

type errorcode = int (* could be made fancy later *)

(* error codes *)
let mTYPECHECK = 1
let mUSER_INPUT_REQUIRED = 2
let mNO_SOLUTION = 3

(* parsing related error codes *)
let mEOF = 0x10
let mFILE_NOT_FOUND = 0x20
let mSYNTAX_ERROR = 0x30


type context = string list
type userlevel = string
type devlevel  = string
exception UserError of log_area * errorcode * userlevel * devlevel * context

