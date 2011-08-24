# script to get the library directory used by ocaml
ocamlc -v | grep 'Standard library directory' | awk '{ print $4 }'