#!/usr/bin/env bash
set -euo pipefail

policy="${1:-status}"
case "$policy" in
    status|automatic|always|never) ;;
    *)
        echo "Usage: $0 [status|automatic|always|never]" >&2
        exit 2
        ;;
esac

if ! command -v kscreen-doctor >/dev/null 2>&1; then
    echo "VRR unavailable: kscreen-doctor was not found." >&2
    exit 3
fi

read_outputs() {
    kscreen-doctor -o \
        | sed -E $'s/\033\\[[0-9;]*[mK]//g' \
        | awk '
            /^Output:/ { output_name=$3 }
            /^[[:space:]]*Vrr:/ {
                vrr=$2
                if (output_name != "" && tolower(vrr) != "incapable") {
                    print output_name "\t" vrr
                }
            }
        '
}

mapfile -t outputs < <(read_outputs)
if ((${#outputs[@]} == 0)); then
    echo "VRR unavailable: no VRR-capable output detected."
    exit 4
fi

if [[ "$policy" != "status" ]]; then
    args=()
    for entry in "${outputs[@]}"; do
        output_name="${entry%%$'\t'*}"
        args+=("output.${output_name}.vrrpolicy.${policy}")
    done
    kscreen-doctor "${args[@]}"
    mapfile -t outputs < <(read_outputs)
fi

for entry in "${outputs[@]}"; do
    output_name="${entry%%$'\t'*}"
    current_policy="${entry#*$'\t'}"
    printf '%s: %s\n' "$output_name" "$current_policy"
done
