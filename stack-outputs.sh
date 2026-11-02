# sourced by the deploy/submit scripts
# reads values that cdk deploy writes to stack-outputs.json (see outputsFile in mc_pricer/cdk.json)

OUTPUTS_FILE="$(dirname "${BASH_SOURCE[0]}")/stack-outputs.json"

stack_output() {
    if [[ ! -f "$OUTPUTS_FILE" ]]; then
        echo "$OUTPUTS_FILE not found - run cdk deploy in mc_pricer/ first" >&2
        return 1
    fi
    # -e makes jq fail on a missing key instead of printing null
    jq -er --arg key "$1" '.McPricerStack[$key]' "$OUTPUTS_FILE" || {
        echo "output $1 not in $OUTPUTS_FILE - is the stack deployed?" >&2
        return 1
    }
}
