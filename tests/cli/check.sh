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
