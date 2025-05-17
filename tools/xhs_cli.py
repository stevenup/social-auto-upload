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
import re

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
    parser.add_argument("--tag_delay", type=float, default=1.0, help="标签请求之间的延迟时间（秒），默认1秒")
    parser.add_argument("--max_tags", type=int, default=20, help="最大处理标签数量，默认20个")
    
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


def get_topic_tags(xhs_client, tags, tag_delay=1.0, max_tags=20):
    """获取话题标签，并添加频率控制
    
    Args:
        xhs_client: XhsClient 实例
        tags: 标签列表
        tag_delay: 每次请求之间的延迟时间（秒）
        max_tags: 最大处理标签数量
        
    Returns:
        处理后的话题对象列表和话题名称列表
    """
    topics = []
    hash_tags = []
    
    # 限制最大处理标签数量
    tags_to_process = tags[:max_tags] if max_tags > 0 else tags
    total_tags = len(tags_to_process)
    
    print(f"\n开始处理话题标签，共 {total_tags} 个标签")
    
    for idx, tag in enumerate(tags_to_process):
        try:
            print(f"处理标签 [{idx+1}/{total_tags}]: {tag}")
            topic_official = xhs_client.get_suggest_topic(tag)
            
            if topic_official and len(topic_official) > 0:
                topic_official[0]['type'] = 'topic'
                topic_one = topic_official[0]
                hash_tag_name = topic_one['name']
                hash_tags.append(hash_tag_name)
                topics.append(topic_one)
                print(f"✓ 获取成功: #{hash_tag_name}[话题]#")
            else:
                print(f"✗ 未找到匹配话题: {tag}")
            
            # 请求间隔，避免风控
            if idx < total_tags - 1 and tag_delay > 0:
                print(f"等待 {tag_delay} 秒...")
                sleep(tag_delay)
                
        except Exception as e:
            print(f"✗ 获取话题 {tag} 失败: {e}")
            # 发生错误后等待更长时间
            if idx < total_tags - 1 and tag_delay > 0:
                longer_delay = tag_delay * 2
                print(f"发生错误，等待 {longer_delay} 秒...")
                sleep(longer_delay)
    
    print(f"\n成功处理 {len(topics)}/{total_tags} 个话题标签")
    return topics, hash_tags


def upload_video(args):
    """上传视频"""
    # 获取cookies
    cookies = get_cookies(args)
    if not cookies:
        print("无法获取有效的cookies")
        return {"success": False, "error": "无法获取有效的cookies"}
    
    # 初始化客户端
    xhs_client = XhsClient(cookies, sign=sign_local, timeout=60)
    
    # 验证cookies
    try:
        xhs_client.get_video_first_frame_image_id("3214")
        print("Cookie验证成功")
    except Exception as e:
        print(f"Cookie验证失败: {e}")
        return {"success": False, "error": "Cookie验证失败"}
    
    # 准备参数
    video_path = args.video_path
    
    # 获取文件名作为默认标题
    if not args.title:
        title = Path(video_path).stem
    else:
        title = args.title
    
    # 解析标签 - 只处理 "#标签1 #标签2 #标签3" 格式
    tags = []
    if args.tags:
        # 预处理标签字符串，替换所有空白字符（包括不间断空格\xa0）为普通空格
        normalized_tags = re.sub(r'\s+', ' ', args.tags).strip()
        
        # 使用正则表达式提取所有以#开头的标签
        tag_matches = re.findall(r'#([^#\s]+)', normalized_tags)
        
        if not tag_matches:
            print(f"错误: 标签格式不正确，请使用 \"#标签1 #标签2 #标签3\" 格式")
            return {"success": False, "error": "标签格式不正确"}
            
        # 清理每个标签
        for match in tag_matches:
            clean_tag = match.strip()
            
            if clean_tag:
                tags.append(clean_tag)
        
        print(f"解析出的标签列表: {tags}")
    
    # 获取话题标签，使用优化后的函数
    topics, hash_tags = get_topic_tags(
        xhs_client, 
        tags, 
        tag_delay=args.tag_delay,
        max_tags=args.max_tags
    )

    # 添加打印语句查看 topics 的格式
    print("\n话题列表 topics 的格式:")
    print(json.dumps(topics, ensure_ascii=False, indent=2))
    
    # 准备话题标签字符串
    hash_tags_str = ' ' + ' '.join(['#' + tag + '[话题]#' for tag in hash_tags])
    
    # 准备描述
    if args.desc:
        desc = args.desc
        # if args.tags:
        #     desc += "\n\n\n" + args.tags
        if hash_tags_str.strip():
            desc += "\n\n\n" + hash_tags_str
    else:
        desc = title
        # if args.tags:
        #     desc += "\n\n\n" + args.tags
        if hash_tags_str.strip():
            desc += "\n\n\n" + hash_tags_str
    
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
    print(f"话题标签: {hash_tags_str}")
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
        
        return {"success": True, "data": note}
    
    except Exception as e:
        print(f"上传失败: {e}")
        return {"success": False, "error": str(e)}


def main():
    """主函数"""
    # 解析命令行参数
    args = parse_args()
    
    # 验证视频路径
    if not validate_video_path(args.video_path):
        return {"success": False, "error": "视频路径验证失败"}
    
    # 上传视频并返回结果
    result = upload_video(args)
    
    # 打印结果但不退出
    if result["success"]:
        print("视频上传成功!")
    else:
        print("视频上传失败!")
        
    return result


if __name__ == "__main__":
    result = main()
    # 设置退出码但仍然让调用者能访问结果
    sys.exit(0 if result.get("success", False) else 1)
