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
    printf '%s\n' "$program" > input.coil
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
compare 0 '(defn f [] (-> f32) 0.1)'
compare 1 '(defn f [] (-> i64) 0.1)'
compare 1 '(defn f [] (-> f64) 1)'
compare 1 '(defn f [] (-> f64) (% 2.0 1.5))'
compare 0 '(defn f [] (-> i8) -128)'
compare 0 '(defn f [] (-> u8) 255)'
compare 1 '(defn f [] (-> i8) 128)'
compare 1 '(defn f [] (-> u8) -1)'
compare 1 '(defn f [] (-> u8) \λ)'
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
    printf '%s\n' "$2" > input.coil
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
run_both 42 '(module app) (import "coil.primitive" :as p) (defn main [] (-> i64) (p/iadd (p/imul 5 8) (p/isub 8 6)))'
run_both 42 '(module app) (import "coil.primitive" :use [fcmp-le fadd]) (defn main [] (-> i64) (if (fcmp-le (fadd 1.5 2.0) 3.5) 42 7))'
run_both 42 '(module app) (module custom) (export combine) (defprimitive combine :ixor) (module app) (import "custom" :as c) (defn main [] (-> i64) (c/combine 40 2))'
compare 1 '(module app) (import "coil.primitive" :as p) (defn main [] (-> i64) (p/iadd 1 2 3))'
compare 1 '(module app) (import "coil.primitive" :as p) (defn main [] (-> bool) (p/icmp-eq true false))'
compare 1 '(module app) (defprimitive add iadd)'
run_both 42 '(defstruct Syntax [(code Code)]) (defsum Source (At [(syntax Syntax)])) (defn main [] (-> i64) 42)'
run_both 42 '(module app) (module lib) (export second) (defn second [A B] [(a A) (b B)] (-> B) b) (module app) (import "lib" :as l) (defn main [] (-> i64) (+ (cast i64 (l/second [bool i8] true 40)) (l/second false 2)))'
run_both 42 '(defn main [] (-> i64) (pass 42 5)) (defn pass [T] [(x T) (n i64)] (-> T) (if n (pass [T] x (- n 1)) x))'
run_both 42 '(defn first [T] [(x T) (y T)] (-> T) x) (defn small [] (-> u8) (first 42 (: 2 u8))) (defn main [] (-> i64) (cast i64 (small)))'
run_both 42 '(defn bytes [T] [] (-> i64) (+ (sizeof T) (alignof T))) (defn via [T] [] (-> i64) (bytes [T])) (defn main [] (-> i64) (+ (via [i32]) (via [f64]) (via [u8]) (via [i64])))'
compare 1 '(defn id [T] [(x T)] (-> T) true)'
compare 1 '(defn id [T] [(x T)] (-> T) x) (defn f [] (-> bool) (id [u8] true))'
compare 1 '(defn id [T] [(x T)] (-> T) x) (defn f [] (-> i64) (id [i64 u8] 1))'
run_both 42 '(defn main [] (-> i64) (identity (identity 42))) (defn identity [(x i64)] (-> i64) x)'
run_both 42 '(defn main [] (-> i64) (+ \space \newline))'
run_both 42 '(defn main [] (-> i64) (if (= (scale 3.5) 7.5) 42 1)) (defn scale [(x f32)] (-> f32) (+ (* 2.0 x) 0.5))'
run_both 42 '(defn main [] (-> i64) (cast i64 (cast f64 (half (: 85 u32))))) (defn half [(x u32)] (-> f32) (/ (cast f32 x) 2.0))'
run_both 42 '(defn main [] (-> i64) (if (= (round (: -12 i8)) -12) 42 1)) (defn round [(x i8)] (-> i8) (cast i8 (cast f64 x)))'
run_both 42 '(defn main [] (-> i64) (let [x (/ 0.0 0.0)] (if (and (!= x x) (not (= x x)) (not (<= x x))) 42 1)))'
run_both 42 '(defn main [] (-> isize) (cast isize (add (: 40 u64) (: 2 usize)))) (defn add [(a usize) (b u64)] (-> usize) (+ a b))'
compare 1 '(defn f [(x isize)] (-> usize) x)'
run_both 42 '(defn* main [] (-> i64) (let* [x 20 y (+ x 2)] (sum x y))) (defn* sum :cc (coil.cc.C) [(x i64) (y i64)] (-> i64) (+ x y))'
compare 1 '(defn* f [] (-> i64) (let* [x y y 1] x))'
run_both 42 '(defn main [] (-> i64) (call sum 20 22)) (defn sum [(a i64) (b i64)] (-> i64) (call + a b))'
compare 1 '(defn call [] (-> i64) 1)'
compare 1 '(defn main [] (-> i64) (call if true 42 0))'
compare 1 '(defn main [] (-> i64) (call (main)))'
run_both 42 '(module app) (module values) (export answer) (const answer later) (const later 42) (module app) (import "values" :as v) (defn main [] (-> i64) (cast i64 (small v/answer))) (defn small [(x u8)] (-> u8) x)'
run_both 42 '(const enabled true) (const scale 0.5) (defn main [] (-> i64) (if enabled (cast i64 (* 84.0 scale)) 0))'
compare 1 '(const a b) (const b a) (defn main [] (-> i64) 0)'
run_both 42 '(const k (: 42 u8)) (const copy k) (defn main [] (-> i64) (cast i64 copy))'
compare 1 '(const k (: 42 u8)) (defn f [] (-> u64) k)'
compare 1 '(const k (: 300 u8)) (defn main [] (-> i64) 0)'
run_both 42 '(const answer (if 0 9 (: 42 u8))) (defn main [] (-> i64) (cast i64 answer))'
compare 1 '(const answer (if true 42 (runtime))) (defn runtime [] (-> i64) 2)'
compare 1 '(const answer (if false 300 (: 42 u8)))'
compare 1 '(const a 300) (defn f [] (-> u8) a)'
run_both 42 '(module app) (module values) (export enabled amount) (def enabled true) (def amount (: 42.5 f32)) (module app) (import "values" :as v) (defn main [] (-> i64) (if v/enabled (cast i64 v/amount) 0))'
run_both 42 '(const k 42) (def stored (: k i8)) (defn main [] (-> i64) (cast i64 stored))'
compare 1 '(def a 1) (defn f [] (-> u8) a)'
compare 1 '(def a 42) (const alias a) (def b alias)'
compare 1 '(def a (if true 42 b)) (def b 1)'
# Read the emitted data symbol directly through the platform C ABI.
printf '%s\n' '(def amount (: -42 i16))' > '7.static.coil'
cat > static-reader.c <<'C'
#include <stdint.h>
#define STRINGIFY_INNER(x) #x
#define STRINGIFY(x) STRINGIFY_INNER(x)
extern const int16_t amount __asm__(STRINGIFY(__USER_LABEL_PREFIX__) "coil_def._7_static.amount");
int main(void) { return amount != -42; }
C
for compiler in coil ./rewrite; do
    "$compiler" emit-obj 7.static.coil -o static.o
    cc static-reader.c static.o -o static-reader
    ./static-reader
