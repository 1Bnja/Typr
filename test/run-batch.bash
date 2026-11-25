#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

if [[ $# -ne 0 ]]; then
    echo "Usage: $0" >&2
    exit 2
fi

python=${TYPR_TEST_PYTHON:-python3}
report=reporte_tests.xml
target=tests/test_suites.py
args=(-o junit_logging=no -o junit_family=xunit1 "--junitxml=$report")

if [[ ! -t 0 || ! -t 1 || -n ${CI:-} ]]; then
    rm -f -- "$report"
    exec "$python" -m pytest "$target" "${args[@]}"
fi

selection=
PS3='Seleccione una opción: '
select _ in 'Ejecutar todas las suites' 'Elegir una suite' 'Salir'; do
    case $REPLY in
        1) selection='Todas las suites'; break ;;
        2)
            suite_list=$("$python" -B -c \
                'import sys; sys.path.insert(0, "tests"); from suite_runner import SUITES; print("\n".join(SUITES))')
            if [[ -z $suite_list ]]; then
                printf 'No hay suites disponibles.\n' >&2
                exit 1
            fi
            mapfile -t suites <<< "$suite_list"
            PS3='Seleccione una suite: '
            select selection in "${suites[@]}"; do
                [[ -n $selection ]] && break
                printf 'Opción no válida.\n' >&2
            done
            if [[ -n ${selection:-} ]]; then
                target+="::test_suite[$selection]"
            fi
            break
            ;;
        3) break ;;
        *) printf 'Opción no válida.\n' >&2 ;;
    esac
done

if [[ -z ${selection:-} ]]; then
    printf 'No se ejecutaron pruebas.\n'
    exit 0
fi

printf 'Selección: %s\n' "$selection"
rm -f -- "$report"
exec "$python" test/scripts/live-batch.py "$report" "$target" "${args[@]}"
