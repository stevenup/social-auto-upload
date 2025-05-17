## `upload_video_to_xhs` 函数调用文档

### 功能描述

该函数封装了向小红书平台上传视频笔记的核心逻辑。它接收视频文件路径和各种可选参数（如标题、标签、描述、发布时间等），处理 Cookie 获取、话题标签查找、视频上传等步骤，并返回一个包含操作结果（成功或失败）以及相关数据（如笔记 ID）的字典。

该函数旨在提供一个简洁、无日志干扰的接口，方便从其他 Python 系统或脚本中以编程方式调用。

### 如何导入

要从另一个项目或脚本中使用此函数，您需要确保 Python 解释器能够找到 `tools/xhs_api.py` 文件。

1.  **添加项目路径到 `sys.path`** （推荐用于开发或简单集成）：
    在您的调用脚本顶部添加：
    ```python
    import sys
    import os
    # 将 'social-auto-upload' 项目的根目录添加到 Python 搜索路径
    # 请将 '/path/to/social-auto-upload' 替换为实际的项目根目录路径
    project_root = '/path/to/social-auto-upload' 
    if project_root not in sys.path:
        sys.path.append(project_root)

    # 现在可以导入模块了
    from tools.xhs_api import upload_video_to_xhs 
    ```

2.  **将 `social-auto-upload` 项目安装为包** （推荐用于更规范的集成）：
    如果 `social-auto-upload` 项目包含 `setup.py`，您可以在您的虚拟环境中安装它：
    ```bash
    cd /path/to/social-auto-upload
    pip install -e . 
    ```
    然后直接导入：
    ```python
    from tools.xhs_api import upload_video_to_xhs
    ```

### 函数签名

```python
def upload_video_to_xhs(
    video_path: str,
    title: str = None,
    tags: str = None,
    desc: str = None,
    cover: str = None,
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
) -> dict:
```

### 参数详解

**必需参数:**

*   `video_path` (str):
    *   **描述**: 要上传的视频文件的完整路径。
    *   **示例**: `"/Users/steven/videos/my_trip.mp4"`

**可选参数:**

*   `title` (str, optional):
    *   **描述**: 视频笔记的标题。如果未提供，将使用视频文件名（不含扩展名）作为标题。小红书标题有长度限制（当前实现为最多 20 个字符）。
    *   **默认值**: `None` (使用文件名)
    *   **示例**: `"我的旅行vlog"`
*   `tags` (str, optional):
    *   **描述**: 与视频相关的标签字符串，标签之间用**空格**分隔，每个标签前需要加 `#` 号。函数会解析此字符串，并尝试获取对应的小红书官方话题。
    *   **默认值**: `None`
    *   **格式**: `"#标签1 #标签2 #更多标签"`
    *   **示例**: `"#旅行 #美食 #vlog"`
*   `desc` (str, optional):
    *   **描述**: 视频笔记的描述内容。如果未提供，将使用 `final_title`（处理后的标题）。如果成功获取了话题标签，会自动将话题标签追加到描述末尾。
    *   **默认值**: `None` (使用标题)
    *   **示例**: `"这次旅行真的太棒了！记录下美好瞬间。"`
*   `cover` (str, optional):
    *   **描述**: 自定义视频封面的图片文件路径。如果未提供，小红书可能会自动选择或提供默认封面。
    *   **默认值**: `None`
    *   **示例**: `"/Users/steven/covers/trip_cover.jpg"`
*   `cookie_file` (str, optional):
    *   **描述**: 包含小红书登录 Cookies 的文本文件的路径。如果同时提供了 `cookies_str`，则此参数会被忽略。如果两者都未提供，则会尝试从 `config_file` 中读取。
    *   **默认值**: `None`
    *   **示例**: `"/path/to/my_xhs_cookies.txt"`
*   `account` (str, optional):
    *   **描述**: 在 `config_file` 中要使用的账号名称（对应于 `accounts.ini` 文件中的节名，如 `[account1]`）。仅当需要从配置文件读取 Cookies 时有效。
    *   **默认值**: `"account1"`
    *   **示例**: `"my_main_account"`
*   `config_file` (str, optional):
    *   **描述**: 指定 `accounts.ini` 配置文件的路径。如果未提供，将使用项目默认路径 `uploader/xhs_uploader/accounts.ini`。仅当需要从配置文件读取 Cookies 且未提供 `cookie_file` 或 `cookies_str` 时有效。
    *   **默认值**: `None` (使用默认路径)
    *   **示例**: `"/etc/myapp/xhs_accounts.ini"`
*   `publish_time` (str, optional):
    *   **描述**: 设置定时发布的时间。如果提供，必须是 `"YYYY-MM-DD HH:MM:SS"` 格式的字符串。如果格式无效或未提供，则立即发布。
    *   **默认值**: `None` (立即发布)
    *   **格式**: `"YYYY-MM-DD HH:MM:SS"`
    *   **示例**: `"2025-01-15 18:30:00"`
*   `private` (bool, optional):
    *   **描述**: 是否将笔记设为私密（仅自己可见）。设置为 `True` 表示私密发布。
    *   **默认值**: `False` (公开)
    *   **示例**: `True`
*   `no_sleep` (bool, optional):
    *   **描述**: 是否在上传成功后禁用默认的延时等待。设置为 `True` 将跳过等待。
    *   **默认值**: `False` (会等待 `sleep_time` 秒)
    *   **示例**: `True`
