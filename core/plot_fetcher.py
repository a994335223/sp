# core/plot_fetcher.py - 剧情信息获取模块 v5.5
"""
SmartVideoClipper - 剧情信息获取 v5.5

获取方式（按优先级）：
1. TMDB API - 全球最大电影数据库，免费API，支持中文
2. AI字幕总结 - 使用本地LLM分析字幕内容自动生成剧情
3. 智能提取 - 从对话中提取关键信息（无AI备用）

v5.5 改进：
- 修复Message对象属性访问方式
- 增加num_predict到500确保thinking完成
- 优化thinking内容提取逻辑
"""

import httpx
import re
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
from collections import Counter

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# ============================================================
# 加载TMDB API Key（多种方式）
# ============================================================
def _load_tmdb_api_key() -> str:
    """
    多方式加载TMDB API Key
    优先级: 环境变量 > config.py
    """
    # 1. 尝试环境变量
    key = os.environ.get("TMDB_API_KEY", "")
    if key:
        return key
    
    # 2. 尝试config.py
    try:
        from config import TMDB_API_KEY
        if TMDB_API_KEY:
            return TMDB_API_KEY
    except ImportError:
        pass
    
    return ""


TMDB_API_KEY = _load_tmdb_api_key()
TMDB_BASE_URL = "https://api.themoviedb.org/3"


