#!/bin/sh
# 独立复现 make dt_binding_check 的两步（无需内核源码树）：
#   1. dt-doc-validate：binding 本身符合 dtschema 元模式
#   2. 提取 examples → dtc 编译 → dt-validate 按 binding 校验示例
# dtschema 版本固定；dt-doc-validate 发现错误时退出码仍可能为 0，因此以输出为准。
set -eu
DTSCHEMA=${DTSCHEMA:-dtschema==2026.9}
dt() { uv tool run --quiet --from "$DTSCHEMA" "$@"; }
out=${TMPDIR:-/tmp}/acme-binding.$$
mkdir -p "$out"
trap 'rm -rf "$out"' EXIT
rc=0
for y in $(find bindings -name '*.yaml' | sort); do
	b=$(basename "$y" .yaml)
	if dt dt-doc-validate -u bindings "$y" > "$out/$b.doc" 2>&1; [ -s "$out/$b.doc" ]; then
		cat "$out/$b.doc"; echo "FAIL: $y does not satisfy the meta-schema"; rc=1; continue
	fi
	dt dt-extract-example "$y" > "$out/$b.dts"
	dtc -q -I dts -O dtb -o "$out/$b.dtb" "$out/$b.dts"
	dt dt-mk-schema -j bindings > "$out/processed.json"
	if dt dt-validate -s "$out/processed.json" "$out/$b.dtb" > "$out/$b.val" 2>&1; [ -s "$out/$b.val" ]; then
		cat "$out/$b.val"; echo "FAIL: example in $y does not validate"; rc=1; continue
	fi
	echo "OK: $y"
done
exit $rc
