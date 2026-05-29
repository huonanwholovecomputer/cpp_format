#!/usr/bin/env python3
"""
C++ 代码空格规范化 + 缩进标准化脚本
=======================================
将此脚本放在项目根目录下运行，自动格式化 .cpp / .h 文件。

格式化规则：
  1. 关键字后空格：if( → if (、for( → for (
  2. 大括号前空格：){ → ) {、else{ → else {
  3. 逗号 / 分号后空格
  4. 赋值 = 两侧空格
  5. 比较运算符 == != <= >= && || 两侧空格
  6. 逻辑非 ! 后不留空格
  7. 比较 < > 两侧空格（保护模板语法 at<uchar>）
  8. 流 << >> 两侧空格
  9. 位运算符 | & 两侧空格
 10. 算术 + - 两侧空格
 11. 数字 * ( 加空格：0.001*( → 0.001 * (
 12. else / else if 独立成行
 13. 合并控制流 { 到同行
 14. 缩进标准化：tab→4空格，对齐到 4 的倍数

重要安全机制：
  - 先保护所有字符串和模板语法，处理完后还原，防止误伤
  - 不修改预处理指令和注释

用法：
  python3 cpp_format.py                    # 格式化当前目录
  python3 cpp_format.py /path/to/project   # 格式化指定目录
  python3 cpp_format.py --dry-run          # 预览变更，不写入
"""

import re
import os
import sys
import argparse

# ============================================================
# 配置
# ============================================================

EXTENSIONS = ('.cpp', '.h', '.hpp', '.c', '.cc', '.cxx')


def protect_all(text):
    """
    用占位符保护模板语法、字符串字面量、字符字面量。
    返回 (替换后文本, 占位符→原文 的字典, 下一个可用序号)。

    保护内容：
      1. 模板语法：identifier<type::name>（如 at<uchar>、makePtr<ns::Type>）
         → 整个包括前面的标识符一起保护，防止 < > 被当成比较运算符破坏
      2. 字符串字面量："..."
      3. 字符字面量：'...'
    """
    protected = {}
    counter = [0]

    def prot(m):
        key = f"\x00PT{counter[0]}\x00"
        counter[0] += 1
        protected[key] = m.group(0)
        return key

    # 1. 保护完整模板：标识符<类型::子类型> 如 at<uchar>、makePtr<wechat_qrcode::WeChatQRCode>
    text = re.sub(
        r'\b\w+\s*<\s*\w+(\s*::\s*\w+)*\s*>',
        prot, text
    )

    # 2. 保护字符串字面量
    text = re.sub(r'"[^"]*"', prot, text)

    # 3. 保护字符字面量
    text = re.sub(r"'[^']*'", prot, text)

    return text, protected, counter[0]


def restore_all(text, protected):
    """还原所有被保护的占位符"""
    for key, val in protected.items():
        text = text.replace(key, val)
    return text


def normalize_indent(line):
    """
    标准化缩进：tab → 4 个空格，然后对齐到 4 的倍数。
    仅处理行首的空白字符。
    """
    if not line or line[0] not in (' ', '\t'):
        return line

    stripped = line.lstrip()
    leading = line[:len(line) - len(stripped)]

    # tab → 4 spaces
    leading = leading.replace('\t', '    ')

    # 对齐到 4 的倍数（只能处理纯空格的情况）
    space_count = len(leading)
    # 修正：舍入到最近 4 的倍数
    target = round(space_count / 4) * 4
    # 但不做大幅修改（可能是故意的半缩进），仅修正常见偏移
    if space_count > 0 and abs(space_count - target) <= 2 and target > 0:
        leading = ' ' * target

    return leading + stripped