done
run_both 42 '(const n 2) (const bytes (sizeof (array (slice i16) n))) (def total bytes) (defn main [] (-> i64) (+ total (alignof (array (ptr i32) 0)) (sizeof u16)))'
run_both 8 '(defn main [] (-> i64) (sizeof (fnptr (coil.cc.C) [(slice i32)] never)))'
compare 1 '(defn f [] (-> i64) (alignof (fnptr (coil.cc.C) [void] void)))'
compare 1 '(const size (sizeof i64)) (defn f [] (-> u8) size)'
compare 1 '(defn f [] (-> i64) (alignof (ptr missing)))'
compare 1 '(const size (sizeof u16)) (defn f [] (-> i64) (sizeof (array u8 size)))'
compare 1 '(defn f [] (-> i64) (sizeof (array i32 -1)))'
run_both 42 '(module app) (module types) (export Packet) (defstruct Packet [(flag u8) (links (array Link 2)) (tail u16)]) (defstruct Link [(next (ptr Link))]) (module app) (import "types" :as t) (const offset (offsetof t/Packet links)) (defn main [] (-> i64) (+ (sizeof t/Packet) offset 2))'
run_both 42 '(defstruct Rec [(byte u8)]) (const Rec 41) (defn main [] (-> i64) (+ Rec (sizeof Rec)))'
compare 1 '(defstruct A [(bs (array B 0))]) (defstruct B [(a A)])'
compare 1 '(defstruct A [(field (ptr Missing))])'
compare 1 '(defstruct i17 [])'
run_both 8 '(module app) (import "coil.layout" :as l) (defstruct S :layout (l/Packed) [(x u8) (y i32) (z u8)]) (defn main [] (-> i64) (+ (sizeof S) (alignof S) (offsetof S y)))'
run_both 68 '(module app) (import "coil.layout" :as l) (defstruct S :layout (l/Align 32) [(x u8) (y i32) (z u8)]) (defn main [] (-> i64) (+ (sizeof S) (alignof S) (offsetof S y)))'
run_both 20 '(module app) (import "coil.layout" :as l) (defstruct S :layout (l/Align 2) [(x u8) (y i32) (z u8)]) (defn main [] (-> i64) (+ (sizeof S) (alignof S) (offsetof S y)))'
run_both 20 '(module app) (import "coil.layout" :as l) (defstruct S :layout (l/C) [(x u8) (y i32) (z u8)]) (defn main [] (-> i64) (+ (sizeof S) (alignof S) (offsetof S y)))'
compare 1 '(module app) (import "coil.layout" :as l) (defstruct S :layout (l/Align 3) [(x u8) (y i32) (z u8)]) (defn main [] (-> i64) (+ (sizeof S) (alignof S) (offsetof S y)))'
compare 1 '(module app) (import "coil.layout" :as l) (defstruct S :layout (l/Align 0) [(x u8) (y i32) (z u8)]) (defn main [] (-> i64) (+ (sizeof S) (alignof S) (offsetof S y)))'
compare 1 '(module app) (import "coil.layout" :as l) (defstruct S :layout (l/Packed 1) [(x u8) (y i32) (z u8)]) (defn main [] (-> i64) (+ (sizeof S) (alignof S) (offsetof S y)))'
run_both 8 '(module app) (import "coil.layout" :as l) (defstruct S :layout (coil.layout.Packed) [(x u8) (y i32) (z u8)]) (defn main [] (-> i64) (+ (sizeof S) (alignof S) (offsetof S y)))'
run_both 8 '(module app) (module linked) (export Node Choice) (defstruct Node [T] [(next (ptr (Node T))) (value T)]) (defsum Choice [A B] (Left [(value A)]) (Right [(value B)])) (module app) (import "linked" :as l) (defn main [] (-> i64) (sizeof (ptr (l/Node (l/Choice i64 bool)))))'
compare 1 '(defstruct Box [T] [(value Missing)])'
compare 1 '(defsum Option [T] (Missing) (Present [(value Unknown)]))'
compare 1 '(defstruct Box [T] [(value T) (value T)])'
compare 1 '(defstruct Box [T] [(value T)]) (defstruct Uses [(p (ptr (Box i8 i32)))])'
compare 1 '(defstruct Box [T] [(value T)]) (defstruct Uses [(p (ptr Box))])'
run_both 12 '(defstruct A [(x u24) (p (ptr i129))]) (defn main [] (-> i64) (+ (offsetof A p) (sizeof u24)))'
compare 1 '(defstruct A [(x i32) (x i16)])'
compare 1 '(defstruct A [(x u16)]) (defn f [] (-> i64) (offsetof A y))'
run_both 48 '(module app) (module msg) (export Event Empty) (defstruct Pair [(x u8) (y u8)]) (defsum Event (Empty) (Batch [(pairs (array Pair 2))]) (Single [(wide i128)])) (module app) (import "msg" :as m) (defn main [] (-> i64) (+ (sizeof m/Event) (alignof m/Event)))'
run_both 40 '(defsum S (Wide [(prefix u8) (value i128)])) (defn main [] (-> i64) (sizeof S))'
compare 1 '(defsum S (A [(value T)])) (defstruct T [(s S)])'
printf '%s\n' '(defsum S (Same)) (defsum T (Same))' > input.coil
for compiler in coil ./rewrite; do
    if "$compiler" check input.coil >diagnostic 2>&1; then exit 1; fi
    grep -F 'variant' diagnostic >/dev/null
