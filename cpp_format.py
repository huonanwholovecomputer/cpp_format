#!/usr/bin/env python3
"""
C++ 代码空格规范化脚本
=======================
将此脚本放在项目根目录下运行，会自动格式化当前目录及子目录下的 .cpp / .h 文件。

格式化规则（参考 Google C++ Style Guide 部分规则）：
  1. 关键字后空格：if( → if (、for( → for (、while( → while ( 等
  2. 左大括号前空格：){ → ) {、else{ → else {
  3. 逗号后空格：,x → , x
  4. 分号后空格（同行多语句）：;next → ; next
  5. 赋值 = 两侧空格：x=y → x = y
  6. 比较运算符两侧空格：== != <= >= && ||
  7. 逻辑非 ! 后不留空格：( ! x) → (!x)
  8. 比较 < > 两侧空格（自动保护模板语法 at<uchar> 不被破坏）
  9. 流运算符 << >> 两侧空格：cout<<x → cout << x
 10. 位运算符 | & 两侧空格
 11. 算术 + - / 两侧空格：a+b → a + b
 12. 乘号 * 前空格（数字*括号）：0.001*( → 0.001 * (
 13. else / else if 独立成行（非 K&R 风格）
 14. 多语句同行时 if/for/while 的 { 折叠到同行

用法：
  python3 cpp_format.py                    # 格式化当前目录下所有 .cpp/.h
  python3 cpp_format.py /path/to/project   # 格式化指定目录
  python3 cpp_format.py --dry-run          # 预览变更，不实际写入
"""

import re
import os
import sys
import argparse

# ============================================================
# 配置区
# ============================================================

# 需要处理的文件扩展名
EXTENSIONS = ('.cpp', '.h', '.hpp', '.c', '.cc', '.cxx', '.hxx')

# 需要保护不被空格破坏的模板类型名（< 后紧跟这些标识符时不加空格）
# 因为 at<uchar> 中的 < 是模板语法，不是比较运算符
TEMPLATE_TYPES = {
    'uchar', 'int', 'float', 'double', 'char', 'bool', 'void',
    'size_t', 'uint8_t', 'int32_t', 'int64_t', 'string', 'vector',
    'Mat', 'Ptr', 'Scalar', 'QByteArray', 'QVector', 'QString',
    'QHostAddress', 'Size', 'Rect', 'Point',
}

# ============================================================
# 辅助函数
# ============================================================

def protect_patterns(text, patterns, placeholder_prefix):
    """
    用占位符保护文本中的特定模式，防止被后续正则误伤。
    返回 (替换后文本, 占位符→原文的字典)

    patterns: 正则表达式列表，每个匹配都会被保护
    """
    protected = {}

    def make_protector():
        def protector(m):
            key = f"\x00{placeholder_prefix}{len(protected)}\x00"
            protected[key] = m.group(0)
            return key
        return protector

    for pat in patterns:
        text = re.sub(pat, make_protector(), text)

    return text, protected


def restore_protected(text, protected):
    """将占位符还原为原文"""
    for key, value in protected.items():
        text = text.replace(key, value)
    return text


# ============================================================
# 逐行格式化规则（不跨行）
# ============================================================