class PlotFetcher:
    """
    剧情信息获取器 v5.3
    
    支持：
    - 电影：获取完整剧情简介
    - 电视剧：获取指定集数的剧情
    - 自动识别媒体类型
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or TMDB_API_KEY
        self.client = httpx.Client(timeout=15, follow_redirects=True)
        self.headers = {"Accept": "application/json"}
        
        if self.api_key:
            print(f"   [TMDB] API Key已配置 (****{self.api_key[-4:]})")
    
    def fetch(
        self,
        title: str,
        media_type: str = "auto",  # auto, movie, tv
        season: int = 1,
        episode: int = 1
    ) -> Dict:
        """
        获取剧情信息
        
        参数：
            title: 作品名称（如"狂飙"）
            media_type: 类型（auto自动判断, movie电影, tv电视剧）
            season: 第几季（电视剧）
            episode: 第几集（电视剧）
        
        返回：
            {
                'title': '狂飙',
                'type': 'tv',
                'overview': '剧情简介...',
                'episode_overview': '本集剧情...',
                'genres': ['犯罪', '剧情'],
                'cast': [{'name': '张译', 'character': '安欣'}],
                'keywords': ['黑帮', '警匪'],
                'source': 'tmdb'
            }
        """
        print(f"\n[剧情获取] 正在搜索：{title}")
        
        result = {
            'title': title,
            'type': media_type if media_type != 'auto' else 'unknown',
            'overview': '',
            'episode_overview': '',
            'genres': [],
            'cast': [],
            'keywords': [],
            'source': 'none'
        }
        
        # 方式1：尝试TMDB API
        if self.api_key:
            tmdb_result = self._fetch_from_tmdb(title, media_type, season, episode)
            if tmdb_result and tmdb_result.get('overview'):
                result.update(tmdb_result)
                result['source'] = 'tmdb'
                print(f"   [OK] TMDB获取成功：{len(result['overview'])}字剧情")
                if result.get('episode_overview'):
                    print(f"   [OK] 第{episode}集剧情：{len(result['episode_overview'])}字")
                return result
        else:
            print("   [INFO] TMDB API未配置")
            print("   [TIP] 请在 config.py 中配置 TMDB_API_KEY")
        
        # 方式2：标记需要AI分析
        print("   [INFO] 将使用AI分析字幕生成剧情")
        result['source'] = 'ai_pending'
        
        return result
    
    def _fetch_from_tmdb(
        self,
        title: str,
        media_type: str,
        season: int,
        episode: int
    ) -> Optional[Dict]:
        """从TMDB获取信息"""
        try:
            # 搜索
            search_url = f"{TMDB_BASE_URL}/search/multi"
            params = {
                "api_key": self.api_key,
                "query": title,
                "language": "zh-CN",
                "include_adult": False
            }
            
            resp = self.client.get(search_url, params=params)
            if resp.status_code != 200:
                print(f"   [TMDB] 搜索失败: HTTP {resp.status_code}")
                return None
            
            data = resp.json()
            results = data.get("results", [])
            
            if not results:
                print("   [TMDB] 未找到匹配结果")
                return None
            
            # 找到最匹配的结果（优先完全匹配）
            best_match = None
            for item in results:
                item_title = item.get("title") or item.get("name", "")
                # 完全匹配
                if item_title == title:
                    best_match = item
                    break
                # 包含匹配
                if title in item_title or item_title in title:
                    if not best_match:
                        best_match = item
            
            if not best_match:
                best_match = results[0]
            
            media_id = best_match.get("id")
            actual_type = best_match.get("media_type", "movie")
            found_title = best_match.get('title') or best_match.get('name')
            
            print(f"   [TMDB] 找到：{found_title} ({actual_type}, ID:{media_id})")
            
            # 获取详情
            if actual_type == "tv":
                return self._fetch_tv_details(media_id, season, episode)
            else:
                return self._fetch_movie_details(media_id)
            
        except Exception as e:
            print(f"   [TMDB] 请求错误: {e}")
            return None
    
    def _fetch_movie_details(self, movie_id: int) -> Optional[Dict]:
        """获取电影详情"""
        try:
            url = f"{TMDB_BASE_URL}/movie/{movie_id}"
            params = {
                "api_key": self.api_key,
                "language": "zh-CN",
                "append_to_response": "credits,keywords"
            }
            
            resp = self.client.get(url, params=params)
            if resp.status_code != 200:
                return None
            
            data = resp.json()
            
            # 解析演员
            cast = []
            for actor in data.get("credits", {}).get("cast", [])[:10]:
                cast.append({
                    "name": actor.get("name", ""),
                    "character": actor.get("character", "")
                })
            
            # 解析关键词
            keywords = [
                kw.get("name", "") 
                for kw in data.get("keywords", {}).get("keywords", [])[:10]
            ]
            
            return {
                'title': data.get("title", ""),
                'type': 'movie',
                'overview': data.get("overview", ""),
                'episode_overview': '',
                'genres': [g.get("name", "") for g in data.get("genres", [])],
                'cast': cast,
                'keywords': keywords,
            }
            
        except Exception as e:
            print(f"   [TMDB] 电影详情获取失败: {e}")
            return None
    
    def _fetch_tv_details(
        self, 
        tv_id: int, 
        season: int, 
        episode: int
    ) -> Optional[Dict]:
        """获取电视剧详情（包括分集剧情）"""
        try:
            # 获取剧集总体信息
            url = f"{TMDB_BASE_URL}/tv/{tv_id}"
            params = {
                "api_key": self.api_key,
                "language": "zh-CN",
                "append_to_response": "credits,keywords"
            }
            
            resp = self.client.get(url, params=params)
            if resp.status_code != 200:
                return None
            
            data = resp.json()
            
            # 解析演员
            cast = []
            for actor in data.get("credits", {}).get("cast", [])[:10]:
                cast.append({
                    "name": actor.get("name", ""),
                    "character": actor.get("character", "")
                })
            
            # 解析关键词
            keywords = [
                kw.get("name", "") 
                for kw in data.get("keywords", {}).get("results", [])[:10]
            ]
            
            result = {
                'title': data.get("name", ""),
                'type': 'tv',
                'overview': data.get("overview", ""),
                'episode_overview': '',
                'genres': [g.get("name", "") for g in data.get("genres", [])],
                'cast': cast,
                'keywords': keywords,
            }
            
            # 获取分集剧情（关键！）
            episode_url = f"{TMDB_BASE_URL}/tv/{tv_id}/season/{season}/episode/{episode}"
            params_ep = {
                "api_key": self.api_key,
                "language": "zh-CN"
            }
            resp = self.client.get(episode_url, params=params_ep)
            
            if resp.status_code == 200:
                ep_data = resp.json()
                result['episode_overview'] = ep_data.get("overview", "")
                result['episode_name'] = ep_data.get("name", f"第{episode}集")
                print(f"   [TMDB] 获取第{season}季第{episode}集剧情成功")
            else:
                print(f"   [TMDB] 第{season}季第{episode}集剧情获取失败: HTTP {resp.status_code}")
            
            return result
            
        except Exception as e:
            print(f"   [TMDB] 电视剧详情获取失败: {e}")
            return None
    
    def close(self):
        """关闭连接"""
        self.client.close()


# ============================================================
# AI字幕总结 v5.5
# ============================================================
def summarize_plot_from_transcript(
    transcript: str,
    segments: List[Dict],
    model: str = None
) -> str:
    """
    使用AI从字幕内容总结剧情 v5.5
    
    v5.5修复：
    1. 正确访问Message对象属性（msg.content而非msg.get('content')）
    2. num_predict=500确保thinking完成后输出content
    3. 从thinking中智能提取结论部分
    """
    if not transcript or len(transcript) < 50:
        return _extract_key_info_from_transcript(transcript or "")
    
    try:
        import ollama
        
        # 更可靠的模型检测
        if not model:
            model = _detect_ollama_model()
        
        if not model:
            print("   [AI] 无可用Ollama模型")
            return _extract_key_info_from_transcript(transcript)
        
        # 提取关键对话
        key_dialogues = transcript[:2000]
        
        # 简化prompt
        prompt = f"""用100字总结以下对白的主要剧情：

