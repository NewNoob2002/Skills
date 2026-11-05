# 树外模块构建与检查入口。KDIR 默认取当前运行内核的头文件包（linux-cachyos-headers 等）。
# 内核由 clang 构建时需 LLVM=1，与内核 .config 中的 CONFIG_CC_IS_CLANG 保持一致。
KDIR ?= /usr/lib/modules/$(shell uname -r)/build
LLVM_FLAG := $(if $(shell grep -s '^CONFIG_CC_IS_CLANG=y' $(KDIR)/.config),LLVM=1)

.PHONY: build checkpatch clean
# W=1 专属告警默认不改变退出码（LNXK-009 的 gap），这里加 -Werror 使新增告警成为失败。
# 注意 -Wmissing-prototypes/-Wmissing-declarations 属于 scripts/Makefile.warn 的默认组，与 W=1 无关。
build:
	$(MAKE) -C $(KDIR) M=$(CURDIR) $(LLVM_FLAG) W=1 KCFLAGS=-Werror modules

checkpatch:
	$(KDIR)/scripts/checkpatch.pl --no-tree --strict --terse -f acme-frame.c

clean:
	$(MAKE) -C $(KDIR) M=$(CURDIR) $(LLVM_FLAG) clean
