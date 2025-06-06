import os
import sys
from pathlib import Path
import re
import json
from datetime import datetime
from time import sleep
import configparser

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conf import BASE_DIR
from uploader.xhs_uploader.main import sign_local, beauty_print
from xhs import XhsClient

def _get_cookies_from_sources(
    cookies_str: str = None,
    cookie_file: str = None,
    config_file_path: Path = None,
    account: str = None,
    base_dir_path: Path = None
):
    """
    Attempts to retrieve cookies from various sources in a specific order.
    1. Directly provided cookies_str.
    2. cookie_file.
    3. config_file_path for a specific account.

    Returns:
        tuple: (cookies_str, error_message)
            - cookies_str (str): The cookie string if found, otherwise None
            - error_message (str): An error message if an error occurred, otherwise None
    """
    if cookies_str:
        return cookies_str, None

    if cookie_file:
        try:
            with open(cookie_file, 'r', encoding='utf-8') as f:
                return f.read().strip(), None
        except Exception as e:
            return None, f"Failed to read cookie file '{cookie_file}': {str(e)}"

    cfg_path = config_file_path
    if not cfg_path and base_dir_path:
        cfg_path = base_dir_path / "uploader" / "xhs_uploader" / "accounts.ini"
    elif not cfg_path:
        return None, "Configuration file path not provided and default path cannot be determined."

    if cfg_path:
        _config = configparser.RawConfigParser()
        try:
            if not cfg_path.exists():
                return None, f"Config file not found: {cfg_path}"
            _config.read(cfg_path, encoding='utf-8')
            if account not in _config:
                return None, f"Account '{account}' not found in config file '{cfg_path}'"
            
            cookies_from_config = _config[account].get('cookies')
            if not cookies_from_config:
                return None, f"No 'cookies' found for account '{account}' in config file '{cfg_path}'"
            return cookies_from_config, None
        except Exception as e:
            return None, f"Failed to read cookies for account '{account}' from config file '{cfg_path}': {str(e)}"
    
    return None, None

