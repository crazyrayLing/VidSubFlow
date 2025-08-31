def split_srt(input_srt, output_srt_en, output_srt_cn):
    with open(input_srt, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    en_lines = []
    cn_lines = []

    i = 0
    while i < len(lines):
        if i + 3 >= len(lines):
            # 说明剩余行数不够一条完整字幕，停止循环
            break

        en_lines.append(lines[i].strip() + '\n')       # 序号
        en_lines.append(lines[i + 1].strip() + '\n')   # 时间戳
        en_lines.append(lines[i + 3].strip() + '\n')   # 英文字幕
        en_lines.append('\n')                           # 空行

        cn_lines.append(lines[i].strip() + '\n')       # 序号
        cn_lines.append(lines[i + 1].strip() + '\n')   # 时间戳
        cn_lines.append(lines[i + 2].strip() + '\n')   # 中文字幕
        cn_lines.append('\n')                           # 空行

        if i + 4 < len(lines) and lines[i + 4].strip() == '':
            i += 5
        else:
            i += 4

    with open(output_srt_en, 'w', encoding='utf-8') as en_file:
        en_file.writelines(en_lines)

    with open(output_srt_cn, 'w', encoding='utf-8') as cn_file:
        cn_file.writelines(cn_lines)
