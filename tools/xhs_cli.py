#!/usr/bin/env python3
"""
小红书视频上传命令行工具

用法:
    python xhs_cli.py --video_path /path/to/video.mp4 --title "视频标题" --tags "#标签1 #标签2 #标签3" --desc "视频描述" --cover /path/to/cover.jpg
"""

import argparse
import configparser
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from time import sleep

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conf import BASE_DIR
from uploader.xhs_uploader.main import sign_local, beauty_print
from xhs import XhsClient


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="小红书视频上传工具")
    
    # 必需参数
    parser.add_argument("--video_path", type=str, required=True, help="视频文件路径")
    
    # 可选参数
    parser.add_argument("--title", type=str, help="视频标题")
    parser.add_argument("--tags", type=str, help="标签，用空格分隔，例如：#标签1 #标签2 #标签3")
    parser.add_argument("--desc", type=str, help="视频描述，不提供则自动生成")
    parser.add_argument("--cover", type=str, help="封面图片路径")
    parser.add_argument("--cookie_file", type=str, help="Cookie文件路径")
    parser.add_argument("--account", type=str, default="account1", help="账号名称，默认为account1")
    parser.add_argument("--config_file", type=str, help="配置文件路径")
    parser.add_argument("--publish_time", type=str, help="发布时间，格式为YYYY-MM-DD HH:MM:SS，不提供则立即发布")
    parser.add_argument("--private", action="store_true", help="是否私密发布，默认为公开")
    parser.add_argument("--no_sleep", action="store_true", help="上传后不休眠（默认会休眠30秒以避免风控）")
    parser.add_argument("--sleep_time", type=int, default=30, help="上传后休眠时间（秒），默认30秒")
    parser.add_argument("--batch", action="store_true", help="批量模式，遇到错误继续处理")
    
    return parser.parse_args()


def get_cookies(args):
    """获取Cookies"""
    # 优先使用Cookie文件
    if args.cookie_file:
        try:
            with open(args.cookie_file, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            print(f"读取Cookie文件失败: {e}")
            return None
    
    # 使用配置文件
    config = configparser.RawConfigParser()
    config_path = args.config_file or Path(BASE_DIR / "uploader" / "xhs_uploader" / "accounts.ini")
    
    try:
        config.read(config_path)
        return config[args.account]['cookies']
    except Exception as e:
        print(f"读取配置文件失败: {e}")
        return None


def validate_video_path(video_path):
    """验证视频文件路径"""
    path = Path(video_path)
    if not path.exists():
        print(f"错误: 视频文件 {video_path} 不存在")
        return False
    
    if not path.is_file():
        print(f"错误: {video_path} 不是一个文件")
        return False
    
    if path.suffix.lower() not in ['.mp4', '.mov', '.avi', '.mkv']:
        print(f"错误: 不支持的视频格式 {path.suffix}，支持的格式: .mp4, .mov, .avi, .mkv")
        return False
    
    return True


def upload_video(args):
    """上传视频"""
    # 获取cookies
    cookies = get_cookies(args)
    if not cookies:
        print("无法获取有效的cookies")
        return False
    
    # 初始化客户端
    xhs_client = XhsClient(cookies, sign=sign_local, timeout=60)
    
    # 验证cookies
    try:
        xhs_client.get_video_first_frame_image_id("3214")
        print("Cookie验证成功")
    except Exception as e:
        print(f"Cookie验证失败: {e}")
        return False
    
    # 准备参数
    video_path = args.video_path
    
    # 获取文件名作为默认标题
    if not args.title:
        title = Path(video_path).stem
    else:
        title = args.title
    
    # 解析标签
    if args.tags:
        # 解析标签字符串为列表
        raw_tags = args.tags.split(' ')
        tags = []
        for tag in raw_tags:
            # 去除前缀#和后缀[话题]#
            clean_tag = tag.lstrip('#').split('[')[0] if tag.startswith('#') else tag.lstrip('@')
            if clean_tag:
                tags.append(clean_tag)
    else:
        tags = []
    
    # 获取话题标签
    topics = []
    for tag in tags[:3]:  # 最多处理前3个标签
        try:
            topic_official = xhs_client.get_suggest_topic(tag)
            if topic_official and len(topic_official) > 0:
                topic_official[0]['type'] = 'topic'
                topics.append(topic_official[0])
        except Exception as e:
            print(f"获取话题 {tag} 失败: {e}")

    # 添加打印语句查看 topics 的格式
    print("\n话题列表 topics 的格式:")
    print(json.dumps(topics, ensure_ascii=False, indent=2))
    
    # 准备描述
    if args.desc:
        desc = args.desc + "\n\n\n" + args.tags
    else:
        desc = title + "\n\n\n" + args.tags
    
    # 准备发布时间
    post_time = None
    if args.publish_time:
        try:
            # 验证时间格式
            datetime.strptime(args.publish_time, "%Y-%m-%d %H:%M:%S")
            post_time = args.publish_time
        except ValueError:
            print(f"警告: 发布时间格式错误，将立即发布。正确格式为: YYYY-MM-DD HH:MM:SS")
    
    print(f"准备上传视频: {video_path}")
    print(f"标题: {title}")
    print(f"标签: {args.tags}")
    print(f"描述: {desc}")
    if args.cover:
        print(f"封面: {args.cover}")
    if post_time:
        print(f"计划发布时间: {post_time}")
    print(f"发布状态: {'私密' if args.private else '公开'}")
    
    # 上传视频
    try:
        note = xhs_client.create_video_note(
            title=title[:20],  # 小红书标题长度限制为20字符
            video_path=video_path,
            desc=desc,
            topics=topics,  # 使用处理后的话题对象列表
            cover_path=args.cover,
            is_private=args.private,
            post_time=post_time
        )
        
        print("\n上传成功! 笔记详情:")
        beauty_print(note)
        
        # 上传后休眠以避免风控
        if not args.no_sleep:
            sleep_time = args.sleep_time
            print(f"\n为避免风控，休眠 {sleep_time} 秒...")
            for i in range(sleep_time, 0, -1):
                sys.stdout.write(f"\r休眠中: {i} 秒剩余...")
                sys.stdout.flush()
                sleep(1)
            print("\n休眠结束")
        
        return True
    
    except Exception as e:
        print(f"上传失败: {e}")
        return False


def main():
    """主函数"""
    # 解析命令行参数
    args = parse_args()
    
    # 验证视频路径
    if not validate_video_path(args.video_path):
        sys.exit(1)
    
    # 上传视频
    if upload_video(args):
        print("视频上传成功!")
        sys.exit(0)
    else:
        print("视频上传失败!")
        sys.exit(1)


if __name__ == "__main__":
    main()
