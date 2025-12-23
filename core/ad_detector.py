# core/ad_detector.py - 广告检测模块 v1.0
"""
SmartVideoClipper - 中间广告检测与去除

检测方法：
1. 音频特征：广告通常音量更大、更稳定
2. 视觉特征：广告通常有品牌logo、文字叠加
3. 时长特征：广告通常是15秒、30秒、60秒的固定时长
4. 内容特征：广告与正片内容不连贯

常见广告类型：
- 片中广告（Mid-roll ads）
- 角标广告（Logo overlay）
- 贴片广告（Pre/Post-roll）
"""

import cv2
import numpy as np
import subprocess
import os
from typing import List, Dict, Tuple, Optional


class AdDetector:
    """广告检测器"""
    
    def __init__(self):
        # 广告典型时长（秒）
        self.ad_durations = [15, 30, 45, 60, 90, 120]
        # 广告时长容差
        self.duration_tolerance = 3
        
    def detect_ads(
        self,
        video_path: str,
        segments: List[Dict] = None
    ) -> List[Dict]:
        """
        检测视频中的广告段落
        
        参数：
            video_path: 视频路径
            segments: 语音识别的段落（可选，用于内容分析）
        
        返回：
            广告段落列表 [{'start': 0, 'end': 30, 'confidence': 0.8}, ...]
        """
        print("[AD] 检测中间广告...")
        
        if not os.path.exists(video_path):
            return []
        
        # 获取视频时长
        duration = self._get_duration(video_path)
        if duration < 300:  # 5分钟以下不检测
            print("   视频较短，跳过广告检测")
            return []
        
        ads = []
        
        # 方法1：检测音频突变（广告音量通常更大）
        audio_ads = self._detect_by_audio(video_path, duration)
        ads.extend(audio_ads)
        
        # 方法2：检测视觉突变（广告画面风格不同）
        visual_ads = self._detect_by_visual(video_path, duration)
        ads.extend(visual_ads)
        
        # 方法3：基于内容分析（广告内容与正片不连贯）
        if segments:
            content_ads = self._detect_by_content(segments, duration)
            ads.extend(content_ads)
        
        # 合并重叠的广告检测结果
        merged_ads = self._merge_detections(ads)
        
        # 过滤低置信度
        final_ads = [ad for ad in merged_ads if ad.get('confidence', 0) > 0.6]
        
        if final_ads:
            print(f"   检测到 {len(final_ads)} 个疑似广告段落:")
            for ad in final_ads:
                print(f"     {ad['start']:.0f}s - {ad['end']:.0f}s (置信度: {ad['confidence']:.1%})")
        else:
            print("   未检测到中间广告")
        
        return final_ads
    
    def _get_duration(self, video_path: str) -> float:
        """获取视频时长"""
        try:
            cmd = [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            return float(result.stdout.strip())
        except:
            return 0
    
    def _detect_by_audio(self, video_path: str, duration: float) -> List[Dict]:
        """通过音频特征检测广告"""
        ads = []
        
        # 分析全片音量分布
        volumes = []
        interval = 5  # 每5秒采样
        
        for t in range(0, int(duration), interval):
            vol = self._get_segment_volume(video_path, t, interval)
            volumes.append({'time': t, 'volume': vol})
        
        if not volumes:
            return []
        
        # 计算平均音量
        avg_volume = np.mean([v['volume'] for v in volumes])
        
        # 查找音量显著高于平均的连续段落
        loud_start = None
        for v in volumes:
            if v['volume'] > avg_volume + 5:  # 高于平均5dB
                if loud_start is None:
                    loud_start = v['time']
            else:
                if loud_start is not None:
                    loud_duration = v['time'] - loud_start
                    # 检查是否是典型广告时长
                    if self._is_ad_duration(loud_duration):
                        ads.append({
                            'start': loud_start,
                            'end': v['time'],
                            'confidence': 0.5,
                            'reason': '音量突高+典型时长'
                        })
                    loud_start = None
        
        return ads
    
    def _get_segment_volume(self, video_path: str, start: float, duration: float) -> float:
        """获取指定段落的音量"""
        try:
            cmd = [
                'ffmpeg', '-y',
                '-ss', str(start),
                '-i', video_path,
                '-t', str(duration),
                '-af', 'volumedetect',
                '-f', 'null', '-'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            for line in result.stderr.split('\n'):
                if 'mean_volume' in line:
                    try:
                        return float(line.split(':')[1].strip().replace(' dB', ''))
                    except:
                        pass
            return -60
        except:
            return -60
    
    def _detect_by_visual(self, video_path: str, duration: float) -> List[Dict]:
        """通过视觉特征检测广告"""
        ads = []
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []
        
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        
        # 每10秒采样一帧
        interval = 10
        frames_data = []
        
        for t in range(0, int(duration), interval):
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ret, frame = cap.read()
            
            if ret:
                # 计算帧特征
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                brightness = np.mean(gray)
                contrast = np.std(gray)
                
                # 边缘密度（广告通常有更多文字/logo）
                edges = cv2.Canny(gray, 50, 150)
                edge_density = np.mean(edges) / 255
                
                # 颜色饱和度（广告通常更鲜艳）
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                saturation = np.mean(hsv[:, :, 1])
                
                frames_data.append({
                    'time': t,
                    'brightness': brightness,
                    'contrast': contrast,
                    'edge_density': edge_density,
                    'saturation': saturation
                })
        
        cap.release()
        
        if not frames_data:
            return []
        
        # 计算平均值
        avg_brightness = np.mean([f['brightness'] for f in frames_data])
        avg_saturation = np.mean([f['saturation'] for f in frames_data])
        avg_edge = np.mean([f['edge_density'] for f in frames_data])
        
        # 查找视觉特征显著不同的段落
        anomaly_start = None
        for f in frames_data:
            # 广告特征：更亮、更饱和、更多边缘（文字/logo）
            is_anomaly = (
                f['brightness'] > avg_brightness * 1.3 or
                f['saturation'] > avg_saturation * 1.5 or
                f['edge_density'] > avg_edge * 2
            )
            
            if is_anomaly:
                if anomaly_start is None:
                    anomaly_start = f['time']
            else:
                if anomaly_start is not None:
                    anomaly_duration = f['time'] - anomaly_start
                    if self._is_ad_duration(anomaly_duration):
                        ads.append({
                            'start': anomaly_start,
                            'end': f['time'],
                            'confidence': 0.4,
                            'reason': '视觉特征异常+典型时长'
                        })
                    anomaly_start = None
        
        return ads
    
    def _detect_by_content(self, segments: List[Dict], duration: float) -> List[Dict]:
        """通过内容分析检测广告"""
        ads = []
        
        # 广告关键词
        ad_keywords = [
            '天猫', '淘宝', '京东', '拼多多', '抖音', '快手',
            '下载', 'APP', '扫码', '关注', '优惠', '折扣',
            '限时', '抢购', '点击', '链接', '二维码',
            '赞助', '冠名', '播出',
        ]
        
        # 查找包含广告关键词的段落
        for seg in segments:
            text = seg.get('text', '')
            start = seg.get('start', 0)
            end = seg.get('end', 0)
            
            # 检查是否包含广告关键词
            keyword_count = sum(1 for kw in ad_keywords if kw in text)
            
            if keyword_count >= 2:
                ads.append({
                    'start': start,
                    'end': end,
                    'confidence': min(0.3 + keyword_count * 0.1, 0.7),
                    'reason': f'包含广告关键词({keyword_count}个)'
                })
        
        return ads
    
    def _is_ad_duration(self, duration: float) -> bool:
        """检查是否是典型广告时长"""
        for ad_dur in self.ad_durations:
            if abs(duration - ad_dur) <= self.duration_tolerance:
                return True
        return False
    
    def _merge_detections(self, ads: List[Dict]) -> List[Dict]:
        """合并重叠的检测结果"""
        if not ads:
            return []
        
        # 按开始时间排序
        ads.sort(key=lambda x: x['start'])
        
        merged = []
        current = ads[0].copy()
        
        for ad in ads[1:]:
            # 检查是否重叠
            if ad['start'] <= current['end'] + 5:  # 5秒容差
                # 合并
                current['end'] = max(current['end'], ad['end'])
                current['confidence'] = max(current['confidence'], ad['confidence'])
            else:
                merged.append(current)
                current = ad.copy()
        
        merged.append(current)
        return merged


def filter_ad_segments(
    timeline: List[Dict],
    ads: List[Dict]
) -> List[Dict]:
    """
    从时间线中过滤掉广告段落
    
    参数：
        timeline: 原始时间线
        ads: 检测到的广告列表
    
    返回：
        过滤后的时间线
    """
    if not ads:
        return timeline
    
    filtered = []
    
    for item in timeline:
        start = item.get('source_start', item.get('start_time', 0))
        end = item.get('source_end', item.get('end_time', 0))
        
        # 检查是否在广告段落内
        is_ad = False
        for ad in ads:
            # 如果超过50%在广告段内，则视为广告
            overlap_start = max(start, ad['start'])
            overlap_end = min(end, ad['end'])
            overlap = max(0, overlap_end - overlap_start)
            
            if overlap > (end - start) * 0.5:
                is_ad = True
                break
        
        if not is_ad:
            filtered.append(item)
    
    removed_count = len(timeline) - len(filtered)
    if removed_count > 0:
        print(f"[AD] 过滤了 {removed_count} 个广告相关场景")
    
    return filtered


# 测试
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        video = sys.argv[1]
        detector = AdDetector()
        ads = detector.detect_ads(video)
        
        if ads:
            print("\n检测到的广告:")
            for ad in ads:
                print(f"  {ad['start']:.0f}s - {ad['end']:.0f}s ({ad['reason']})")
    else:
        print("用法: python ad_detector.py video.mp4")

