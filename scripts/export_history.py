#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导出余额历史到 Excel。
示例：
    python scripts/export_history.py --range 2025-10-01:2025-10-27
    python scripts/export_history.py --range 2025-10-20:2025-10-27 --models deepseek --output archives/custom.xlsx
"""

import argparse
from datetime import datetime
from pathlib import Path

# 导入主程序模块（注意：当前项目的主文件名为deepseek_ok_3.0.py）
import sys
import os
import importlib.util

# 确保可以从项目根目录导入
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# 导入主模块（文件名包含点号，需要使用importlib）
module_path = os.path.join(BASE_DIR, 'deepseek_ok_3.0.py')
spec = importlib.util.spec_from_file_location("deepseek_ok_3_0", module_path)
deepseek_ok_3_0 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deepseek_ok_3_0)


def parse_range(range_str: str):
    try:
        start_str, end_str = range_str.split(':', 1)
        start_date = datetime.strptime(start_str.strip(), '%Y-%m-%d')
        end_date = datetime.strptime(end_str.strip(), '%Y-%m-%d')
        if start_date > end_date:
            raise ValueError("开始日期不能晚于结束日期")
        return start_date, end_date
    except Exception as exc:
        raise argparse.ArgumentTypeError(f"非法日期范围格式: {range_str}") from exc


def main():
    parser = argparse.ArgumentParser(description="导出余额历史到 Excel。")
    parser.add_argument('--range', required=True, help='日期范围，格式 YYYY-MM-DD:YYYY-MM-DD')
    parser.add_argument('--models', default=None, help='导出的模型，逗号分隔（默认导出全部）')
    parser.add_argument('--output', default=None, help='输出文件路径（默认生成在 archives/ 目录）')
    args = parser.parse_args()

    start_date, end_date = parse_range(args.range)
    models = [m.strip() for m in args.models.split(',')] if args.models else deepseek_ok_3_0.MODEL_ORDER

    start_ts = start_date.strftime('%Y-%m-%d 00:00:00')
    end_ts = end_date.strftime('%Y-%m-%d 23:59:59')

    if args.output:
        output_path = Path(args.output)
    else:
        filename = f"balances-{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}.xlsx"
        output_path = deepseek_ok_3_0.ARCHIVE_DIR / filename

    deepseek_ok_3_0.history_store.export_range_to_excel(start_ts, end_ts, output_path, models=models)
    print(f"✅ 历史数据导出完成: {output_path}")


if __name__ == '__main__':
    main()