done
grep -F 'input.coil:' diagnostic >/dev/null
compare 1 '(defsum S (Bad [(value Missing)]))'
run_both 72 '(defn main [] (-> i64) (third 9 45 72)) (defn third [(x i64) (y i64) (z i64)] (-> i64) z)'
run_both 19 '(defn main [] (-> i64) (discard false -7) 19) (defn discard [(x bool) (y i8)] (-> i8) y)'

# Validate the returned values across an independently compiled C caller.
cat > input.coil <<'COIL'
(defn single [] (-> f32) 0.1)
(defn doubleValue [] (-> f64) -1.25)
(defn narrow [] (-> i8) -128)
(defn high [] (-> u8) 255)
(defn widenSigned [(x i8)] (-> i64) (cast i64 x))
(defn widenUnsigned [(x u8)] (-> i64) (cast i64 x))
(defn truth [] (-> bool) true)
(defn lie [] (-> bool) false)
COIL
./rewrite emit-obj input.coil -o scalars.o
cat > caller.c <<'C'
#include <stdbool.h>
#include <stdint.h>
extern float single(void);
extern double doubleValue(void);
extern int8_t narrow(void);
extern uint8_t high(void);
extern int64_t widenSigned(int8_t);
extern int64_t widenUnsigned(uint8_t);
extern bool truth(void);
extern bool lie(void);
int main(void) { return single() != 0.1f || doubleValue() != -1.25 || narrow() != -128 || high() != 255 || !truth() || lie() || widenSigned(-1) != -1 || widenUnsigned(255) != 255; }
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

run_both 42 '(defn main [] (-> i64) (let [x (identity 42) y x x 7] (let [y x] y) y)) (defn identity [(n i64)] (-> i64) n)'
run_both 12 '(defn main [] (-> i64) (f 12)) (defn f [(x i64)] (-> i64) (let [previous x x true] (if x previous 0)))'
run_both 9 '(defn main [] (-> i64) (let [x 9] (if false (let [x false] x) true) (let [_ 3] x)))'
compare 1 '(defn main [] (-> i64) (let [x y y 3] x))'
compare 1 '(defn main [] (-> i64) (let [x 3] x) x)'
compare 1 '(defn main [] (-> i64) (let [x 3 y] x))'
compare 1 '(defn main [] (-> i64) (let [_ 1] _))'
compare 1 '(defn main [] (-> i64) (let [x (do)] 3))'
compare 1 '(defn main [] (-> i64) (let [f 3] (f))) (defn f [] (-> i64) 42)'
run_both 19 '(defn main [] (-> i64) (let [(mut x) 3 before x] (if true (set! x (f before)) (set! x 11)) (load x))) (defn f [(v i64)] (-> i64) 19)'
run_both 3 '(defn main [] (-> i64) (let [(mut x) 3 before x] (store! x 8) before))'
run_both 7 '(defn main [] (-> i64) (let [(mut x) false] (set! x true) (if x 7 4)))'
run_both 0 '(defn main [] (-> i64) (let [(mut x) 6] (set! x 4)))'
compare 1 '(defn main [] (-> i64) (let [x 1] (set! x 3)))'
compare 1 '(defn main [] (-> i64) (let [x 1] (load x)))'
compare 1 '(defn main [] (-> i64) (let [(mut x) 1] (set! x true)))'
run_both 200 '(defn main [] (-> i64) (let [small (: 200 u8)] (cast i64 small)))'
run_both 1 '(defn main [] (-> i64) (cast i64 (cast u8 257)))'
run_both 255 '(defn main [] (-> i64) (cast i64 (cast i8 (: 255 u8))))'
compare 1 '(defn main [] (-> i64) (: 256 u8) 1)'
compare 1 '(defn main [] (-> i64) (: 42 bool) 1)'
compare 1 '(defn main [] (-> i64) (cast i64 true))'
compare 1 '(defn f [] (-> bool) (cast bool 1))'

run_both 120 '(defn main [] (-> i64) (fact 5)) (defn fact [(n i64)] (-> i64) (if (<= n 1) 1 (* n (fact (- n 1)))))'
run_both 9 '(defn main [] (-> i64) (- 20 6 5))'
run_both 9 '(defn main [] (-> i64) (let [(mut x) 2] (+ (do (set! x 3) x) (do (set! x (* x 2)) x))))'
run_both 11 '(defn main [] (-> i64) (if (comparisons-agree) 11 22)) (defn comparisons-agree [] (-> bool) (= (< (: -1 i8) 2) (> (: 255 u8) 2)))'
run_both 42 '(defn main [] (-> i64) (if (!= true false) (+ 9 10 11 12) 0))'
run_both 14 '(defn main [] (-> i64) (^ (& 15 12) (| 2 0)))'
run_both 253 '(defn main [] (-> i64) (cast i64 (- (: 3 i8))))'
run_both 0 '(defn main [] (-> i64) (cast i64 (+ (: 255 u8) 1)))'
compare 0 '(defn f [] (-> i8) (+ 1 (: 3 i8)))'
compare 1 '(defn f [] (-> i8) (+ 1 3))'
compare 1 '(defn f [] (-> i64) (+ true false))'
compare 1 '(defn f [] (-> i64) (< 1 2 3) 0)'
compare 1 '(defn f [] (-> u8) (- (: 3 u8)))'
run_both 7 '(defn main [] (-> i64) (cast i64 (+ (if true 3 4) (: 4 u8))))'
run_both 6 '(defn main [] (-> i64) (cast i64 (+ (let [x 4] (do x 2)) (: 4 i8))))'

