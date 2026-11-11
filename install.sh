#!/bin/sh
# 安装 embedded-engineering 技能到指定 Agent 的技能目录，并可选地初始化固件仓库。
#
# 用法：
#   ./install.sh --agent claude|codex|grok|hermes [--scope project|user] [--project-dir DIR]
#   ./install.sh --dest DIR                       # 任意支持 Agent Skills 格式的目录
# 选项：
#   --with-agents-md   项目中没有 AGENTS.md 时复制模板（只在 --scope project 时有效）
#   --with-barrc       项目根没有 .clang-format/.clang-tidy/.editorconfig 时复制 BARR-C 配置
#   --overwrite        已安装同名技能时替换（默认拒绝）
#   --dry-run          只打印将要执行的操作
set -eu

SKILL_NAME=embedded-engineering
SRC_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/skills/$SKILL_NAME

agent=""
scope=project
project_dir=$(pwd)
dest=""
with_agents_md=0
with_barrc=0
overwrite=0
dry_run=0

usage() {
    sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'
    exit "${1:-0}"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --agent) agent=${2:?}; shift 2 ;;
        --scope) scope=${2:?}; shift 2 ;;
        --project-dir) project_dir=${2:?}; shift 2 ;;
        --dest) dest=${2:?}; shift 2 ;;
        --with-agents-md) with_agents_md=1; shift ;;
        --with-barrc) with_barrc=1; shift ;;
        --overwrite) overwrite=1; shift ;;
        --dry-run) dry_run=1; shift ;;
        -h|--help) usage 0 ;;
        *) echo "unknown option: $1" >&2; usage 2 ;;
    esac
done

run() {
    echo "+ $*"
    [ "$dry_run" -eq 1 ] || "$@"
}

[ -f "$SRC_DIR/SKILL.md" ] || { echo "error: $SRC_DIR/SKILL.md not found" >&2; exit 1; }

if [ -z "$dest" ]; then
    case "$agent" in
        claude) sub=.claude/skills ;;
        codex)  sub=.agents/skills ;;
        grok)   sub=.grok/skills ;;
        hermes) sub=.hermes/skills ;;
        "") echo "error: need --agent or --dest" >&2; usage 2 ;;
        *) echo "error: unsupported agent '$agent' (use --dest for others)" >&2; exit 2 ;;
    esac
    case "$scope" in
        project)
            [ -d "$project_dir" ] || { echo "error: project dir $project_dir not found" >&2; exit 1; }
            dest=$(CDPATH= cd -- "$project_dir" && pwd)/$sub ;;
        user) dest=$HOME/$sub ;;
        *) echo "error: --scope must be project or user" >&2; exit 2 ;;
    esac
fi

target=$dest/$SKILL_NAME
if [ -e "$target" ] && [ "$overwrite" -ne 1 ]; then
    echo "error: $target exists; pass --overwrite to replace it" >&2
    exit 1
fi
run mkdir -p "$dest"
# 先复制，再把旧版移到备份；替换失败时保留并恢复旧版。
tmp="$dest/.$SKILL_NAME.tmp.$$"
backup="$dest/.$SKILL_NAME.bak.$$"
cleanup() {
    status=$?
    trap - 0 HUP INT TERM
    if [ -e "$backup" ] && [ ! -e "$target" ]; then
        if ! mv "$backup" "$target"; then
            echo "error: restore failed; old version retained at $backup" >&2
            status=1
        fi
    fi
    [ ! -e "$tmp" ] || rm -rf "$tmp"
    exit "$status"
}
if [ "$dry_run" -ne 1 ]; then
    [ ! -e "$tmp" ] && [ ! -e "$backup" ] || { echo "error: staging path exists" >&2; exit 1; }
    trap cleanup 0
    trap 'exit 1' HUP INT TERM
fi
run cp -R "$SRC_DIR" "$tmp"
[ ! -e "$target" ] || run mv "$target" "$backup"
run mv "$tmp" "$target"
[ ! -e "$backup" ] || run rm -rf "$backup"
echo "installed: $target"

if [ "$scope" = project ] && [ -n "$agent" ]; then
    proj=$(CDPATH= cd -- "$project_dir" && pwd)
    if [ "$with_agents_md" -eq 1 ]; then
        if [ -e "$proj/AGENTS.md" ]; then
            echo "skip: $proj/AGENTS.md exists (merge assets/AGENTS.md.template manually)"
        else
            run cp "$SRC_DIR/assets/AGENTS.md.template" "$proj/AGENTS.md"
            echo "next: fill the placeholders in $proj/AGENTS.md (choose one of six profiles; list by directory if multiple)"
        fi
    fi
    if [ "$with_barrc" -eq 1 ]; then
        for f in .clang-format .clang-tidy .editorconfig; do
            if [ -e "$proj/$f" ]; then
                echo "skip: $proj/$f exists (compare with $SRC_DIR/assets/barr-c/$f)"
            else
                run cp "$SRC_DIR/assets/barr-c/$f" "$proj/$f"
            fi
        done
    fi
fi

[ "$agent" = claude ] && echo "next: start a new Claude Code session; invoke /$SKILL_NAME or let it trigger from the description"
exit 0
