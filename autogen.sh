# See: https://stackoverflow.com/questions/59895/how-to-get-the-source-directory-of-a-bash-script-from-within-the-script-itself
# Note: you can't refactor this out: its at the top of every script so the scripts can find their includes.
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do # resolve $SOURCE until the file is no longer a symlink
  DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE" # if $SOURCE was a relative symlink, we need to resolve it relative to the path where the symlink file was located
done
SCRIPT_DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"

source "${SCRIPT_DIR}/include.sh"

cd "$SCRIPT_DIR" || fatal 1 "Failed to change to $SCRIPT_DIR"

requires=(
    "git"
    "poetry"
)

check_requirements "${requires[@]}"

# Note: 1 means failure/false/no
is_ci=1
while true; do
    case "$1" in
    --ci)
        # Enable CI mode operation
        is_ci=0
        ;;
    -*)
        ;;
    *)
        # End of options
        break
        ;;
    esac
    shift
done

# CI autodetect
if [ "$CI" = "true" ]; then
    log "Detected CI environment"
    is_ci=0
fi

if [ $is_ci -ne 0 ]; then
    log "Ensure pull request rebase"
    # Note: will break for git < 1.7.9 (looking at you Centos 7 users)
    if ! git config pull.rebase true; then
        fatal 1 "Failed to setup git pull request rebase"
    fi

    log "Linking hook scripts"
    while read -r hookscript; do
        if [ "$(readlink -f "$hookscript")" != "$(readlink -f .git/hooks/"$(basename "$hookscript")")" ]; then
            if ! ln -sf "$(readlink -f "$hookscript")" ".git/hooks/$(basename "$hookscript")" ; then
                fatal 1 "Failed to activate repository githooks"
            fi
        fi
    done < <(find "${githooks_dir}" -mindepth 1 -maxdepth 1 -type f)
fi

while read -r autogen_script; do
    if ! "$autogen_script"; then
        fatal 1 "$autogen_script failed"
    fi
done < <(find "${autogen_dir}" -mindepth 1 -maxdepth 1 -type f -name '*.sh' | sort)

log "Success"