run_both 24 '(defn main [] (-> i64) (let [(mut i) 0 (mut sum) 0] (while (< i 10) (set! i (+ i 1)) (when (= i 4) (continue)) (when (= i 8) (break)) (set! sum (+ sum i))) sum))'
run_both 0 '(defn main [] (-> i64) (while 0 (main)))'
run_both 37 '(defn main [] (-> i64) (loop (break 37)))'
run_both 9 '(defn main [] (-> i64) (f false)) (defn f [(flag bool)] (-> i64) (loop (if flag (break 4) (break 9))))'
run_both 13 '(defn main [] (-> i64) (let [(mut n) 2] (loop (let [inner (loop (break 13))] (unless n (break inner)) (set! n (- n 1))))))'
compare 1 '(defn main [] (-> i64) (break 2))'
compare 1 '(defn main [] (-> i64) (continue))'
compare 1 '(defn main [] (-> i64) (while false (break true)))'
compare 1 '(defn main [] (-> i64) (loop (break 4) (missing)))'
run_both 41 '(defn main [] (-> i64) (loop :outer (loop (break :outer 41))))'
run_both 7 '(defn main [] (-> i64) (let [(mut i) 0] (loop :outer (set! i (+ i 1)) (loop (when (< i 7) (continue :outer)) (break :outer i)))))'
run_both 4 '(defn main [] (-> i64) (loop (break (break 4))))'
compare 1 '(defn main [] (-> i64) (loop :one (break :two 3)))'
run_both 23 '(defn main [] (-> i64) (loop (+ 1 (break 23))))'
run_both 19 '(defn main [] (-> i64) (loop (identity (break 19)))) (defn identity [(x i64)] (-> i64) x)'
run_both 5 '(defn main [] (-> i64) (while 5)) (defn while [(n i64)] (-> i64) n)'
compare 1 '(defn main [] (-> i64) (loop (+ (break 7) 1)))'
run_both 17 '(defn main [] (-> i64) (and (or 17)))'
run_both 19 '(defn main [] (-> i64) (if (and (and) (not (or)) (not 0)) 19 0))'
run_both 2 '(defn main [] (-> i64) (let [(mut x) 0] (and (do (set! x 1) true) (do (set! x 2) false) (do (set! x 3) true)) x))'
run_both 1 '(defn main [] (-> i64) (let [(mut x) 0] (or (do (set! x 1) true) (do (set! x 2) false)) x))'
compare 1 '(defn main [] (-> i64) (and 1 2))'
compare 1 '(defn main [] (-> i64) (or true (missing)) 1)'
run_both 42 '(defn main [] (-> i64) (block :found (loop (return-from :found 42))))'
run_both 17 '(defn main [] (-> i64) (let [(mut n) 0] (loop (set! n (+ n 1)) (block :skip (when (< n 3) (continue)) (break 17)))))'
run_both 11 '(defn main [] (-> i64) (let [(mut n) 0] (scope :again (set! n (+ n 1)) (when (< n 2) (continue :again)) (+ 9 n))))'
run_both 7 '(defn main [] (-> i64) (f true)) (defn f [(b bool)] (-> i64) (block :x (when b (return-from :x 7)) 19))'
compare 1 '(defn main [] (-> i64) (block :x (break 1)))'
compare 1 '(defn main [] (-> i64) (scope 1 2))'
run_both 21 '(defn main [] (-> i64) (let [(mut n) 0] (do (defer (set! n (+ (* n 10) 1))) (defer (set! n (+ (* n 10) 2))) 0) n))'
run_both 19 '(defn main [] (-> i64) (let [(mut n) 19] (block :done (defer (set! n 5)) (return-from :done n))))'
run_both 42 '(defn main [] (-> i64) (let [(mut n) 0] (loop (defer (set! n 42)) (break)) n))'
run_both 3 '(defn main [] (-> i64) (let [(mut n) 0 (mut i) 0] (while (< i 3) (defer (set! n (+ n 1))) (set! i (+ i 1)) (continue)) n))'
run_both 7 '(defn main [] (-> i64) (let [(mut n) 7] (block :exit (return-from :exit 0) (defer (set! n 42)) 0) n))'
run_both 8 '(defn main [] (-> i64) (let [(mut n) 0] (do (defer (set! n (loop (break 8)))) 0) n))'
compare 1 '(defn main [] (-> i64) (loop (defer (break 3)) 0))'
compare 1 '(defn main [] (-> i64) (defer 0))'
compare 1 '(defn main [] (-> i64) (if true (defer 0) 2))'
run_both 65 '(defn main [] (-> i64) (let [(mut n) 0] (block :out (defer (set! n (+ (* 10 n) 1))) (loop (defer (set! n (+ (* 10 n) 2))) (return-from :out (do (set! n 3) 0)))) n))'
run_both 0 '(defn main [] (-> i64) (cond))'
run_both 42 '(defn main [] (-> i64) (cond false 3 false 7 42))'
run_both 7 '(defn main [] (-> i64) (cond false 3 :else 7 true (missing)))'
run_both 2 '(defn main [] (-> i64) (let [(mut n) 0] (cond (do (set! n 1) false) 0 (do (set! n 2) true) n (do (set! n 3) true) 0 0)))'
compare 1 '(defn f [] (-> i64) (cond true false 1))'
run_both 128 '(defn main [] (-> i64) (cast i64 (shift 1 7))) (defn shift [(x u8) (n u8)] (-> u8) (<< x n))'
run_both 7 '(defn main [] (-> i64) (if (= (shift -128 4) (: -8 i8)) 7 0)) (defn shift [(x i8) (n i8)] (-> i8) (>> x n))'
run_both 15 '(defn main [] (-> i64) (cast i64 (shift 240 4))) (defn shift [(x u8) (n u8)] (-> u8) (>> x n))'
compare 1 '(defn f [(x u16) (n u8)] (-> u16) (<< x n))'
run_both 10 '(defn main [] (-> i64) (/ 100 5 2))'
run_both 13 '(defn main [] (-> i64) (f -17 5)) (defn f [(x i8) (y i8)] (-> i64) (if (and (= (/ x y) (: -3 i8)) (= (% x y) (: -2 i8))) 13 0))'
run_both 127 '(defn main [] (-> i64) (f 251 2)) (defn f [(x u8) (y u8)] (-> i64) (+ (cast i64 (/ x y)) (* 2 (cast i64 (% x y)))))'
compare 1 '(defn main [] (-> i64) (% 100 7 3))'
compare 1 '(defn f [(x i64) (y u64)] (-> i64) (/ x y))'

