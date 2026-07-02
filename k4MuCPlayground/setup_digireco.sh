script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
benchmarks_dir="$(cd "${script_dir}/.." && pwd)"

echo "setup_digireco.sh now delegates to ../setup_config.sh"
source "${benchmarks_dir}/setup_config.sh" "$@"
