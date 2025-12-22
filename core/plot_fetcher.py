# core/plot_fetcher.py - 剧情信息获取模块
"""
SmartVideoClipper - 剧情信息获取 v2.0

获取方式（按优先级）：
1. TMDB API - 全球最大电影数据库，免费API，支持中文
2. AI字幕总结 - 使用本地LLM分析字幕内容自动生成剧情
3. 用户手动输入 - 作为最终备选

优点：
- 不依赖爬虫，稳定可靠
- TMDB有详细的分集剧情
- AI总结可以弥补API不足
"""

import httpx
import re
import os
from typing import Dict, List, Optional
import json

# TMDB API配置
# 免费注册获取: https://www.themoviedb.org/settings/api
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")
TMDB_BASE_URL = "https://api.themoviedb.org/3"


class PlotFetcher:
    """
    剧情信息获取器
    
    支持：
    - 电影：获取完整剧情简介
    - 电视剧：获取指定集数的剧情
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or TMDB_API_KEY
        self.client = httpx.Client(timeout=15, follow_redirects=True)
        self.headers = {"Accept": "application/json"}
    
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
                'cast': [
                    {'name': '张译', 'character': '安欣'},
                    {'name': '张颂文', 'character': '高启强'},
                ],
                'keywords': ['黑帮', '警匪', '扫黑除恶'],
                'source': 'tmdb'  # tmdb / ai / manual
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
                print(f"   ✓ TMDB获取成功：{len(result['overview'])}字剧情")
                return result
        else:
            print("   [INFO] TMDB API未配置，跳过")
        
        # 方式2：使用AI分析字幕（在调用方实现）
        # 这里只返回空结果，由调用方决定是否使用AI
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
                print(f"   [TMDB] 搜索失败: {resp.status_code}")
                return None
            
            data = resp.json()
            results = data.get("results", [])
            
            if not results:
                print("   [TMDB] 未找到匹配结果")
                return None
            
            # 找到最匹配的结果
            best_match = None
            for item in results:
                item_title = item.get("title") or item.get("name", "")
                if title in item_title or item_title in title:
                    best_match = item
                    break
            
            if not best_match:
                best_match = results[0]
            
            media_id = best_match.get("id")
            actual_type = best_match.get("media_type", "movie")
            
            print(f"   [TMDB] 找到：{best_match.get('title') or best_match.get('name')} ({actual_type})")
            
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
            
            # 获取分集剧情
            episode_url = f"{TMDB_BASE_URL}/tv/{tv_id}/season/{season}/episode/{episode}"
            resp = self.client.get(episode_url, params=params)
            
            if resp.status_code == 200:
                ep_data = resp.json()
                result['episode_overview'] = ep_data.get("overview", "")
                result['episode_name'] = ep_data.get("name", f"第{episode}集")
                print(f"   [TMDB] 获取第{season}季第{episode}集剧情")
            
            return result
            
        except Exception as e:
            print(f"   [TMDB] 电视剧详情获取失败: {e}")
            return None
    
    def close(self):
        """关闭连接"""
        self.client.close()


def summarize_plot_from_transcript(
    transcript: str,
    segments: List[Dict],
    model: str = None
) -> str:
    """
    使用AI从字幕内容总结剧情
    
    当TMDB获取失败时使用此方法
    """
    try:
        import ollama
        
        # 获取可用模型
        if not model:
            try:
                models_response = ollama.list()
                if hasattr(models_response, 'models'):
                    for m in models_response.models:
                        model = getattr(m, 'name', None)
                        if model:
                            break
            except:
                pass
        
        if not model:
            print("   [AI] 无可用模型，无法生成剧情总结")
            return ""
        
        # 提取关键对话（前1000字）
        key_dialogues = transcript[:3000] if transcript else ""
        
        prompt = f"""请根据以下对白内容，总结这部影视作品的剧情。

对白内容：
{key_dialogues}

请输出：
1. 剧情简介（200字左右）
2. 主要人物及关系
3. 主要冲突点

注意：只输出总结内容，不要有多余解释。
"""

        print(f"   [AI] 使用 {model} 分析字幕生成剧情...")
        
        response = ollama.chat(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.3, 'num_predict': 800}
        )
        
        summary = response['message']['content']
        print(f"   ✓ AI生成剧情总结：{len(summary)}字")
        
        return summary
        
    except Exception as e:
        print(f"   [AI] 剧情总结失败: {e}")
        return ""


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


# 便捷函数
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


# 测试
if __name__ == "__main__":
    # 测试文件名解析
    test_files = [
        "狂飙E01.mp4",
        "狂飙S01E05.mp4",
        "[字幕组]狂飙.EP10.mp4",
        "狂飙 第5集.mp4",
    ]
    
    for f in test_files:
        title = extract_title_from_filename(f)
        season, episode = parse_episode_from_filename(f)
        print(f"{f} → 标题:{title}, S{season}E{episode}")
    
    # 测试API（需要配置TMDB_API_KEY）
    # result = get_plot_info("狂飙E01.mp4", api_key="your_api_key")
    # print(result)

