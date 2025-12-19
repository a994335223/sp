# core/movie_info.py - 联网获取电影信息（国内版-豆瓣）
"""
SmartVideoClipper - 电影信息获取模块

功能: 从豆瓣获取电影信息（评分、演员、剧情简介）
用途: 增强AI文案生成的背景知识

依赖: httpx, beautifulsoup4
"""

import httpx
from bs4 import BeautifulSoup
import re
import time
import random


class MovieInfoFetcher:
    """
    🇨🇳 国内版：使用豆瓣获取电影信息
    ✅ 无需VPN，国内直接访问
    ✅ 无需API Key
    ✅ 数据更贴合国内用户习惯
    ⚠️ 包含完善的反爬虫处理
    """
    
    def __init__(self):
        # 🔧 更完善的请求头，模拟真实浏览器
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": "https://www.douban.com/"
        }
        self.max_retries = 3
    
    def search_movie(self, movie_name: str) -> dict:
        """
        搜索电影信息（带重试机制）
        
        参数:
            movie_name: 电影名称
        
        返回:
            {
                'title': '电影名',
                'rating': '8.5/10 (豆瓣)',
                'director': '导演',
                'cast': ['演员1', '演员2', ...],
                'genres': ['动作', '科幻'],
                'overview': '剧情简介',
                'source': '豆瓣'
            }
        """
        for attempt in range(self.max_retries):
            try:
                # 🔧 添加随机延迟，避免被封
                if attempt > 0:
                    delay = random.uniform(2, 5)
                    print(f"   第{attempt+1}次重试，等待{delay:.1f}秒...")
                    time.sleep(delay)
                
                return self._search_douban(movie_name)
            except Exception as e:
                print(f"⚠️ 豆瓣搜索失败 (尝试 {attempt+1}/{self.max_retries}): {e}")
                if attempt == self.max_retries - 1:
                    return {"title": movie_name, "overview": "", "error": str(e)}
        
        return {"title": movie_name, "overview": ""}
    
    def _search_douban(self, movie_name: str) -> dict:
        """使用豆瓣搜索（国内可直接访问）"""
        # 🔧 添加随机延迟
        time.sleep(random.uniform(0.5, 1.5))
        
        with httpx.Client(headers=self.headers, timeout=15, follow_redirects=True) as client:
            # 1. 搜索电影
            search_url = "https://www.douban.com/search"
            params = {"q": movie_name, "cat": "1002"}  # cat=1002是电影
            resp = client.get(search_url, params=params)
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # 找到第一个电影结果
            result = soup.select_one(".result-list .result h3 a")
            if not result:
                return {"title": movie_name, "overview": "未找到"}
            
            # 提取豆瓣电影ID
            onclick = result.get("onclick", "")
            sid_match = re.search(r"sid:\s*(\d+)", onclick)
            if sid_match:
                movie_id = sid_match.group(1)
                movie_url = f"https://movie.douban.com/subject/{movie_id}/"
            else:
                movie_url = result.get("href")
            
            # 2. 获取电影详情页
            time.sleep(random.uniform(0.5, 1))  # 再次延迟
            resp = client.get(movie_url)
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # 解析标题
            title_elem = soup.select_one("h1 span")
            title = title_elem.text.strip() if title_elem else movie_name
            
            # 解析评分
            rating_elem = soup.select_one(".rating_num")
            rating = rating_elem.text.strip() if rating_elem else "N/A"
            
            # 解析详细信息
            info_elem = soup.select_one("#info")
            info_text = info_elem.text if info_elem else ""
            
            # 导演
            director_match = re.search(r"导演:\s*([^\n]+)", info_text)
            director = director_match.group(1).strip().split("/")[0] if director_match else "N/A"
            
            # 主演
            cast_match = re.search(r"主演:\s*([^\n]+)", info_text)
            cast = []
            if cast_match:
                cast = [c.strip() for c in cast_match.group(1).split("/")[:5]]
            
            # 类型
            genre_match = re.search(r"类型:\s*([^\n]+)", info_text)
            genres = genre_match.group(1).strip().split() if genre_match else []
            
            # 简介
            summary_elem = soup.select_one('[property="v:summary"]')
            summary = summary_elem.text.strip() if summary_elem else ""
            
            return {
                "title": title,
                "rating": f"{rating}/10 (豆瓣)",
                "director": director,
                "cast": cast,
                "genres": genres,
                "overview": summary[:500],
                "source": "豆瓣"
            }


# 使用示例
if __name__ == "__main__":
    fetcher = MovieInfoFetcher()
    
    # 测试搜索
    test_movies = ["复仇者联盟", "流浪地球", "哪吒之魔童降世"]
    
    for movie in test_movies:
        print(f"\n搜索: {movie}")
        print("-" * 40)
        info = fetcher.search_movie(movie)
        
        if "error" not in info:
            print(f"🎬 电影: {info['title']}")
            print(f"⭐ 评分: {info['rating']}")
            print(f"🎬 导演: {info['director']}")
            print(f"👥 主演: {', '.join(info['cast'][:3])}")
            print(f"🏷️ 类型: {', '.join(info['genres'])}")
            print(f"📖 简介: {info['overview'][:100]}...")
        else:
            print(f"❌ 搜索失败: {info.get('error')}")