mkdir -p package/src
(
    cd package
    printf '[package]\nname = "demo"\nentry = "custom.coil"\n' > Coil.toml
    echo '(defn main [] (-> i64) 31)' > custom.coil
    for compiler in coil ../rewrite; do
        "$compiler" check
        status=0
        "$compiler" run || status=$?
        [ "$status" -eq 31 ]
        rm -f package-app
        "$compiler" build -o package-app
        status=0
        ./package-app || status=$?
        [ "$status" -eq 31 ]
    done
    printf '[package]\nname = "demo"\n' > Coil.toml
    echo '(defn main [] (-> i64) 17)' > src/main.coil
    for compiler in coil ../rewrite; do
        "$compiler" check
        status=0
        "$compiler" run || status=$?
        [ "$status" -eq 17 ]
        rm -f package-app
        "$compiler" build -o package-app
        status=0
        ./package-app || status=$?
        [ "$status" -eq 17 ]
    done
    for entry in missing.coil src; do
        printf '[package]\nname = "demo"\nentry = "%s"\n' "$entry" > Coil.toml
        for compiler in coil ../rewrite; do
            if "$compiler" build -o rejected > diagnostic 2>&1; then exit 1; fi
            grep -F "Coil.toml: [package] entry '$entry' is not a file" diagnostic >/dev/null
            [ ! -e rejected ]
        done
    done
)
run_both 42 '(module demo.math) (defn main [] (-> i64) (+ (answer) (demo.math.answer) (demo.math/answer))) (defn answer [] (-> i64) 14)'
compare 1 '(module demo.math) (defn main [] (-> i64) (other/answer)) (defn answer [] (-> i64) 1)'
compare 1 '(module demo.math) (defn main [] (-> i64) (demo.math/main))'
compare 1 '(module demo.math) (defn answer [] (-> i64) 1) (defn demo.math.answer [] (-> i64) 2)'
compare 1 '(module "demo.math") (defn main [] (-> i64) 1)'
run_both 42 '(module app) (defn main [] (-> i64) (+ (answer) (other.read-answer))) (defn answer [] (-> i64) 12) (module other) (defn read-answer [] (-> i64) (other/answer)) (defn answer [] (-> i64) 30)'
run_both 33 '(module app) (defn main [] (-> i64) (prelude.answer)) (module prelude) (defn answer [] (-> i64) (next)) (module app) (defn next [] (-> i64) 1) (module prelude) (defn next [] (-> i64) 33)'
compare 1 '(module a) (defn main [] (-> i64) (helper)) (module b) (defn helper [] (-> i64) 7)'
compare 1 '(module a) (defn main [] (-> i64) (b/helper)) (module b) (defn helper [] (-> i64) 7)'
run_both 13 '(module a) (defn main [] (-> i64) (b.main)) (module b) (defn main [] (-> i64) 13)'
run_both 9 '(defn f [] (-> i64) 9) (module b) (defn main [] (-> i64) (f))'
run_both 27 '(module app) (module lib.math) (defn f [] (-> i64) 9) (module app) (import "lib.math" :as m :use [f]) (defn main [] (-> i64) (+ (m/f) (lib.math/f) (f)))'
run_both 12 '(module entry) (module numbers) (module entry) (import "numbers" :use [value]) (defn main [] (-> i64) (value)) (module numbers) (defn value [] (-> i64) 12)'
run_both 8 '(module entry) (module numbers) (defn value [] (-> i64) 2) (module entry) (import "numbers" :use [value]) (defn value [] (-> i64) 8) (defn main [] (-> i64) (value))'
compare 1 '(module entry) (module lib) (defn f [] (-> i64) 1) (module entry) (import "lib" :as m) (defn main [] (-> i64) (f))'
compare 1 '(module entry) (module lib) (module entry) (import "lib" :as "text")'
compare 1 '(module app) (module z) (defn f [] (-> i64) 7) (module app) (import "z" :as m) (defn probe [] (-> i64) (m/z/f))'
compare 1 '(module app) (defn main [] (-> i64) 7) (module z) (import "app" :as m) (defn probe [] (-> i64) (m/main))'
run_both 18 '(module app) (module a) (export visible) (defn hidden [] (-> i64) 9) (defn visible [] (-> i64) (a/hidden)) (module app) (import "a" :as m :use *) (defn main [] (-> i64) (+ (m/visible) (visible)))'
run_both 9 '(module app) (module a) (export) (defn hidden [] (-> i64) 9) (module app) (defn main [] (-> i64) (a.hidden))'
compare 1 '(module app) (module a) (export) (defn hidden [] (-> i64) 9) (module app) (import "a" :as m) (defn main [] (-> i64) (m/hidden))'
compare 1 '(module app) (module a) (module app) (import "a" :use [f]) (module a) (export) (defn f [] (-> i64) 1)'
compare 1 '(module app) (export undefined)'
compare 1 '(module app) (export [main]) (defn main [] (-> i64) 2)'
compare 1 '(module app) (module a) (defn f [] (-> i64) 4) (module b) (defn f [] (-> i64) 5) (module app) (import "a" :use *) (import "b" :use *) (defn main [] (-> i64) (f))'
run_both 5 '(module app) (module a) (defn f [] (-> i64) 4) (module b) (defn f [] (-> i64) 5) (module app) (import "a" :use * :exclude [f]) (import "b" :use *) (defn main [] (-> i64) (f))'
run_both 4 '(module app) (module a) (defn f [] (-> i64) 4) (module app) (import "a" :use *) (import "a" :use *) (defn main [] (-> i64) (f))'

