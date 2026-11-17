#!/bin/sh
# Compare the integrated check command with the bootstrap compiler on actual files.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
(cd "$root" && coil build -o "$tmp/rewrite")
cd "$tmp"

compare() {
    expected=$1
    program=$2
    echo "$program" > input.coil
    for compiler in coil ./rewrite; do
        if "$compiler" check input.coil >diagnostic 2>&1; then actual=0; else actual=1; fi
        if [ "$actual" != "$expected" ]; then
            cat diagnostic >&2
            echo "$compiler check returned $actual for $program" >&2
            exit 1
        fi
        if [ "$expected" = 1 ]; then
            grep -F "error:" diagnostic >/dev/null
            grep -F "input.coil:" diagnostic >/dev/null
        fi
    done
}

compare 0 '(defn main [] (-> i64) (answer)) (defn answer [] (-> i64) 42)'
compare 0 '(defn f [] (-> bool) true)'
compare 0 '(defn f [] (-> i8) -128)'
compare 0 '(defn f [] (-> u8) 255)'
compare 1 '(defn f [] (-> i8) 128)'
compare 1 '(defn f [] (-> u8) -1)'
compare 1 '(defn main [] (-> bool) (answer)) (defn answer [] (-> i64) 42)'
compare 1 '(defn main [] (-> i64) (missing))'
compare 1 '(defn main [] (-> i64) (f)) (defn f [(x i64)] (-> i64) 42)'
compare 1 '(defn f [] (-> i64) 1) (defn f [] (-> i64) 2)'
compare 0 '(defn main [] (-> i64) (id (id 42))) (defn id [(x i64)] (-> i64) x)'
compare 1 '(defn main [] (-> i64) (id true)) (defn id [(x i64)] (-> i64) x)'
compare 1 '(defn main [] (-> i64) (id 1 2)) (defn id [(x i64)] (-> i64) x)'
compare 1 '(defn id [(x i64)] (-> i64) y)'
compare 1 '(defn f [(x i64) (x i64)] (-> i64) x)'

# Compile, link and run identical sources independently.
run_both() {
    expected=$1
    echo "$2" > input.coil
    coil build input.coil -o reference >/dev/null
    ./rewrite emit-obj input.coil -o actual.o
    cc actual.o -o actual
    ./rewrite build input.coil -o built
    status=0
    ./rewrite run input.coil || status=$?
    [ "$status" -eq "$expected" ]
    for exe in reference actual built; do
        status=0
        "./$exe" || status=$?
        [ "$status" -eq "$expected" ] || {
            echo "$exe returned $status, expected $expected" >&2
            exit 1
        }
    done
}
run_both 42 '(defn main [] (-> i64) (identity (identity 42))) (defn identity [(x i64)] (-> i64) x)'
run_both 72 '(defn main [] (-> i64) (third 9 45 72)) (defn third [(x i64) (y i64) (z i64)] (-> i64) z)'
run_both 19 '(defn main [] (-> i64) (discard false -7) 19) (defn discard [(x bool) (y i8)] (-> i8) y)'

# Validate the returned values across an independently compiled C caller.
cat > input.coil <<'COIL'
(defn narrow [] (-> i8) -128)
(defn high [] (-> u8) 255)
(defn truth [] (-> bool) true)
(defn lie [] (-> bool) false)
COIL
./rewrite emit-obj input.coil -o scalars.o
cat > caller.c <<'C'
#include <stdbool.h>
#include <stdint.h>
extern int8_t narrow(void);
extern uint8_t high(void);
extern bool truth(void);
extern bool lie(void);
int main(void) { return narrow() != -128 || high() != 255 || !truth() || lie(); }
C
cc caller.c scalars.o -o caller
./caller

echo '(defn main [] (-> i64) (missing))' > input.coil
if ./rewrite emit-obj input.coil -o rejected.o >diagnostic 2>&1; then exit 1; fi
grep -F "call to undefined function" diagnostic >/dev/null
test ! -e rejected.o

# A checked library can be emitted as an object. Linking the same file as
# an executable fails without main, and preserves the previous destination.
echo '(defn helper [] (-> i64) 5)' > library.coil
./rewrite emit-obj library.coil -o library.o
printf 'previous output\n' > destination
cp destination previous
if ./rewrite build library.coil -o destination >diagnostic 2>&1; then exit 1; fi
grep -F "cc exited unsuccessfully" diagnostic >/dev/null
cmp previous destination

run_both 29 '(defn main [] (-> i64) (pick false)) (defn pick [(flag bool)] (-> i64) (if flag 17 29))'
run_both 17 '(defn main [] (-> i64) (pick -4)) (defn pick [(n i8)] (-> i64) (if n 17 29))'
run_both 29 '(defn main [] (-> i64) (pick 0)) (defn pick [(n u64)] (-> i64) (if n 17 29))'
run_both 31 '(defn main [] (-> i64) (pick true false)) (defn pick [(a bool) (b bool)] (-> i64) (if a (if b (loop-again) (do (identity 3) (identity 31))) (loop-again))) (defn identity [(x i64)] (-> i64) x) (defn loop-again [] (-> i64) (loop-again))'
run_both 8 '(defn main [] (-> i64) (f false 4)) (defn f [(flag bool) (x u8)] (-> i64) (if flag 1 x) (if flag x 1) 8)'
run_both 0 '(defn main [] (-> i64) (if true false 2) 0)'
compare 1 '(defn main [] (-> i64) (if true false 2))'
compare 1 '(defn main [] (-> i64) (if false (missing) 2))'
compare 1 '(defn main [] (-> i64) (do true))'
run_both 23 '(defn main [] (-> i64) (noop) (ignore false) 23) (defn noop [] (-> void)) (defn ignore [(x bool)] (-> void) (if x (noop) (do 2 (do))))'
compare 1 '(defn f [(x void)] (-> void) x)'
compare 1 '(defn f [] (-> i64))'
compare 1 '(defn f [] (-> i64) (do))'
