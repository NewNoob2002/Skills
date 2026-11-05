/* 丢弃永不执行的 C++ 静态析构与 C 终结函数（GCC + newlib/newlib-nano，配合 -fno-use-cxa-atexit）。
 * MCU 固件从不正常退出，这些代码只占 Flash。
 *
 * 用法一（项目有自己的链接脚本）：把下面 /DISCARD/ 段并入 SECTIONS { ... }。
 * 用法二（使用工具链默认脚本）：原样以 -Wl,-T,linker_discard.ld 追加；INSERT 把它插入默认脚本。
 *   已在 Arm GNU Toolchain 15.3 + newlib-nano 上验证：.fini 与 .fini_array 被移除，链接成功。
 *
 * 注意：不要丢弃 .init_array / .preinit_array，那是全局构造函数表。
 * 若链接报 _fini 未定义，说明启动代码会调用 exit()：去掉 *(.fini) 一行，只丢弃 .fini_array。
 */
SECTIONS
{
    /DISCARD/ :
    {
        *(.fini_array)
        *(.fini_array.*)
        *(.fini)
    }
}
INSERT AFTER .text;