mkdir mapped
(
    cd mapped
    cat > Coil.toml <<'TOML'
[package]
name = "mapped"
entry = "app.coil"
[modules]
"mapped.left" = "left.coil"
"mapped.right" = "right.coil"
"mapped.shared" = "shared.coil"
TOML
    echo '(module mapped.app) (import "mapped.left" :as l) (import "mapped.right" :as r) (defn main [] (-> i64) (+ (l/f) (r/f)))' > app.coil
    echo '(module mapped.left) (import "mapped.shared" :use [value]) (defn f [] (-> i64) (value))' > left.coil
    echo '(module mapped.right) (import "mapped.shared" :as s) (defn f [] (-> i64) (s/value))' > right.coil
    echo '(module mapped.shared) (export value) (defn value [] (-> i64) 19)' > shared.coil
    for compiler in coil ../rewrite; do
        "$compiler" check
        status=0
        "$compiler" run || status=$?
        [ "$status" -eq 38 ]
    done
    for broken in '(defn value [] (-> i64) (missing))' '('; do
        printf '(module mapped.shared)\n%s\n' "$broken" > shared.coil
        for compiler in coil ../rewrite; do
            if "$compiler" check >diagnostic 2>&1; then exit 1; fi
            grep -F 'shared.coil:2:' diagnostic >/dev/null
        done
    done
)

mkdir -p discovered/lib
(
    cd discovered
    cat > Coil.toml <<'TOML'
[package]
name = "discovered"
entry = "entry.coil"
source-roots = ["lib"]
[modules]
"discovered.extra" = "./lib/extra.coil"
TOML
    echo '(module discovered.app) (import "discovered.worker" :use [work]) (defn offset [] (-> i64) 9) (defn main [] (-> i64) (work))' > entry.coil
    echo '(module discovered.worker) (import "discovered.extra" :as e) (defn work [] (-> i64) (e/value))' > lib/arbitrary.coil
    echo '(module discovered.extra) (import "discovered.app" :as app) (defn value [] (-> i64) (+ 20 (app/offset)))' > lib/extra.coil
    for compiler in coil ../rewrite; do
        "$compiler" check
        status=0
        "$compiler" run || status=$?
        [ "$status" -eq 29 ]
    done
)

mkdir -p standalone/source/nested standalone/caller
echo '(module sample.app) (import "sample.worker" :as w) (defn main [] (-> i64) (w/value))' > standalone/source/entry.coil
echo '(module sample.worker) (defn value [] (-> i64) 28)' > standalone/source/nested/implementation.coil
echo '(module sample.duplicate)' > standalone/source/a.coil
echo '(module sample.duplicate)' > standalone/source/b.coil
echo '(module sample.worker) (defn value [] (-> i64) 63)' > standalone/caller/decoy.coil
(
    cd standalone/caller
    for compiler in coil ../../rewrite; do
        "$compiler" check ../source/entry.coil
        status=0
        "$compiler" run ../source/entry.coil || status=$?
        [ "$status" -eq 28 ]
    done
)

for target in nested/implementation implementation.coil; do
    printf '(import "%s")\n' "$target" > standalone/source/path-import.coil
    for compiler in coil ./rewrite; do
        if "$compiler" check standalone/source/path-import.coil >diagnostic 2>&1; then exit 1; fi
        grep -F "import paths are not supported" diagnostic >/dev/null
        grep -F "path-import.coil:1:1" diagnostic >/dev/null
    done
done

echo '(module sample.app) (import "sample.duplicate")' > standalone/source/conflict.coil
for compiler in coil ./rewrite; do
    if "$compiler" check standalone/source/conflict.coil >diagnostic 2>&1; then exit 1; fi
    grep -F "namespace 'sample.duplicate' is declared by multiple source files" diagnostic >/dev/null
    grep -F '/a.coil' diagnostic >/dev/null
    grep -F '/b.coil' diagnostic >/dev/null
done

mkdir -p dependencies/app/src dependencies/math/impl dependencies/constants/src dependencies/bare
(
    cd dependencies
    cat > app/Coil.toml <<'TOML'
[package]
name = "app"
entry = "src/main.coil"
[dependencies]
math = { path = "../math" }
constants = { path = "../constants" }
TOML
    cat > math/Coil.toml <<'TOML'
[package]
name = "math"
source-roots = ["impl"]
[dependencies]
constants = { path = "../constants" }
[modules]
"math.operations" = "impl/operations.coil"
TOML
    cat > constants/Coil.toml <<'TOML'
[package]
name = "constants"
exclude = ["src/ignored.coil"]
[dependencies]
bare = { path = "../bare" }
TOML
    echo '(module app.main) (import "math.operations" :as m) (defn main [] (-> i64) (m/answer))' > app/src/main.coil
    echo '(module math.operations) (import "constants.values" :use [value]) (defn answer [] (-> i64) (+ 2 (value)))' > math/impl/operations.coil
    echo '(module constants.values) (import "bare.base" :as b) (defn value [] (-> i64) (b/value))' > constants/src/values.coil
    echo '(module constants.values) (defn value [] (-> i64) 9)' > constants/src/ignored.coil
    echo '(module bare.base) (defn value [] (-> i64) 40)' > bare/anything.coil
    cd app
    for compiler in coil ../../rewrite; do
        "$compiler" check
        status=0
        "$compiler" run || status=$?
        [ "$status" -eq 42 ]
    done
    mkdir -p ../outside
    printf '[package]\nname = "math"\nsource-roots = ["../outside"]\n' > ../math/Coil.toml
    for compiler in coil ../../rewrite; do
        if "$compiler" check >diagnostic 2>&1; then exit 1; fi
        grep -F 'source root outside the package' diagnostic >/dev/null
    done

)

