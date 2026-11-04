#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化测试脚本 - 测试新闻抓取功能（不调用 AI）
"""

import sys
import io
import feedparser
import os
from datetime import datetime

# 修复 Windows 控制台编码
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def test_fetch_news():
    """测试抓取新闻"""
    print("[START] 开始测试新闻抓取...")
    print("=" * 50)

    # 只测试一个简单的源
    test_feeds = [
        ('TechCrunch', 'https://techcrunch.com/feed/'),
    ]

    for name, url in test_feeds:
        try:
            print(f"[FETCH] 正在抓取: {name}")
            feed = feedparser.parse(url)

            if hasattr(feed, 'entries') and len(feed.entries) > 0:
                print(f"[OK] 成功获取 {len(feed.entries)} 条新闻")

                # 显示前3条
                for i, entry in enumerate(feed.entries[:3], 1):
                    print(f"\n  {i}. {entry.title}")
                    print(f"     链接: {entry.link}")
                    summary = entry.get('summary', entry.get('description', ''))[:100]
                    print(f"     摘要: {summary}...")
            else:
                print(f"[WARN] 未获取到新闻条目")

        except Exception as e:
            print(f"[ERROR] 抓取失败: {e}")

    print("\n" + "=" * 50)
    print("[DONE] 测试完成")

if __name__ == "__main__":
    test_fetch_news()
