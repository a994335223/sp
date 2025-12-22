# core/story_understanding.py - 剧情理解模块
"""
SmartVideoClipper v3.0 - 剧情深度理解模块

核心理念：先理解故事，再做解说

工作流程：
1. 联网搜索：获取剧情简介、人物关系、经典场景
2. 字幕分析：提取对话，识别关键剧情点
3. 剧情结构化：起承转合，冲突点，高潮点
4. 生成剧情地图：每个时间段发生了什么

这是解说质量的基础！
"""

import httpx
from bs4 import BeautifulSoup
import re
import time
import random
from typing import Dict, List, Tuple, Optional
import json


class StoryUnderstanding:
    """
    剧情理解引擎
    
    输入：电影名称 + 字幕文件
    输出：结构化的剧情理解
    """
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
    
    def understand(
        self,
        movie_name: str,
        transcript_segments: List[Dict],
        full_transcript: str,
        external_plot_info: Dict = None
    ) -> Dict:
        """
        全面理解一部电影/剧集
        
        参数：
            movie_name: 作品名称
            transcript_segments: 字幕片段
            full_transcript: 完整字幕文本
            external_plot_info: 外部获取的剧情信息（来自TMDB/AI总结）
        
        返回：
        {
            'title': '狂飙',
            'type': 'tv_series',  # movie / tv_series
            'genre': ['犯罪', '剧情'],
            'plot_summary': '...',  # 300字剧情简介
            'characters': [
                {'name': '高启强', 'role': '主角', 'description': '从鱼贩到黑帮老大'},
                ...
            ],
            'key_scenes': [
                {'time': '10:00', 'description': '高启强第一次见安欣', 'importance': 'high'},
                ...
            ],
            'story_structure': {
                'opening': {'time_range': [0, 180], 'description': '人物出场'},
                'development': {'time_range': [180, 1200], 'description': '冲突升级'},
                'climax': {'time_range': [1200, 2000], 'description': '对决'},
                'ending': {'time_range': [2000, 2400], 'description': '结局'},
            },
            'classic_dialogues': [
                {'time': 600, 'speaker': '高启强', 'text': '...', 'context': '...'},
            ],
            'emotional_beats': [
                {'time': 800, 'emotion': '紧张', 'intensity': 0.8},
            ]
        }
        """
        print("\n" + "="*60)
        print("🧠 剧情理解引擎 v3.0")
        print("="*60)
        
        result = {
            'title': movie_name,
            'type': 'unknown',
            'genre': [],
            'plot_summary': '',
            'characters': [],
            'key_scenes': [],
            'story_structure': {},
            'classic_dialogues': [],
            'emotional_beats': []
        }
        
        # 1. 使用外部传入的剧情信息（优先）或联网搜索
        print("\n[1/4] 获取剧情信息...")
        
        if external_plot_info and external_plot_info.get('overview'):
            # 使用外部传入的信息
            result['plot_summary'] = external_plot_info.get('overview', '')
            # 合并分集剧情
            if external_plot_info.get('episode_overview'):
                result['plot_summary'] += '\n\n本集剧情：' + external_plot_info['episode_overview']
            
            # 解析演员信息
            for actor in external_plot_info.get('cast', []):
                result['characters'].append({
                    'name': actor.get('character') or actor.get('name', ''),
                    'role': '主演',
                    'description': f"由{actor.get('name', '')}饰演"
                })
            
            result['genre'] = external_plot_info.get('genres', [])
            result['type'] = external_plot_info.get('type', 'movie')
            
            print(f"   ✓ 获取到 {len(result['plot_summary'])} 字剧情简介")
            print(f"   ✓ 识别到 {len(result['characters'])} 个主要人物")
            print(f"   ✓ 数据来源: {external_plot_info.get('source', 'unknown')}")
        else:
            # 回退到原有的联网搜索
            web_info = self._search_plot_info(movie_name)
            if web_info:
                result['plot_summary'] = web_info.get('plot', '')
                result['characters'] = web_info.get('characters', [])
                result['genre'] = web_info.get('genre', [])
                result['type'] = web_info.get('type', 'movie')
                print(f"   ✓ 获取到 {len(result['plot_summary'])} 字剧情简介")
                print(f"   ✓ 识别到 {len(result['characters'])} 个主要人物")
            else:
                print("   [INFO] 未获取到外部剧情信息")
        
        # 2. 分析字幕内容
        print("\n[2/4] 分析字幕内容...")
        dialogue_analysis = self._analyze_dialogues(transcript_segments, full_transcript)
        result['classic_dialogues'] = dialogue_analysis.get('classic_dialogues', [])
        result['emotional_beats'] = dialogue_analysis.get('emotional_beats', [])
        print(f"   ✓ 识别到 {len(result['classic_dialogues'])} 句经典台词")
        print(f"   ✓ 识别到 {len(result['emotional_beats'])} 个情感节点")
        
        # 3. 推断剧情结构
        print("\n[3/4] 推断剧情结构...")
        result['story_structure'] = self._infer_story_structure(
            transcript_segments, 
            dialogue_analysis,
            result['plot_summary']
        )
        print(f"   ✓ 剧情结构已生成")
        
        # 4. 识别关键场景
        print("\n[4/4] 识别关键场景...")
        result['key_scenes'] = self._identify_key_scenes(
            transcript_segments,
            dialogue_analysis,
            result['story_structure'],
            result['plot_summary']
        )
        print(f"   ✓ 识别到 {len(result['key_scenes'])} 个关键场景")
        
        print("\n" + "="*60)
        print("✅ 剧情理解完成！")
        print("="*60)
        
        return result
    
    def _search_plot_info(self, movie_name: str) -> Optional[Dict]:
        """从多个来源搜索剧情信息"""
        
        # 尝试从豆瓣获取
        douban_info = self._search_douban(movie_name)
        if douban_info:
            return douban_info
        
        # 尝试从百度百科获取
        baike_info = self._search_baike(movie_name)
        if baike_info:
            return baike_info
        
        return None
    
    def _search_douban(self, movie_name: str) -> Optional[Dict]:
        """从豆瓣搜索"""
        try:
            time.sleep(random.uniform(0.5, 1.5))
            
            client = httpx.Client(headers=self.headers, timeout=15, follow_redirects=True)
            
            # 搜索
            search_url = "https://www.douban.com/search"
            params = {"q": movie_name, "cat": "1002"}
            resp = client.get(search_url, params=params)
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # 找到第一个结果
            result = soup.select_one(".result-list .result h3 a")
            if not result:
                return None
            
            # 提取ID
            onclick = result.get("onclick", "")
            sid_match = re.search(r"sid:\s*(\d+)", onclick)
            if sid_match:
                movie_id = sid_match.group(1)
                movie_url = f"https://movie.douban.com/subject/{movie_id}/"
            else:
                movie_url = result.get("href")
            
            # 获取详情
            time.sleep(random.uniform(0.5, 1))
            resp = client.get(movie_url)
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # 解析剧情简介
            summary_elem = soup.select_one('[property="v:summary"]')
            plot = summary_elem.text.strip() if summary_elem else ""
            
            # 解析类型
            genre_elems = soup.select('[property="v:genre"]')
            genres = [g.text.strip() for g in genre_elems]
            
            # 解析演员（作为人物参考）
            cast_elems = soup.select('.celebrity a')
            characters = []
            for elem in cast_elems[:6]:
                name = elem.text.strip()
                if name:
                    characters.append({
                        'name': name,
                        'role': '主演',
                        'description': ''
                    })
            
            # 判断类型
            info_text = soup.select_one("#info")
            info_str = info_text.text if info_text else ""
            is_tv = "集数" in info_str or "首播" in info_str
            
            client.close()
            
            return {
                'plot': plot,
                'genre': genres,
                'characters': characters,
                'type': 'tv_series' if is_tv else 'movie'
            }
            
        except Exception as e:
            print(f"   [WARNING] 豆瓣搜索失败: {e}")
            return None
    
    def _search_baike(self, movie_name: str) -> Optional[Dict]:
        """从百度百科搜索"""
        try:
            time.sleep(random.uniform(0.5, 1))
            
            url = f"https://baike.baidu.com/item/{movie_name}"
            client = httpx.Client(headers=self.headers, timeout=10, follow_redirects=True)
            resp = client.get(url)
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # 找剧情简介
            summary_divs = soup.select('.lemma-summary')
            plot = ""
            for div in summary_divs:
                plot += div.text.strip()
            
            client.close()
            
            if len(plot) > 50:
                return {
                    'plot': plot[:1000],
                    'genre': [],
                    'characters': [],
                    'type': 'movie'
                }
            
            return None
            
        except Exception as e:
            print(f"   [WARNING] 百科搜索失败: {e}")
            return None
    
    def _analyze_dialogues(
        self, 
        segments: List[Dict], 
        full_transcript: str
    ) -> Dict:
        """分析对话内容"""
        
        classic_dialogues = []
        emotional_beats = []
        
        # 情感关键词
        emotion_keywords = {
            '愤怒': ['滚', '去死', '混蛋', '王八蛋', '杀', '恨', '怒'],
            '悲伤': ['哭', '泪', '对不起', '死', '失去', '再见', '离开'],
            '惊讶': ['什么', '怎么可能', '不会吧', '天哪', '我的天'],
            '恐惧': ['害怕', '救命', '不要', '别杀', '求求你'],
            '紧张': ['快', '小心', '危险', '跑', '逃', '来不及'],
            '温情': ['爱', '喜欢', '想你', '谢谢', '对不起', '原谅'],
            '冲突': ['为什么', '凭什么', '你敢', '我不信', '说谎'],
        }
        
        # 经典台词模式（通常较长且有力量感）
        classic_patterns = [
            r'.{10,}[！!。]',  # 较长的感叹句或陈述句
            r'我.{5,}[！!]',  # 以"我"开头的宣言
            r'你.{5,}[？?]',  # 质问
        ]
        
        for seg in segments:
            text = seg.get('text', '')
            start_time = seg.get('start', 0)
            
            # 检测情感
            for emotion, keywords in emotion_keywords.items():
                if any(kw in text for kw in keywords):
                    # 计算强度
                    intensity = sum(1 for kw in keywords if kw in text) / len(keywords)
                    intensity = min(1.0, intensity * 3)  # 放大
                    
                    emotional_beats.append({
                        'time': start_time,
                        'text': text,
                        'emotion': emotion,
                        'intensity': intensity
                    })
                    break
            
            # 检测经典台词
            if len(text) > 15:  # 足够长
                for pattern in classic_patterns:
                    if re.search(pattern, text):
                        classic_dialogues.append({
                            'time': start_time,
                            'text': text,
                            'reason': '有力量的台词'
                        })
                        break
        
        # 去重和排序
        emotional_beats = sorted(emotional_beats, key=lambda x: x['intensity'], reverse=True)[:20]
        classic_dialogues = classic_dialogues[:15]
        
        return {
            'classic_dialogues': classic_dialogues,
            'emotional_beats': emotional_beats
        }
    
    def _infer_story_structure(
        self,
        segments: List[Dict],
        dialogue_analysis: Dict,
        plot_summary: str
    ) -> Dict:
        """推断剧情结构（起承转合）"""
        
        if not segments:
            return {}
        
        # 获取总时长
        total_duration = max(seg.get('end', seg.get('start', 0) + 3) for seg in segments)
        
        # 基于情感节点推断结构
        emotional_beats = dialogue_analysis.get('emotional_beats', [])
        
        # 找到最高潮点
        if emotional_beats:
            climax_time = max(emotional_beats, key=lambda x: x['intensity'])['time']
        else:
            climax_time = total_duration * 0.7  # 默认在70%位置
        
        # 构建结构
        structure = {
            'opening': {
                'time_range': [0, total_duration * 0.1],
                'description': '人物出场，背景介绍',
                'importance': 'medium'
            },
            'development': {
                'time_range': [total_duration * 0.1, climax_time - 60],
                'description': '冲突展开，矛盾升级',
                'importance': 'high'
            },
            'climax': {
                'time_range': [climax_time - 60, climax_time + 120],
                'description': '高潮对决，矛盾爆发',
                'importance': 'critical'
            },
            'resolution': {
                'time_range': [climax_time + 120, total_duration * 0.95],
                'description': '冲突解决，真相揭示',
                'importance': 'high'
            },
            'ending': {
                'time_range': [total_duration * 0.95, total_duration],
                'description': '结局收尾',
                'importance': 'medium'
            }
        }
        
        return structure
    
    def _identify_key_scenes(
        self,
        segments: List[Dict],
        dialogue_analysis: Dict,
        story_structure: Dict,
        plot_summary: str
    ) -> List[Dict]:
        """识别关键场景"""
        
        key_scenes = []
        
        # 从情感节点生成关键场景
        for beat in dialogue_analysis.get('emotional_beats', [])[:10]:
            key_scenes.append({
                'time': beat['time'],
                'duration': 10,  # 预估时长
                'description': f"{beat['emotion']}情感场景",
                'dialogue': beat['text'],
                'importance': 'high' if beat['intensity'] > 0.5 else 'medium',
                'reason': f"情感强度: {beat['intensity']:.2f}"
            })
        
        # 从经典台词生成关键场景
        for dialogue in dialogue_analysis.get('classic_dialogues', [])[:8]:
            # 检查是否重复
            if not any(abs(s['time'] - dialogue['time']) < 30 for s in key_scenes):
                key_scenes.append({
                    'time': dialogue['time'],
                    'duration': 8,
                    'description': '经典台词场景',
                    'dialogue': dialogue['text'],
                    'importance': 'high',
                    'reason': '有力量的台词'
                })
        
        # 从剧情结构添加关键节点
        for phase, info in story_structure.items():
            if info.get('importance') in ['critical', 'high']:
                time_range = info.get('time_range', [0, 0])
                mid_time = (time_range[0] + time_range[1]) / 2
                
                if not any(abs(s['time'] - mid_time) < 60 for s in key_scenes):
                    key_scenes.append({
                        'time': mid_time,
                        'duration': 15,
                        'description': info['description'],
                        'dialogue': '',
                        'importance': info['importance'],
                        'reason': f'{phase}阶段关键点'
                    })
        
        # 按时间排序
        key_scenes = sorted(key_scenes, key=lambda x: x['time'])
        
        return key_scenes


# 测试
if __name__ == "__main__":
    engine = StoryUnderstanding()
    
    # 模拟测试
    test_segments = [
        {'start': 10, 'end': 15, 'text': '你知道我是谁吗？'},
        {'start': 100, 'end': 110, 'text': '我要杀了你！'},
        {'start': 500, 'end': 510, 'text': '对不起，我爱你。'},
        {'start': 1000, 'end': 1010, 'text': '这一切都结束了。'},
    ]
    
    result = engine.understand(
        movie_name="测试电影",
        transcript_segments=test_segments,
        full_transcript="你知道我是谁吗？...我要杀了你！...对不起，我爱你...这一切都结束了。"
    )
    
    print(json.dumps(result, ensure_ascii=False, indent=2))