run_both 27 '(module app) (extern abs [i32] (-> i32)) (defn main [] (-> i64) (cast i64 (abs -27)))'
run_both 37 '(module app) (module lib) (extern labs [i64] (-> i64)) (extern labs [i64] (-> i64)) (module app) (import "lib" :as c) (defn main [] (-> i64) (c/labs -37))'
compare 1 '(extern labs [i64] (-> i64)) (defn main [] (-> i64) (labs false))'
compare 1 '(extern labs [i64] (-> i64)) (defn main [] (-> i64) (labs))'

echo '(module app) (extern record_value [i64 i64 i64 i64 i64 i64 i64 i64 u8 u8] (-> void)) (extern read_value [] (-> i64)) (defn main [] (-> i64) (record_value 1 2 3 4 5 6 7 8 13 17) (read_value))' > external.coil
cat > external.c <<'C'
#include <stdint.h>
static int64_t saved;
void record_value(int64_t a, int64_t b, int64_t c, int64_t d,
                  int64_t e, int64_t f, int64_t g, int64_t h,
                  uint8_t i, uint8_t j) {
    saved = a + b + c + d + e + f + g + h + i + j;
}
int64_t read_value(void) { return saved; }
C
for compiler in coil ./rewrite; do
    "$compiler" emit-obj external.coil -o external.o
    cc external.c external.o -o external-app
    status=0
    ./external-app || status=$?
    [ "$status" -eq 66 ]
done

run_both 43 '(module app) (extern magnitude :as "labs" [i64] (-> i64)) (defn main [] (-> i64) (magnitude -43))'
run_both 43 '(module app) (extern magnitude :cc (coil.cc.C) :as "labs" [i64] (-> i64)) (extern magnitude :as "labs" :cc (coil.cc.C) [i64] (-> i64)) (defn main [] (-> i64) (magnitude -43))'
run_both 24 '(module app) (import "coil.cc" :as abi) (import "coil.layout" :as layout) (defn main [] (-> i64) (+ (sizeof abi/NativeCc) (sizeof layout/Layout)))'
run_both 8 '(module app) (import "coil.cc" :as abi) (defn main [] (-> i64) (sizeof (fnptr (abi/Fast) [i8] void)))'
run_both 27 '(module app) (import "coil.cc" :as abi) (extern abs :cc (abi/C) [i32] (-> i32)) (defn main [] (-> i64) (cast i64 (abs -27)))'
run_both 27 '(module app) (import "coil.cc" :use [C]) (extern abs :cc (C) [i32] (-> i32)) (defn main [] (-> i64) (cast i64 (abs -27)))'
compare 1 '(module app) (defsum Convention (C)) (extern abs :cc (C) [i32] (-> i32))'
run_both 27 '(extern abs :cc (coil.cc.C) [i32] (-> i32)) (defn main [] (-> i64) (cast i64 (abs -27)))'
run_both 31 '(defn main [] (-> i64) (increment 30)) (defn increment :cc (coil.cc.C) [(n i64)] (-> i64) (+ n 1))'
compare 1 '(defn f :cc (coil.cc.C) [] (-> i64))'
compare 1 '(extern magnitude :cc (cc/unknown) [i64] (-> i64))'
compare 1 '(extern magnitude :as "" [i64] (-> i64))'

for declarations in '(extern labs [i64] (-> i64)) (extern labs [i32] (-> i32))' \
    '(extern magnitude :as "labs" [i64] (-> i64)) (extern magnitude :as "other" [i64] (-> i64))'; do
    echo "$declarations" > input.coil
    for compiler in coil ./rewrite; do
        if "$compiler" check input.coil >diagnostic 2>&1; then exit 1; fi
        grep -F "conflicting signatures" diagnostic >/dev/null
    done
done

mkdir -p mixed/src 'mixed/native files' 'mixed/include files' 'mixed/library files'
(
    cd mixed
    cat > Coil.toml <<'TOML'
[package]
name = "mixed"
entry = "src/main.coil"
[cc]
sources = ["native files/calculate.c"]
include-dirs = ["include files"]
flags = ["-DDELTA=3"]
[link]
objects = ["native files/start.o"]
search-paths = ["library files"]
libs = ["increment"]
TOML
    echo '(module mixed.main) (extern calculate [i64] (-> i64)) (defn main [] (-> i64) (calculate 10))' > src/main.coil
    echo 'long start(long); long increment(long);' > 'include files/math_parts.h'
    printf '#include "math_parts.h"\nlong calculate(long x) { return increment(start(x)) + DELTA; }\n' > 'native files/calculate.c'
    echo 'long start(long x) { return x * 3; }' > start.c
    echo 'long increment(long x) { return x + 4; }' > increment.c
    cc -c start.c -o 'native files/start.o'
    cc -c increment.c -o increment.o
    ar rcs 'library files/libincrement.a' increment.o
    for compiler in coil ../rewrite; do
        "$compiler" build -o executable
        status=0
        ./executable || status=$?
        [ "$status" -eq 37 ]
        status=0
        "$compiler" run || status=$?
        [ "$status" -eq 37 ]
    done
    cp executable previous-build
    cp 'native files/calculate.c' working.c
    printf '#error invalid native source\n' > 'native files/calculate.c'
    if ../rewrite build -o executable >diagnostic 2>&1; then exit 1; fi
    grep -F 'invalid native source' diagnostic >/dev/null
    cmp previous-build executable
    cp working.c 'native files/calculate.c'
    echo 'flags = ["-Wl,--unknown-coil-test-option"]' >> Coil.toml
    if ../rewrite build -o executable >diagnostic 2>&1; then exit 1; fi
    grep -F -- '--unknown-coil-test-option' diagnostic >/dev/null
    cmp previous-build executable
)

