/* QEMU mps2-an386（Cortex-M4）目标测试的链接脚本。
 * 存储布局取自 QEMU hw/arm/mps2.c：ZBT SSRAM1 4 MiB @ 0x00000000 作为“flash”，
 * SSRAM2/3 @ 0x20000000 作为 RAM。只用于仿真，不对应真实板卡。 */
MEMORY
{
    FLASH (rx)  : ORIGIN = 0x00000000, LENGTH = 4M
    RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 64K
}

ENTRY(Reset_Handler)

SECTIONS
{
    .text :
    {
        KEEP(*(.vectors))
        *(.text*)
        *(.rodata*)
        . = ALIGN(4);
    } > FLASH

    .data :
    {
        _sdata = .;
        *(.data*)
        . = ALIGN(4);
        _edata = .;
    } > RAM AT > FLASH
    _sidata = LOADADDR(.data);

    .bss (NOLOAD) :
    {
        _sbss = .;
        *(.bss*)
        *(COMMON)
        . = ALIGN(4);
        _ebss = .;
    } > RAM

    _estack = ORIGIN(RAM) + LENGTH(RAM);
}