def upload_video_to_xhs(
    # Required parameters
    video_path: str,
    
    # Optional parameters
    title: str = None,
    tags: str = None,
    desc: str = None,
    cover_path: str = None,
    cookie_file: str = None,
    account: str = "account1",
    config_file: str = None,
    publish_time: str = None,
    private: bool = False,
    no_sleep: bool = False,
    sleep_time: int = 30,
    tag_delay: float = 1.0,
    max_tags: int = 20,
    cookies_str: str = None,
    silent: bool = True
):
    """
    Uploads a video to Xiaohongshu (Little Red Book).

    Args:
        video_path (str): Path to the video file (required).
        title (str, optional): Video title. Defaults to filename stem.
        tags (str, optional): Space-separated tags, e.g., "#tag1 #tag2".
        desc (str, optional): Video description. Defaults to title.
        cover_path (str, optional): Path to the cover image file.
        cookie_file (str, optional): Path to the cookie file.
        account (str, optional): Account name in config file. Defaults to "account1".
        config_file (str, optional): Path to the config file.
        publish_time (str, optional): Scheduled publish time "YYYY-MM-DD HH:MM:SS".
        private (bool, optional): Set to True for private upload.
        no_sleep (bool, optional): Set to True to disable sleep after upload.
        sleep_time (int, optional): Sleep duration in seconds after upload.
        tag_delay (float, optional): Delay between topic tag lookups.
        max_tags (int, optional): Maximum number of tags to process.
        cookies_str (str, optional): Pass cookies directly as a string.
        silent (bool, optional): Suppress print outputs.

    Returns:
        dict: {
            "status": int,      # 200 for success, other codes for various error types
            "message": str,     # Success message or error description
            "data": dict        # Present only when status is 200
        }
    """
    old_stdout = None
    if silent:
        old_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')

    try:
        # Validate video path
        path = Path(video_path)
        if not path.exists() or not path.is_file():
            return {
                "status": 404,
                "message": f"Video file not found or is not a file: {video_path}"
            }
        if path.suffix.lower() not in ['.mp4', '.mov', '.avi', '.mkv']:
            return {
                "status": 400,
                "message": f"Unsupported video format: {path.suffix}. Supported: .mp4, .mov, .avi, .mkv"
            }

        # Get cookies
        _config_path_obj = Path(config_file) if config_file else None
        _cookies, cookie_error = _get_cookies_from_sources(
            cookies_str=cookies_str,
            cookie_file=cookie_file,
            config_file_path=_config_path_obj,
            account=account,
            base_dir_path=Path(BASE_DIR)
        )

        if cookie_error:
            return {
                "status": 401,
                "message": cookie_error
            }
        if not _cookies:
            return {
                "status": 401,
                "message": "Could not obtain valid cookies from any source"
            }

        # Initialize XHS Client
        xhs_client = XhsClient(_cookies, sign=sign_local, timeout=60)

        # Validate cookies by trying a simple API call
        try:
            response = xhs_client.get_video_first_frame_image_id("3214")
        except Exception as e:
            return {
                "status": 401,
                "message": f"Cookie validation failed: {str(e)}"
            }

        # Prepare title
        final_title = title if title else path.stem
        
        # Parse tags
        parsed_tags = []
        if tags:
            normalized_tags_str = re.sub(r'\s+', ' ', tags).strip()
            tag_matches = re.findall(r'#([^#\s]+)', normalized_tags_str)
            if not tag_matches and normalized_tags_str.startswith('#'):
                tag_matches = [normalized_tags_str[1:]]
            elif not tag_matches and normalized_tags_str:
                parsed_tags = normalized_tags_str.split()

            if tag_matches:
                parsed_tags = [match.strip() for match in tag_matches if match.strip()]
            elif not parsed_tags and tags and not tags.startswith('#'):
                parsed_tags = tags.split()

        # Get official topic tags
        topics = []
        hash_tags_names = []
        if parsed_tags:
            tags_to_process = parsed_tags[:max_tags] if max_tags > 0 else parsed_tags
            for idx, tag_name in enumerate(tags_to_process):
                try:
                    topic_official_list = xhs_client.get_suggest_topic(tag_name)
                    if topic_official_list and len(topic_official_list) > 0:
                        topic_official = topic_official_list[0]
                        topic_official['type'] = 'topic'
                        topics.append(topic_official)
                        hash_tags_names.append(topic_official['name'])
                    if idx < len(tags_to_process) - 1 and tag_delay > 0:
                        sleep(tag_delay)
                except Exception as e:
                    print(f"Warning: Failed to get topic for tag '{tag_name}': {e}")
                    if idx < len(tags_to_process) - 1 and tag_delay > 0:
                        sleep(tag_delay * 2)

        # Prepare description
        final_desc = desc if desc else final_title
        if hash_tags_names:
            hash_tags_str = ' '.join(['#' + ht_name + '[话题]#' for ht_name in hash_tags_names])
            final_desc += f"\n\n\n{hash_tags_str}"

        # Validate publish time
        post_time_str = None
        if publish_time:
            try:
                datetime.strptime(publish_time, "%Y-%m-%d %H:%M:%S")
                post_time_str = publish_time
            except ValueError:
                if silent and old_stdout:
                    sys.stdout = old_stdout
                print(f"Warning: Invalid publish_time format ('{publish_time}'). Publishing immediately. Use YYYY-MM-DD HH:MM:SS.")
                if silent:
                    sys.stdout = open(os.devnull, 'w')
                post_time_str = None

        # Upload video
        try:
            note = xhs_client.create_video_note(
                title=final_title[:20],
                video_path=str(path),
                desc=final_desc,
                topics=topics,
                cover_path=cover_path,
                is_private=private,
                post_time=post_time_str
            )
            
            # Sleep if not disabled
            if not no_sleep:
                if silent and old_stdout:
                    sys.stdout = old_stdout
                print(f"Sleeping for {sleep_time} seconds to avoid rate limits...")
                if silent:
                    sys.stdout = open(os.devnull, 'w')
                sleep(sleep_time)

            return {
                "status": 200,
                "message": "Video uploaded successfully",
                "data": note
            }

        except Exception as e:
            return {
                "status": 500,
                "message": f"XHS API upload failed: {str(e)}"
            }

    finally:
        if silent and old_stdout:
            sys.stdout.close()
            sys.stdout = old_stdout