mkdir -p foreign-deps/app/src foreign-deps/api/src foreign-deps/base/native foreign-deps/unused/src
(
    cd foreign-deps
    cat > app/Coil.toml <<'TOML'
[package]
name = "app"
entry = "src/main.coil"
[dependencies]
api = { path = "../api" }
unused = { path = "../unused" }
TOML
    cat > api/Coil.toml <<'TOML'
[package]
name = "api"
[dependencies]
base = { path = "../base" }
[cc]
sources = ["bridge.c"]
TOML
    cat > base/Coil.toml <<'TOML'
[package]
name = "base"
[cc]
sources = ["native/value.c"]
include-dirs = ["native"]
flags = ["-DOFFSET=5"]
TOML
    cat > unused/Coil.toml <<'TOML'
[package]
name = "unused"
[link]
libs = ["missing_unused_library"]
TOML
    echo '(module app.main) (import "api.bridge" :as api) (defn main [] (-> i64) (api/read))' > app/src/main.coil
    echo '(module api.bridge) (extern read :as "foreign_bridge" [] (-> i64))' > api/src/bridge.coil
    echo 'long foreign_value(void); long foreign_bridge(void) { return foreign_value() + 1; }' > api/bridge.c
    echo '#define BASE 30' > base/native/value.h
    printf '#include <value.h>\nlong foreign_value(void) { return BASE + OFFSET; }\n' > base/native/value.c
    echo '(module unused.lib) (defn value [] (-> i64) 1)' > unused/src/lib.coil
    cd app
    for compiler in coil ../../rewrite; do
        status=0
        "$compiler" run || status=$?
        [ "$status" -eq 36 ]
    done
    echo '(module app.main) (import "unused.lib" :as missing) (defn main [] (-> i64) (missing/value))' > src/main.coil
    for compiler in coil ../../rewrite; do
        if "$compiler" build -o rejected >diagnostic 2>&1; then exit 1; fi
        grep -F 'missing_unused_library' diagnostic >/dev/null
        [ ! -e rejected ]
    done
)

run_both 17 '(defn main [] (-> i64) (|> (|>> 17)))'
run_both 12 '(defn double [(x i64)] (-> i64) (+ x x)) (defn main [] (-> i64) (|> 9 (- 3) double))'
run_both 14 '(defn double [(x i64)] (-> i64) (+ x x)) (defn main [] (-> i64) (|>> 3 (- 10) double))'
run_both 42 '(defn main [] (-> i64) (|> true (if 42 9)))'
run_both 11 '(defn answer [] (-> i64) 11) (defn main [] (-> i64) (|>> answer ()))'
run_both 21 '(defn main [] (-> i64) (let [(mut x) 0] (|>> (do (set! x (+ (* x 10) 1)) x) (+ (do (set! x (+ (* x 10) 2)) x))) x))'
compare 1 '(defn main [] (-> i64) (|> 1 ()))'
compare 1 '(defn main [] (-> i64) (|> 2 undefined-stage))'
compare 1 '(defn main [] (-> i64) (let [(mut n) 0] (& false (do (set! n 1) true)) n))'

mkdir -p ws/members/app ws/members/lib
(
    cd ws
    printf '%s\n' '[workspace]' 'name = "work"' 'members = ["members/*"]' > Coil.toml
    printf '%s\n' '[package]' 'name = "app"' 'entry = "main.coil"' '[cc]' 'sources = ["locate.c"]' > members/app/Coil.toml
    printf '%s\n' '[package]' 'name = "lib"' > members/lib/Coil.toml
    echo '(module work.app.main) (import "work.lib.values" :as v) (extern locate [] (-> i64)) (defn main [] (-> i64) (- (locate) (v/value)))' > members/app/main.coil
    echo '(module work.lib.values) (defn value [] (-> i64) 42)' > members/lib/values.coil
    printf '%s\n' '#include <unistd.h>' 'long locate(void) { return access("member-marker", F_OK) == 0 ? 42 : 99; }' > members/app/locate.c
    touch member-marker
    for compiler in coil ../rewrite; do
        "$compiler" check 2>diagnostic
        grep -F '2/2 members ok' diagnostic >/dev/null
        "$compiler" run 2>diagnostic
        grep -F '1/1 members ok' diagnostic >/dev/null
        "$compiler" build 2>diagnostic
        ./members/app/build/debug/app
        "$compiler" build -o picked 2>diagnostic
        ./picked
        rm -f picked members/app/build/debug/app
    done
    echo '(module work.lib.bad) (defn broken [] (-> i64) missing)' > members/lib/bad.coil
    for compiler in coil ../rewrite; do
        if "$compiler" check >diagnostic 2>&1; then exit 1; fi
        grep -F '1/2 members ok' diagnostic >/dev/null
        grep -F 'bad.coil' diagnostic >/dev/null
    done
)

mkdir -p default-output/src
(
    cd default-output
    echo '(defn main [] (-> i64) 0)' > 'src/multi.part.coil'
    for compiler in coil ../rewrite; do
        "$compiler" build 'src/multi.part.coil'
        ./build/debug/multi.part
        rm build/debug/multi.part
    done
    printf '%s\n' '[package]' 'name = "named-app"' 'entry = "src/multi.part.coil"' > Coil.toml
    for compiler in coil ../rewrite; do
        "$compiler" build
        ./build/debug/named-app
        "$compiler" build src/multi.part.coil
        ./build/debug/multi.part
        rm build/debug/named-app build/debug/multi.part
    done
)