def format_line(line):
    """
    对单行代码应用所有空格规则。
    预处理指令（#include 等）、注释行不做处理。
    """
    # 预处理指令不处理（如 #include <...>）
    if line.lstrip().startswith('#'):
        return line

    stripped = line.lstrip()
    if not stripped:
        return line

    # 注释行不处理
    if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
        return line

    # 保留行首缩进
    leading = line[:len(line) - len(stripped)]
    t = stripped

    # --------------------------------------------------
    # 第一步：保护模板语法和字符串字面量
    # --------------------------------------------------
    # 模板模式：<类型名> 或 <命名空间::类型名>
    # 例如 <uchar>、<wechat_qrcode::WeChatQRCode>、<float>
    # 如果不保护，后面的 < > 比较运算符规则会破坏它们
    t, protected = protect_patterns(t, [
        r'<\s*\w+(\s*::\s*\w+)*\s*>',   # <type> 或 <ns::type>
        r'"[^"]*"',                       # 字符串字面量 "..."
    ], 'PROT')

    # --------------------------------------------------
    # 第二步：关键字后的空格
    # --------------------------------------------------
    # if( → if (、for( → for (、while( → while (、switch( → switch (
    for kw in ['if', 'for', 'while', 'switch', 'catch']:
        t = re.sub(r'\b' + kw + r'\(', kw + ' (', t)
    # else if( → else if (
    t = re.sub(r'\belse\s+if\(', 'else if (', t)

    # --------------------------------------------------
    # 第三步：大括号前加空格
    # --------------------------------------------------
    # }else → } else         （将 else 从 } 上拆下来）
    t = re.sub(r'\}else\b', '} else', t)
    # ){ → ) {               （条件后的 { 前加空格）
    t = re.sub(r'\)\{', ') {', t)
    # else{ → else {         （else 后的 { 前加空格）
    t = re.sub(r'\belse\{', 'else {', t)

    # --------------------------------------------------
    # 第四步：逗号和分号后的空格
    # --------------------------------------------------
    # ,x → , x               （逗号后加空格，但不破坏字符串内的逗号）
    t = re.sub(r',([^\s"\'\\])', r', \1', t)
    # ;next → ; next         （同行多语句时分号后加空格）
    t = re.sub(r';([a-zA-Z_])', r'; \1', t)

    # --------------------------------------------------
    # 第五步：赋值 = 两侧加空格
    # --------------------------------------------------
    # 匹配标识符]=值 或 标识符=值 的模式，但排除 == != <= >= 等复合运算符
    # 例如：x=y → x = y、arr[0]=5 → arr[0] = 5
    t = re.sub(r'([a-zA-Z0-9_\]\)])=([^= ])', r'\1 = \2', t)
    # 行尾的 = 也要处理
    t = re.sub(r'([a-zA-Z0-9_\]\)])=$', r'\1 = ', t)

    # --------------------------------------------------
    # 第六步：比较运算符两侧加空格
    # --------------------------------------------------
    # == != <= >= && ||
    for op in ['==', '!=', '<=', '>=', '&&', r'\|\|']:
        clean_op = op.replace('\\', '')  # 去掉转义符用于替换
        t = re.sub(
            r'([a-zA-Z0-9_)\]])' + op + r'([a-zA-Z0-9_\[\(!])',
            r'\1 ' + clean_op + r' \2',
            t
        )

    # --------------------------------------------------
    # 第七步：逻辑非 ! 后面不留空格
    # --------------------------------------------------
    # ( ! x) → (!x)
    t = re.sub(r'\(\s*!\s*', '(!', t)
    # 通用：! 后面跟标识符时去掉中间空格
    t = re.sub(r'!\s+([a-zA-Z_])', r'!\1', t)

    # --------------------------------------------------
    # 第八步：比较 < > 两侧加空格
    # --------------------------------------------------
    # 此时模板语法已被保护，剩下的 < > 都是比较运算符
    t = re.sub(r'([a-zA-Z0-9_\)\]])\s*<\s*([a-zA-Z0-9_\(])', r'\1 < \2', t)
    t = re.sub(r'([a-zA-Z0-9_\)\]])\s*>\s*([a-zA-Z0-9_\(])', r'\1 > \2', t)

    # --------------------------------------------------
    # 第九步：流运算符 << >> 两侧加空格
    # --------------------------------------------------
    # cout<<x → cout << x、qDebug()<<"text" → qDebug() << "text"
    t = re.sub(r'(\w|\)|\]|")<<(\w|")', r'\1 << \2', t)
    t = re.sub(r'(\w|\)|\]|")>>(\w|")', r'\1 >> \2', t)

    # --------------------------------------------------
    # 第十步：位运算符 | & 两侧加空格
    # --------------------------------------------------
    # flag|mask → flag | mask（不破坏 ||）
    t = re.sub(r'(\w|\]|\))\|(\w|\()', r'\1 | \2', t)
    # val&0xff → val & 0xff（不破坏 &&）
    t = re.sub(r'([a-zA-Z0-9_\)\]]\S)&(\d)', r'\1 & \2', t)
    t = re.sub(r'([a-zA-Z0-9_\)\]]\S)&([a-zA-Z_])', r'\1 & \2', t)

    # --------------------------------------------------
    # 第十一步：算术运算符两侧加空格
    # --------------------------------------------------
    # )+ 和 ]+ 后加空格（如 val[2])+"text" → val[2]) + "text"）
    t = re.sub(r'(\)|\])\+', r'\1 + ', t)
    # )- 和 ]- 后加空格
    t = re.sub(r'(\)|\])\-', r'\1 - ', t)
    # )* ( → 保持不变，但 数字*( 需要加空格（如 0.001*( → 0.001 * (）
    t = re.sub(r'(\d)\*\(', r'\1 * (', t)
    t = re.sub(r'(\))\*\(', r'\1 * (', t)

    # --------------------------------------------------
    # 第十二步：还原保护的模板和字符串
    # --------------------------------------------------
    t = restore_protected(t, protected)

    # --------------------------------------------------
    # 第十三步：清理多余空格
    # --------------------------------------------------
    # 多个连续空格合并为一个
    t = re.sub(r' {2,}', ' ', t)
    # 分号前多余空格去掉
    t = re.sub(r' +;', ';', t)

    return leading + t


# ============================================================
# 跨行格式化规则
# ============================================================