{key_dialogues}

剧情总结："""
        
        print(f"   [AI] 使用 {model} 分析字幕...")
        
        response = ollama.chat(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.3, 'num_predict': 500}  # v5.5: 确保thinking完成
        )
        
        # v5.5修复：正确访问Message对象属性
        msg = response.get('message', {})
        summary = ""
        
        # 优先使用content
        if hasattr(msg, 'content') and msg.content:
            summary = msg.content.strip()
        # content为空时尝试thinking
        elif hasattr(msg, 'thinking') and msg.thinking:
            thinking = msg.thinking.strip()
            # 从thinking中提取最后的结论部分
            lines = thinking.split('\n')
            for line in reversed(lines):
                line = line.strip()
                if line and 30 < len(line) < 200:
                    # 排除思考过程语句
                    if not any(x in line for x in ['需要', '首先', '接下来', '可以', '应该']):
                        summary = line
                        break
            if not summary:
                summary = thinking[:200]
        
        # 清理可能的前缀
        summary = summary.replace('剧情总结：', '').replace('剧情总结:', '')
        summary = summary.strip()
        
        if summary and len(summary) > 20:
            print(f"   [OK] AI生成剧情总结：{len(summary)}字")
            return summary
        else:
            print("   [AI] 总结结果太短，使用备用方案")
            return _extract_key_info_from_transcript(transcript)
        
    except Exception as e:
        print(f"   [AI] 剧情总结失败: {e}")
        return _extract_key_info_from_transcript(transcript)


def _detect_ollama_model() -> Optional[str]:
    """检测可用的Ollama模型"""
    try:
        import ollama
        
        # 方式1：通过list API - 保留完整模型名
        try:
            response = ollama.list()
            models = response.get('models', [])
            
            # 按优先级选择
            priority = ['qwen3', 'qwen2.5', 'qwen', 'llama3', 'gemma', 'mistral']
            for p in priority:
                for m in models:
                    name = m.get('name', '') or m.get('model', '')
                    if name and p in name.lower():
                        return name  # 返回完整名称如 qwen3:8b
            
            # 返回第一个可用模型
            if models:
                name = models[0].get('name', '') or models[0].get('model', '')
                if name:
                    return name
        except:
            pass
        
        return None
        
    except ImportError:
        return None
    except Exception:
        return None


def _extract_key_info_from_transcript(transcript: str) -> str:
    """
    从对白中智能提取关键信息（无AI备用方案）
    
    这是最后的备用方案，确保始终有内容返回
    """
    if not transcript or len(transcript) < 20:
        return "一场扣人心弦的故事正在展开"
    
    # 提取高频人名/称呼
    name_patterns = [
        r'([\u4e00-\u9fa5]{2,3}(?:哥|姐|叔|伯|爷|奶))',  # 亲属称呼
        r'([\u4e00-\u9fa5]{2,3}(?:总|长|主任|局长|书记|队长|警官))',  # 职务称呼
        r'(老[\u4e00-\u9fa5]|小[\u4e00-\u9fa5])',  # 老X/小X
    ]
    
    names = []
    for pattern in name_patterns:
        names.extend(re.findall(pattern, transcript))
    
    name_counts = Counter(names)
    top_names = [n for n, c in name_counts.most_common(3) if c >= 2]
    
    # 提取关键动作/事件
    action_keywords = {
        '调查': '调查',
        '案件': '案件',
        '杀人': '命案',
        '警察': '警方行动',
        '犯罪': '犯罪',
        '交易': '交易',
        '证据': '证据',
        '抓捕': '抓捕',
        '审问': '审讯',
        '黑帮': '黑帮',
        '扫黑': '扫黑除恶',
        '贩毒': '毒品案',
        '走私': '走私',
        '腐败': '腐败',
        '开会': '会议',
        '汇报': '工作',
    }
    
    found_actions = []
    for keyword, display in action_keywords.items():
        if keyword in transcript:
            found_actions.append(display)
    
    # 构建描述
    if top_names and found_actions:
        names_str = '、'.join(top_names[:2])
        actions_str = '、'.join(found_actions[:2])
        return f"故事围绕{names_str}等人展开，涉及{actions_str}等事件"
    elif top_names:
        names_str = '、'.join(top_names[:2])
        return f"故事围绕{names_str}等人展开，情节跌宕起伏"
    elif found_actions:
        actions_str = '、'.join(found_actions[:2])
        return f"一个涉及{actions_str}的故事正在展开"
    else:
        return "一场扣人心弦的故事正在展开"


# ============================================================
# 文件名解析工具
# ============================================================
def parse_episode_from_filename(filename: str) -> tuple:
    """
    从文件名解析季和集数
    
    支持格式：
    - 狂飙E01.mp4 → (1, 1)
    - 狂飙S01E05.mp4 → (1, 5)
    - 狂飙 第1集.mp4 → (1, 1)
    - 狂飙.EP05.mp4 → (1, 5)
    """
    filename = os.path.basename(filename)
    
    # 格式1: S01E05
    match = re.search(r'S(\d+)E(\d+)', filename, re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))
    
    # 格式2: E01 或 EP01
    match = re.search(r'E[Pp]?(\d+)', filename, re.IGNORECASE)
    if match:
        return 1, int(match.group(1))
    
    # 格式3: 第X集
    match = re.search(r'第(\d+)集', filename)
    if match:
        return 1, int(match.group(1))
    
    # 默认第1季第1集
    return 1, 1


def extract_title_from_filename(filename: str) -> str:
    """
    从文件名提取作品名称
    
    支持格式：
    - 狂飙E01.mp4 → 狂飙
    - 狂飙S01E05.mp4 → 狂飙
    - [字幕组]狂飙.EP01.mp4 → 狂飙
    """
    filename = os.path.basename(filename)
    
    # 去除扩展名
    name = os.path.splitext(filename)[0]
    
    # 去除常见前缀（字幕组标记等）
    name = re.sub(r'^\[.*?\]', '', name)
    name = re.sub(r'^\【.*?\】', '', name)
    
    # 去除集数标记
    name = re.sub(r'[._\s-]*S\d+E\d+.*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[._\s-]*E[Pp]?\d+.*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[._\s-]*第\d+集.*', '', name)
    
    # 清理
    name = name.strip('._- ')
    
    return name if name else "未知作品"


# ============================================================
# 便捷函数
# ============================================================
def get_plot_info(
    video_path: str,
    title: str = None,
    api_key: str = None
) -> Dict:
    """
    获取剧情信息的便捷函数
    
    自动从文件名解析标题和集数
    """
    if not title:
        title = extract_title_from_filename(video_path)
    
    season, episode = parse_episode_from_filename(video_path)
    
    print(f"\n[剧情获取] 作品: {title}, 第{season}季第{episode}集")
    
    fetcher = PlotFetcher(api_key)
    result = fetcher.fetch(
        title=title,
        media_type="auto",
        season=season,
        episode=episode
    )
    fetcher.close()
    
    return result


# ============================================================
# 测试
# ============================================================
if __name__ == "__main__":
    # 测试文件名解析
    print("=== 文件名解析测试 ===")
    test_files = [
        "狂飙E01.mp4",
        "狂飙S01E05.mp4",
        "[字幕组]狂飙.EP10.mp4",
        "狂飙 第5集.mp4",
    ]
    
    for f in test_files:
        title = extract_title_from_filename(f)
        season, episode = parse_episode_from_filename(f)
        print(f"  {f} → 标题:{title}, S{season}E{episode}")
    
    # 测试TMDB API
    print("\n=== TMDB API测试 ===")
    if TMDB_API_KEY:
        result = get_plot_info("狂飙E01.mp4")
        print(f"  结果: {result.get('source')}")
        if result.get('overview'):
            print(f"  剧情: {result['overview'][:100]}...")
        if result.get('episode_overview'):
            print(f"  本集: {result['episode_overview'][:100]}...")
    else:
        print("  TMDB API未配置，跳过测试")