def format_line(line):
    """
    对单行代码应用空格规则。
    注意：入参 line 不得包含行尾换行符！
    返回格式化后的行（不含行尾换行符）。
    """
    # 预处理指令（#include 等）不处理
    if line.lstrip().startswith('#'):
        return line

    stripped = line.lstrip()
    if not stripped:
        return line

    # 注释行不处理
    if stripped.startswith('//') or stripped.startswith('/*'):
        return line

    leading = line[:len(line) - len(stripped)]
    t = stripped

    # ---- 保护模板和字符串 ----
    t, protected, _ = protect_all(t)

    # ---- 关键字后空格 ----
    for kw in ['if', 'for', 'while', 'switch', 'catch']:
        t = re.sub(r'\b' + kw + r'\(', kw + ' (', t)
    t = re.sub(r'\belse\s+if\(', 'else if (', t)

    # ---- 大括号前空格 ----
    t = re.sub(r'\}else\b', '} else', t)       # }else → } else
    t = re.sub(r'\)\{', ') {', t)               # ){ → ) {
    t = re.sub(r'\belse\{', 'else {', t)        # else{ → else {

    # ---- 逗号、分号后空格 ----
    t = re.sub(r',([^\s])', r', \1', t)         # ,x → , x
    t = re.sub(r';([a-zA-Z_])', r'; \1', t)      # ;x → ; x

    # ---- 赋值 = 两侧空格（跳过 == != <= >=）----
    t = re.sub(r'([a-zA-Z0-9_\]\)])=([^= ])', r'\1 = \2', t)
    t = re.sub(r'([a-zA-Z0-9_\]\)])=$', r'\1 = ', t)

    # ---- 比较运算符 ----
    for op in ['==', '!=', '<=', '>=', '&&', r'\|\|']:
        clean = op.replace('\\', '')
        t = re.sub(
            r'([a-zA-Z0-9_)\]])' + op + r'([a-zA-Z0-9_\[\(!])',
            r'\1 ' + clean + r' \2', t
        )

    # ---- ! 逻辑非后不留空格 ----
    t = re.sub(r'\(\s*!\s*', '(!', t)
    t = re.sub(r'!\s+([a-zA-Z_])', r'!\1', t)

    # ---- 比较 < > 两侧空格（模板已保护，剩下都是比较）----
    t = re.sub(r'([a-zA-Z0-9_\)\]])\s*<\s*([a-zA-Z0-9_\(])', r'\1 < \2', t)
    t = re.sub(r'([a-zA-Z0-9_\)\]])\s*>\s*([a-zA-Z0-9_\(])', r'\1 > \2', t)

    # ---- 流运算符 << >> ----
    t = re.sub(r'(\w|\)|\]|")<<(\w|")', r'\1 << \2', t)
    t = re.sub(r'(\w|\)|\]|")>>(\w|")', r'\1 >> \2', t)

    # ---- 位运算符 | &（不破坏 || &&）----
    t = re.sub(r'(\w|\]|\))\|(\w|\()', r'\1 | \2', t)
    t = re.sub(r'([a-zA-Z0-9_\)\]]\S)&(\d)', r'\1 & \2', t)
    t = re.sub(r'([a-zA-Z0-9_\)\]]\S)&([a-zA-Z_])', r'\1 & \2', t)

    # ---- 算术 + -（在 ) 或 ] 之后的）----
    t = re.sub(r'(\)|\])\+', r'\1 + ', t)
    t = re.sub(r'(\)|\])\-', r'\1 - ', t)

    # ---- 数字*( → 数字 * ( ----
    t = re.sub(r'(\d)\*\(', r'\1 * (', t)
    t = re.sub(r'(\))\*\(', r'\1 * (', t)

    # ---- 还原保护的模板和字符串 ----
    t = restore_all(t, protected)

    # ---- 清理多余空格 ----
    t = re.sub(r' {2,}', ' ', t)       # 多个空格合并
    t = re.sub(r' +;', ';', t)          # 分号前多余空格

    return leading + t


# ============================================================
# 跨行处理
# ============================================================

def collapse_braces(lines):
    """
    如果控制流语句的下一行只有一个 {，合并到同行。
    例如：if (...)\n    {   →   if (...) {
    """
    result = []
    skip = False
    for i, line in enumerate(lines):
        if skip:
            skip = False
            continue
        s = line.rstrip()
        nxt = lines[i + 1].rstrip() if i + 1 < len(lines) else ""
        if nxt.lstrip().startswith('{'):
            ls = s.lstrip()
            is_ctrl = any(
                ls.startswith(kw + ' (') or ls.startswith(kw + '(')
                for kw in ['if', 'else if', 'for', 'while', 'switch']
            )
            if is_ctrl or ls.startswith('} else'):
                result.append(s + ' {')
                rem = nxt.lstrip()[1:].lstrip()
                if rem:
                    result.append(' ' * (len(nxt) - len(nxt.lstrip())) + rem)
                skip = True
                continue
        result.append(line)
    return result