def collapse_braces(lines):
    """
    将 if/for/while/switch 的条件行和下一行的 { 合并为一行。

    例如：
        if (condition)
        {              →  if (condition) {
    """
    result = []
    skip_next = False

    for i, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue

        s = line.rstrip()
        nxt = lines[i + 1].rstrip() if i + 1 < len(lines) else ""

        # 下一行是否只有一个 {
        if nxt.lstrip().startswith('{'):
            ls = s.lstrip()
            # 是控制流关键字行？
            is_control = any(
                ls.startswith(kw + ' (') or ls.startswith(kw + '(')
                for kw in ['if', 'else if', 'for', 'while', 'switch']
            )
            # 或者是 } else 行？
            is_else = ls.startswith('} else')

            if is_control or is_else:
                result.append(s + ' {')
                # 处理 { 后面可能还有内容的情况（极少见）
                remaining = nxt.lstrip()[1:].lstrip()
                if remaining:
                    result.append(' ' * (len(nxt) - len(nxt.lstrip())) + remaining)
                skip_next = True
                continue

        result.append(line.rstrip('\n'))

    return [l + '\n' for l in result]


def split_else_lines(text):
    """
    将 } else 拆分为两行（else 独立成行）。

    例如：
        } else if (cond) {   →   }
                                 else if (cond) {
        } else {             →   }
                                 else {
        } else stmt;         →   }
                                 else stmt;

    缩进与原来的 } 保持一致。
    """
    # } else if (condition) { → }\n    else if (condition) {
    text = re.sub(
        r'^(\s*)\}\s*(else if\s*\([^)]*\))\s*\{',
        lambda m: m.group(1) + '}\n' + m.group(1) + m.group(2) + ' {',
        text,
        flags=re.MULTILINE
    )

    # } else { → }\n    else {
    text = re.sub(
        r'^(\s*)\}\s*else\s*\{',
        lambda m: m.group(1) + '}\n' + m.group(1) + 'else {',
        text,
        flags=re.MULTILINE
    )

    # } else 语句; → }\n    else 语句;
    text = re.sub(
        r'^(\s*)\}\s*else\s+([^{])',
        lambda m: m.group(1) + '}\n' + m.group(1) + 'else ' + m.group(2),
        text,
        flags=re.MULTILINE
    )

    return text


# ============================================================
# 文件处理
# ============================================================

def format_file(filepath, dry_run=False):
    """
    格式化单个文件。

    处理流程：
      1. 逐行应用空格规则
      2. 折叠控制流的大括号（collapse_braces）
      3. 拆分 else 到独立行（split_else_lines）

    返回修改行数。
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    original = ''.join(lines)

    # 第 1 遍：逐行空格规则
    for i in range(len(lines)):
        new_line = format_line(lines[i])
        if new_line != lines[i].rstrip('\n'):
            lines[i] = new_line + '\n'

    # 第 2 遍：折叠大括号
    lines = collapse_braces(lines)

    # 第 3 遍：拆分 else 到独立行
    text = ''.join(lines)
    text = split_else_lines(text)

    if not dry_run and text != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text)

    # 计算修改行数
    new_lines = text.split('\n')
    old_lines = original.split('\n')
    changed = sum(1 for i, (o, n) in enumerate(zip(old_lines, new_lines)) if o != n)
    changed += abs(len(new_lines) - len(old_lines))

    return changed


def find_files(root_dir):
    """递归查找所有 C++ 源文件"""
    result = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # 跳过隐藏目录和常见的非源码目录
        dirnames[:] = [d for d in dirnames if not d.startswith('.') and d not in ('build', 'cmake-build')]
        for f in filenames:
            if f.endswith(EXTENSIONS) and not f.startswith('moc_') and not f.startswith('ui_'):
                result.append(os.path.join(dirpath, f))
    return result


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='C++ 代码空格规范化工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python3 cpp_format.py                  # 格式化当前目录
  python3 cpp_format.py /path/to/project # 格式化指定目录
  python3 cpp_format.py --dry-run        # 仅预览，不修改文件
        """
    )
    parser.add_argument('path', nargs='?', default='.',
                        help='项目根目录路径（默认当前目录）')
    parser.add_argument('--dry-run', action='store_true',
                        help='预览模式：显示修改行数但不写入文件')
    args = parser.parse_args()

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print(f"错误：路径不存在 - {root}")
        sys.exit(1)

    files = find_files(root)
    print(f"找到 {len(files)} 个 C++ 源文件")
    print(f"模式：{'预览（不修改）' if args.dry_run else '直接修改'}\n")

    total_changed = 0
    for f in files:
        changed = format_file(f, dry_run=args.dry_run)
        rel = os.path.relpath(f, root)
        if changed > 0:
            print(f"  [{changed:4d} 行] {rel}")
        total_changed += changed

    print(f"\n共修改 {total_changed} 行。{'（预览模式，未实际写入）' if args.dry_run else ''}")


if __name__ == "__main__":
    main()