*   `sleep_time` (int, optional):
    *   **描述**: 上传成功后的等待时间（秒），用于避免过于频繁的操作触发风控。仅当 `no_sleep` 为 `False` 时有效。
    *   **默认值**: `30`
    *   **示例**: `60`
*   `tag_delay` (float, optional):
    *   **描述**: 在查找每个标签对应的小红书话题时，API 调用之间的延迟时间（秒）。用于避免请求过于频繁。
    *   **默认值**: `1.0`
    *   **示例**: `1.5`
*   `max_tags` (int, optional):
    *   **描述**: 最多处理 `tags` 字符串中解析出的前 N 个标签，以获取对应的小红书话题。设置为 0 或负数表示不限制。
    *   **默认值**: `20`
    *   **示例**: `5`
*   `cookies_str` (str, optional):
    *   **描述**: 直接以字符串形式传入小红书 Cookies。**优先级最高**，如果提供此参数，将忽略 `cookie_file` 和 `config_file`。
    *   **默认值**: `None`
    *   **示例**: `"sessionid=xxxx;userid=yyyy;..."`
*   `silent` (bool, optional):
    *   **描述**: 是否禁止函数内部的 `print` 输出（例如 "Cookie验证成功"、"等待 N 秒..." 等）。设置为 `True` 将抑制所有标准输出。**注意**：错误信息（如 Cookie 读取失败）会通过返回值字典的 `error` 字段返回，而不是打印。
    *   **默认值**: `True` (无日志输出)
    *   **示例**: `False` (允许打印内部信息，主要用于调试)

### Cookie 处理优先级

函数获取 Cookies 的顺序如下：

1.  **`cookies_str`**: 如果提供了非空字符串，直接使用。
2.  **`cookie_file`**: 如果 `cookies_str` 未提供，且 `cookie_file` 提供了有效路径，则从该文件读取。
3.  **`config_file` 和 `account`**: 如果以上两者都未提供，则尝试从指定的（或默认的）`config_file` 中读取指定 `account` 的 Cookies。

### 返回值

函数总是返回一个 Python 字典，包含以下两种可能的结构：

**成功:**

```json
{
  "success": True,
  "data": {
    "id": "笔记的唯一ID字符串", // 例如 "681342360000000023010c35"
    "score": 分数或其他数值 // 例如 10
    // ... 可能包含小红书 API 返回的其他字段
  }
}
```

*   `success`: 固定为 `True`。
*   `data`: 包含小红书 API 成功创建笔记后返回的原始数据字典。关键字段是 `id`（笔记 ID）。

**失败:**

```json
{
  "success": False,
  "error": "描述错误的字符串信息" 
}
```

*   `success`: 固定为 `False`。
*   `error`: 描述失败原因的字符串。例如 "视频文件未找到"、"Cookie验证失败"、"上传失败: [具体API错误]" 等。

### 调用示例

```python
import sys
import os

# --- 设置导入路径 (根据实际情况修改) ---
project_root = '/path/to/social-auto-upload' 
if project_root not in sys.path:
    sys.path.append(project_root)

from tools.xhs_api import upload_video_to_xhs

# --- 准备参数 ---
video_file = "/data/videos/my_latest_vlog.mp4"
note_title = "周末探店记"
note_tags = "#周末去哪儿 #咖啡探店 #日常vlog"
note_description = "发现一家宝藏咖啡店，环境和咖啡都很赞！"
schedule_time = "2025-02-10 12:00:00" # 定时发布
# 可以选择直接传入 cookies 字符串
my_cookies = "a1=xxxx; web_session=yyyy; ..." 

# --- 调用函数 ---
# 示例1：使用 cookies 字符串，并定时发布
result = upload_video_to_xhs(
    video_path=video_file,
    title=note_title,
    tags=note_tags,
    desc=note_description,
    publish_time=schedule_time,
    cookies_str=my_cookies, # 直接传入 cookies
    silent=True # 保持安静，不打印日志
)

# 示例2：使用配置文件读取 cookies，立即私密发布
# result = upload_video_to_xhs(
#     video_path="/data/videos/private_test.mp4",
#     title="私密测试视频",
#     account="my_test_account", # 假设配置文件中有这个账号
#     config_file="/etc/myapp/xhs_accounts.ini", # 指定配置文件路径
#     private=True, # 设置为私密
#     silent=False # 允许打印调试信息
# )

# --- 处理结果 ---
if result["success"]:
    note_info = result["data"]
    note_id = note_info.get("id")
    score = note_info.get("score")
    print(f"视频上传成功！")
    print(f"  笔记 ID: {note_id}")
    print(f"  得分: {score}")
    # 在这里可以将 note_id 保存到数据库或其他系统
    # save_note_id_to_db(note_id)
else:
    error_msg = result["error"]
    print(f"视频上传失败: {error_msg}")
    # 可以记录错误日志或进行其他错误处理
    # log_upload_error(video_file, error_msg)

```

### 注意事项

*   确保调用环境中已安装 `social-auto-upload` 项目所需的所有依赖项（如 `requests`, `xhs`, `configparser` 等，具体见 `requirements.txt`）。
*   Cookie 的有效性至关重要，如果 Cookie 过期或无效，会导致验证失败或上传失败。
*   小红书的 API 可能会变化，如果遇到问题，可能需要检查 `xhs` 库或此函数的实现是否与最新的 API 兼容。
*   频繁调用此接口可能需要适当的延迟或代理来避免触发平台的风控策略。函数内置了 `sleep_time` 和 `tag_delay`，但根据使用频率可能需要调整或在外部调用层添加更多控制。
