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

def upload_video_to_xhs(
    # Required parameters matching argparse
    video_path: str,
    
    # Optional parameters matching argparse
    title: str = None,
    tags: str = None, # Accepts string like "#tag1 #tag2"
    desc: str = None,
    cover_path: str = None,
    cookie_file: str = None,
    account: str = "account1",
    config_file: str = None,
    publish_time: str = None, # Accepts string "YYYY-MM-DD HH:MM:SS"
    private: bool = False,
    no_sleep: bool = False,
    sleep_time: int = 30,
    # batch: bool = False, # 'batch' argument seems unused in upload_video logic, omitting for API clarity unless needed
    tag_delay: float = 1.0,
    max_tags: int = 20,
    
    # API specific parameters (not from argparse)
    cookies_str: str = None, # Allow passing cookies directly as a string
    silent: bool = True
):
    """
    Uploads a video to Xiaohongshu (Little Red Book).
    Parameters match the definitions in tools/xhs_cli.py.

    Args:
        video_path (str): Path to the video file (required).
        title (str, optional): Video title. Defaults to filename stem.
        tags (str, optional): Space-separated tags, e.g., "#tag1 #tag2".
        desc (str, optional): Video description. Defaults to title.
        cover_path (str, optional): Path to the cover image file.
        cookie_file (str, optional): Path to the cookie file.
        account (str, optional): Account name in config file. Defaults to "account1".
        config_file (str, optional): Path to the config file. Defaults to uploader/xhs_uploader/accounts.ini.
        publish_time (str, optional): Scheduled publish time "YYYY-MM-DD HH:MM:SS". Defaults to immediate publish.
        private (bool, optional): Set to True for private upload. Defaults to False.
        no_sleep (bool, optional): Set to True to disable sleep after upload. Defaults to False.
        sleep_time (int, optional): Sleep duration in seconds after upload. Defaults to 30.
        tag_delay (float, optional): Delay between topic tag lookups. Defaults to 1.0.
        max_tags (int, optional): Maximum number of tags to process for topics. Defaults to 20.
        cookies_str (str, optional): Pass cookies directly as a string (overrides cookie_file/config_file).
        silent (bool, optional): Suppress print outputs. Defaults to True.

    Returns:
        dict: {"success": True, "data": {"id": "note_id", "score": score}} or
              {"success": False, "error": "error message"}
    """
    # Silence print statements if requested
    old_stdout = None
    if silent:
        old_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')

    try:
        # --- Parameter Validation and Preparation ---
        # Validate video path
        path = Path(video_path)
        if not path.exists() or not path.is_file():
            return {"success": False, "error": f"Video file not found or is not a file: {video_path}"}
        if path.suffix.lower() not in ['.mp4', '.mov', '.avi', '.mkv']:
             return {"success": False, "error": f"Unsupported video format: {path.suffix}. Supported: .mp4, .mov, .avi, .mkv"}

        # Get cookies
        _cookies = cookies_str # Prioritize directly passed cookies
        if not _cookies:
            if cookie_file:
                try:
                    with open(cookie_file, 'r', encoding='utf-8') as f:
                        _cookies = f.read().strip()
                except Exception as e:
                     return {"success": False, "error": f"Failed to read cookie file '{cookie_file}': {str(e)}"}
            else:
                _config = configparser.RawConfigParser()
                _config_path = config_file or Path(BASE_DIR / "uploader" / "xhs_uploader" / "accounts.ini")
                try:
                    if not Path(_config_path).exists():
                         return {"success": False, "error": f"Config file not found: {_config_path}"}
                    _config.read(_config_path, encoding='utf-8')
                    if account not in _config:
                         return {"success": False, "error": f"Account '{account}' not found in config file '{_config_path}'"}
                    _cookies = _config[account].get('cookies')
                except Exception as e:
                    return {"success": False, "error": f"Failed to read cookies for account '{account}' from config file '{_config_path}': {str(e)}"}
        
        if not _cookies:
            return {"success": False, "error": "Could not obtain valid cookies."}

        # --- Initialize XHS Client ---
        xhs_client = XhsClient(_cookies, sign=sign_local, timeout=60)

        # Validate cookies by trying a simple API call
        try:
            xhs_client.get_video_first_frame_image_id("3214") # Use a known valid (but likely non-existent) ID
        except Exception as e:
            # Catch potential exceptions during cookie validation
            return {"success": False, "error": f"Cookie validation failed: {str(e)}"}

        # --- Prepare Content ---
        # Title
        final_title = title if title else path.stem
        
        # Tags (Parse from string if provided)
        parsed_tags = []
        if tags:
            normalized_tags_str = re.sub(r'\s+', ' ', tags).strip()
            tag_matches = re.findall(r'#([^#\s]+)', normalized_tags_str)
            if not tag_matches and normalized_tags_str.startswith('#'): # Handle case like "#tag" without space
                 tag_matches = [normalized_tags_str[1:]]
            elif not tag_matches and normalized_tags_str: # Handle case like "tag1 tag2"
                 parsed_tags = normalized_tags_str.split()

            if tag_matches:
                parsed_tags = [match.strip() for match in tag_matches if match.strip()]
            elif not parsed_tags and tags and not tags.startswith('#'): # If no '#' found but tags provided, treat as space-separated
                 parsed_tags = tags.split()

        # Get official topic tags from XHS API
        topics = []
        hash_tags_names = []
        if parsed_tags:
            tags_to_process = parsed_tags[:max_tags] if max_tags > 0 else parsed_tags
            for idx, tag_name in enumerate(tags_to_process):
                try:
                    topic_official_list = xhs_client.get_suggest_topic(tag_name)
                    if topic_official_list and len(topic_official_list) > 0:
                        topic_official = topic_official_list[0]
                        topic_official['type'] = 'topic' # Ensure type is set
                        topics.append(topic_official)
                        hash_tags_names.append(topic_official['name'])
                    # Apply delay between API calls
                    if idx < len(tags_to_process) - 1 and tag_delay > 0:
                        sleep(tag_delay)
                except Exception as e:
                    # Log or handle individual tag lookup errors if necessary, but don't stop the process
                    print(f"Warning: Failed to get topic for tag '{tag_name}': {e}") # Use print here as it might be silenced
                    if idx < len(tags_to_process) - 1 and tag_delay > 0:
                         sleep(tag_delay * 2) # Longer delay on error

        # Description
        final_desc = desc if desc else final_title
        # Append topic tags to description if found
        if hash_tags_names:
            hash_tags_str = ' '.join(['#' + ht_name + '[话题]#' for ht_name in hash_tags_names])
            final_desc += f"\n\n\n{hash_tags_str}" # Append as per original logic

        # Publish Time Validation
        post_time_str = None
        if publish_time:
            try:
                datetime.strptime(publish_time, "%Y-%m-%d %H:%M:%S")
                post_time_str = publish_time
            except ValueError:
                 # Restore stdout temporarily to show warning if not silent
                if silent and old_stdout: sys.stdout = old_stdout
                print(f"Warning: Invalid publish_time format ('{publish_time}'). Publishing immediately. Use YYYY-MM-DD HH:MM:SS.")
                if silent: sys.stdout = open(os.devnull, 'w')
                post_time_str = None # Fallback to immediate publish

        # --- Upload Video ---
        try:
            note = xhs_client.create_video_note(
                title=final_title[:20], # Title limit
                video_path=str(path),
                desc=final_desc,
                topics=topics,
                cover_path=cover_path, # Use the 'cover_path' parameter directly
                is_private=private, # Use the 'private' parameter
                post_time=post_time_str
            )
            
            # Sleep if not disabled
            if not no_sleep:
                # Restore stdout temporarily for sleep message if not silent
                if silent and old_stdout: sys.stdout = old_stdout
                print(f"Sleeping for {sleep_time} seconds to avoid rate limits...")
                if silent: sys.stdout = open(os.devnull, 'w')
                sleep(sleep_time)

            return {"success": True, "data": note}

        except Exception as e:
            return {"success": False, "error": f"XHS API upload failed: {str(e)}"}

    finally:
        # Restore standard output if it was silenced
        if silent and old_stdout:
            sys.stdout.close()
            sys.stdout = old_stdout