def split_else_lines(text):
    """
    将 } else 拆分为两行（else 独立成行）。
    例如：    } else {   →   }\n    else {
    """
    # } else if (cond) { → }\n    else if (cond) {
    text = re.sub(
        r'^(\s*)\}\s*(else if\s*\([^)]*\))\s*\{',
        lambda m: m.group(1) + '}\n' + m.group(1) + m.group(2) + ' {',
        text, flags=re.MULTILINE
    )
    # } else { → }\n    else {
    text = re.sub(
        r'^(\s*)\}\s*else\s*\{',
        lambda m: m.group(1) + '}\n' + m.group(1) + 'else {',
        text, flags=re.MULTILINE
    )
    # } else 语句; → }\n    else 语句;
    text = re.sub(
        r'^(\s*)\}\s*else\s+([^{])',
        lambda m: m.group(1) + '}\n' + m.group(1) + 'else ' + m.group(2),
        text, flags=re.MULTILINE
    )
    return text


# ============================================================
# 文件处理
# ============================================================

def format_file(filepath, dry_run=False):
    """
    格式化单个文件。处理流程：
      1. 标准化缩进（normalize_indent）
      2. 逐行空格规则（format_line）
      3. 合并控制流大括号（collapse_braces）
      4. 拆分 else 到独立行（split_else_lines）
    """
    # 二进制模式读取，保留原始行尾样式
    with open(filepath, 'rb') as f:
        raw = f.read()

    # 检测原始行尾样式
    if b'\r\n' in raw:
        line_ending = '\r\n'
    elif b'\r' in raw:
        line_ending = '\r'
    else:
        line_ending = '\n'

    text = raw.decode('utf-8')
    original = text
    lines = text.split('\n')  # 用 \n 分割，\r 会在 rstrip 时处理

    # 第 1 遍：缩进标准化
    for i in range(len(lines)):
        lines[i] = normalize_indent(lines[i])

    # 第 2 遍：逐行空格规则
    for i in range(len(lines)):
        # format_line 期望不含行尾符的纯文本行
        clean = lines[i].rstrip('\r')
        formatted = format_line(clean)
        if formatted != clean:
            lines[i] = formatted

    # 第 3 遍：合并大括号
    lines = collapse_braces(lines)

    # 第 4 遍：拆分 else 到独立行
    text = '\n'.join(lines)
    text = split_else_lines(text)

    # 还原正确的行尾样式
    if line_ending != '\n':
        text = text.replace('\n', line_ending)

    if not dry_run and text != original:
        with open(filepath, 'wb') as f:
            f.write(text.encode('utf-8'))

    # 统计修改行数
    old_lines = original.split('\n')
    new_lines = text.split('\n')
    changed = sum(1 for i, (o, n) in enumerate(zip(old_lines, new_lines))
                  if o.rstrip('\r') != n.rstrip('\r'))
    changed += abs(len(new_lines) - len(old_lines))
    return changed


def find_files(root_dir):
    """递归查找 C++ 源文件，跳过自动生成文件"""
    result = []
    skip_prefix = ('moc_', 'ui_', 'robot_control_lcmt')
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames
                       if not d.startswith('.')
                       and d not in ('build', 'cmake-build-debug', 'cmake-build-release')]
        for f in filenames:
            if f.endswith(EXTENSIONS) and not f.startswith(skip_prefix):
                result.append(os.path.join(dirpath, f))
    return result


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='C++ 代码空格规范化 + 缩进标准化工具')
    parser.add_argument('path', nargs='?', default='.',
                        help='项目根目录（默认当前目录）')
    parser.add_argument('--dry-run', action='store_true',
                        help='预览模式，不实际修改文件')
    args = parser.parse_args()

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print(f"错误：路径不存在 - {root}")
        sys.exit(1)

    files = find_files(root)
    print(f"找到 {len(files)} 个 C++ 源文件")
    if args.dry_run:
        print("模式：预览（不修改文件）\n")
    else:
        print("模式：直接修改\n")

    total = 0
    for f in files:
        changed = format_file(f, dry_run=args.dry_run)
        rel = os.path.relpath(f, root)
        if changed:
            print(f"  [{changed:4d} 行变更] {rel}")
        total += changed

    print(f"\n共 {total} 行变更。" +
          ("（预览模式，未实际写入）" if args.dry_run else ""))


if __name__ == "__main__":
    main()
